"""Export the musculoskeletal scope of Z-Anatomy as Draco glTF.

    blender -b source/Z-Anatomy/Startup.blend --python tools/export_regions.py -- \
        [--out .] [--render verification/regions] [--samples verification/decimation] \
        [--regions knee,hip] [--skip-overview] [--no-measure]

One file per region plus an overview, an insertion layer per region, a
manifest, region-assignment.csv. Prints EXPORT_OK and exits zero; any
assertion is a hard stop. Nothing here touches the authored nerves.

What the model does that the inventory did not predict, and how it is handled:

  * 971 of the 2,054 kept objects are mirrored with a negative-scale transform
    and SHARE their mesh datablock with the contralateral twin (the .l side is
    the mirror of the .r). Exporting that as-is reproduces the inside-out bug
    from the nerve job. Every object is therefore baked to world space here,
    and any object whose world matrix has a negative determinant has its
    winding reversed after the bake, so the exported normals point outward on
    both sides and every node carries an identity transform. Because twins
    share data, decimation runs once per datablock and is baked twice.
  * 1,201 kept objects carry modifiers. The inventory counted base meshes, but
    for the ligaments the base mesh is a cage of a handful of triangles that
    only becomes a ligament once Subdivision and Solidify have run - the
    anterior talofibular ligament is two triangles before its modifiers. So
    skeletal, muscular and articular objects are exported as the atlas
    displays them: the viewport-evaluated mesh, modifiers applied. The 705
    insertion footprints are the exception: their Subdivision + Solidify
    would take them from 63,843 to 931,484 triangles for a 0.5 mm skin on a
    painted patch, so they are exported as flat base-mesh patches, at full
    resolution, as the brief's budget assumed. Materials are exported
    double-sided so nothing thin disappears from behind.
  * A few closed meshes are wound inside-out in the source on both sides
    (the acetabular labrum, for one). Any closed mesh whose signed volume is
    negative after the bake is flipped, and named in the manifest.
  * A source mesh whose attachment is demonstrably wrong is redrawn here by
    anchor rule - tools/corrections.py - never hand-edited in the .blend.
    The object keeps its name, material, collection and parent; only the
    mesh data written for it is replaced, and its node carries
    corrected = True and source = "redrawn" in its extras. The rules are
    resolved against the live source objects before anything is renamed,
    and the result is recorded in corrections.json beside the manifest.
"""

import argparse
import json
import os
import struct
import sys
import time
from collections import Counter, defaultdict

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import corrections  # noqa: E402
import regions  # noqa: E402
import scope  # noqa: E402

OVERVIEW_TARGET = 200000
REGION_RATIO = 0.5                    # own meshes
CONTEXT_RATIO = 0.25 * REGION_RATIO   # 25% of the neighbour's target
FLOOR_OVERVIEW = 24                   # no mesh collapses below this in the overview
FLOOR_REGION = 16
FLOOR_CONTEXT = 24

t0 = time.time()


def log(msg):
    print("[%6.1fs] %s" % (time.time() - t0, msg))
    sys.stdout.flush()


# ------------------------------------------------------------ inventory


def collection_paths():
    paths = {}

    def walk(coll, prefix):
        p = (prefix + "/" + coll.name) if prefix else coll.name
        paths[coll.name] = p
        for child in coll.children:
            walk(child, p)

    walk(bpy.context.scene.collection, "")
    return paths


def triangles_of(me):
    return sum(max(len(p.vertices) - 2, 0) for p in me.polygons)


def inventory_rows():
    """The same fields tools/inventory.py writes, from the live model."""
    paths = collection_paths()
    rows = []
    for ob in bpy.data.objects:
        tris = triangles_of(ob.data) if ob.type == "MESH" and ob.data else 0
        corners = [ob.matrix_world @ Vector(c[:]) for c in ob.bound_box]
        rows.append({
            "object_name": ob.name,
            "object_type": ob.type,
            "triangles": tris,
            "all_collections": [paths.get(c.name, c.name) for c in ob.users_collection],
            "centroid_x": sum(c.x for c in corners) / 8.0,
            "centroid_y": sum(c.y for c in corners) / 8.0,
            "centroid_z": sum(c.z for c in corners) / 8.0,
            "ob": ob,
        })
    return rows


# ------------------------------------------------------------ source meshes


class Source:
    """One kept object: its source mesh, world matrix and metadata."""

    def __init__(self, row, assignment, depsgraph, corrected=None):
        self.name = row["object_name"]
        self.ob = row["ob"]
        self.system = row["system"]
        self.region = assignment["region"]
        self.signal = assignment["signal"]
        self.side = scope.side_of(self.name)
        self.matrix = self.ob.matrix_world.copy()
        self.mirrored = self.matrix.determinant() < 0
        self.inventory_tris = int(row["triangles"])
        self.modifiers = [m.type for m in self.ob.modifiers if m.show_viewport]
        self.corrected = bool(corrected) and self.name in corrected
        if self.corrected:
            # Redrawn by rule: the corrected geometry in this object's own
            # frame, so the bake below treats it like any other source mesh.
            # Its modifiers are not applied - the ribbon is finished geometry.
            verts, tris, _rec = corrected[self.name]
            self.mesh = corrections.local_mesh(self.name, self.ob, verts, tris)
            self.modifiers = []
        elif self.system == "insertion" or not self.modifiers:
            self.mesh = self.ob.data
            self.modifiers = [] if self.system == "insertion" else self.modifiers
        else:
            self.mesh = bpy.data.meshes.new_from_object(self.ob.evaluated_get(depsgraph))
            self.mesh.name = "eval|" + self.name
        self.source_tris = triangles_of(self.mesh)
        self.exported_tris = None

    @property
    def key(self):
        return self.mesh.name


def share_evaluated_twins(sources):
    """Twins that share a base datablock and evaluate to identical local-space
    meshes share the evaluated mesh too, so decimation still runs once."""
    import numpy as np
    by_name = {s.name: s for s in sources}
    shared = 0
    for s in sources:
        if s.side != "l" or not s.modifiers:
            continue
        t = by_name.get(scope.twin_of(s.name))
        if t is None or not t.modifiers or s.ob.data is not t.ob.data:
            continue
        a, b = s.mesh, t.mesh
        if len(a.vertices) != len(b.vertices) or len(a.polygons) != len(b.polygons):
            continue
        va = np.empty(len(a.vertices) * 3)
        vb = np.empty(len(b.vertices) * 3)
        a.vertices.foreach_get("co", va)
        b.vertices.foreach_get("co", vb)
        if np.abs(va - vb).max() > 1e-7:
            continue
        bpy.data.meshes.remove(a)
        s.mesh = b
        shared += 1
    return shared


def mirror_check(sources):
    """Which twin pairs are true mirrors: same datablock and world matrices
    related by an X reflection (to 0.1 mm at the far corner of the box)."""
    by_name = {s.name: s for s in sources}
    flipx = Matrix.Diagonal((-1, 1, 1, 1))
    stats = Counter()
    for s in sources:
        if s.side != "l":
            continue
        t = by_name.get(scope.twin_of(s.name))
        if t is None:
            stats["unpaired"] += 1
            continue
        if s.mesh is not t.mesh:
            stats["separate-data"] += 1
            continue
        d = flipx @ t.matrix - s.matrix
        corners = [Vector(c[:]) for c in s.ob.bound_box]
        worst = max((d @ c).length for c in corners) if corners else 0.0
        stats["mirror-instance" if worst < 1e-4 else "shared-data-not-mirror"] += 1
    return stats


# ------------------------------------------------------------ decimation


class Decimator:
    def __init__(self):
        self.scene = bpy.data.scenes.new("decimate")
        self.cache = {}
        self.calls = 0

    @staticmethod
    def target(base, ratio, floor):
        if base <= floor:
            return base
        return max(floor, int(round(base * ratio)))

    def get(self, src_mesh, target):
        """A mesh with about `target` triangles, decimated by COLLAPSE from
        src_mesh. Cached per (datablock, target) so mirrored twins share."""
        base = triangles_of(src_mesh)
        if target >= base:
            return src_mesh, base
        key = (src_mesh.name, target)
        if key in self.cache:
            return self.cache[key]
        tmp = bpy.data.objects.new("__decimate", src_mesh)
        self.scene.collection.objects.link(tmp)
        md = tmp.modifiers.new("decimate", "DECIMATE")
        md.decimate_type = "COLLAPSE"
        md.ratio = target / float(base)
        md.use_collapse_triangulate = True
        with bpy.context.temp_override(scene=self.scene, view_layer=self.scene.view_layers[0]):
            dg = bpy.context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
        me.name = "%s|%d" % (src_mesh.name[:40], target)
        # Materials survive new_from_object, but make the slots match the
        # source exactly so material_index attributes still mean the same thing.
        me.materials.clear()
        for mat in src_mesh.materials:
            me.materials.append(mat)
        self.scene.collection.objects.unlink(tmp)
        bpy.data.objects.remove(tmp)
        self.calls += 1
        out = (me, triangles_of(me))
        self.cache[key] = out
        return out


def solve_overview_ratio(sources):
    """The uniform ratio that lands the overview on its budget once the floor
    is applied: proportional, so a mesh that is 5% of the model keeps 5% of
    the budget, floored so nothing collapses to nothing."""
    counts = [s.source_tris for s in sources]

    def total(ratio):
        return sum(t if t <= FLOOR_OVERVIEW else max(FLOOR_OVERVIEW, int(round(t * ratio)))
                   for t in counts)

    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if total(mid) < OVERVIEW_TARGET:
            lo = mid
        else:
            hi = mid
    return hi, total(hi)


# ------------------------------------------------------------ baking / export


_volume_cache = {}


def closed_and_volume(me):
    """(closed, signed volume) in the mesh's own frame, cached per datablock."""
    if me.name in _volume_cache:
        return _volume_cache[me.name]
    bm = bmesh.new()
    bm.from_mesh(me)
    closed = all(not e.is_boundary for e in bm.edges)
    vol = bm.calc_volume(signed=True)
    bm.free()
    _volume_cache[me.name] = (closed, vol)
    return closed, vol


winding_corrected = set()


def bake_mesh(src, mesh, label):
    """A world-space copy of `mesh` for object `src`, winding corrected:
    reversed when the object's transform is a mirror, and reversed again if
    the closed result still has negative volume - i.e. the source was wound
    inside-out to begin with."""
    me = mesh.copy()
    me.name = "%s|%s" % (label, src.name)
    me.transform(src.matrix)
    if src.mirrored:
        me.flip_normals()
    # A mirror transform followed by a flip leaves the signed volume equal to
    # the local one, so the local sign is the world sign for every object.
    closed, vol = closed_and_volume(mesh)
    if closed and vol < 0:
        me.flip_normals()
        winding_corrected.add(src.name)
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.update()
    return me


def bake(src, mesh, context):
    me = bake_mesh(src, mesh, "bake")
    ob = bpy.data.objects.new(src.name, me)
    ob["sourceName"] = src.name
    ob["region"] = src.region
    ob["side"] = src.side
    ob["context"] = bool(context)
    ob["system"] = src.system
    if src.corrected:
        ob["corrected"] = True
        ob["source"] = "redrawn"
    assert ob.name == src.name, "name collision on %r -> %r" % (src.name, ob.name)
    return ob


def read_glb_nodes(path):
    """{node name: triangles} from the file's JSON chunk - what the file says,
    not what was asked for. The manifest is filled from this."""
    with open(path, "rb") as f:
        b = f.read()
    magic = struct.unpack("<I", b[:4])[0]
    assert magic == 0x46546C67, path
    clen = struct.unpack("<I", b[12:16])[0]
    g = json.loads(b[20:20 + clen])
    out = {}
    for n in g["nodes"]:
        if "mesh" not in n:
            continue
        t = 0
        for pr in g["meshes"][n["mesh"]]["primitives"]:
            t += g["accessors"][pr["indices"]]["count"] // 3
        out[n["name"]] = t
    return out


class Exporter:
    def __init__(self, outdir, draco=True):
        self.outdir = outdir
        self.draco = draco
        self.scene = bpy.data.scenes.new("export")
        self.coll = bpy.data.collections.new("export")
        self.scene.collection.children.link(self.coll)

    def add(self, ob):
        self.coll.objects.link(ob)

    def clear(self):
        for ob in list(self.coll.objects):
            me = ob.data
            self.coll.objects.unlink(ob)
            bpy.data.objects.remove(ob)
            if me.users == 0:
                bpy.data.meshes.remove(me)

    def write(self, filename):
        path = os.path.join(self.outdir, filename)
        expected = {ob.name for ob in self.coll.objects}
        with bpy.context.temp_override(scene=self.scene, view_layer=self.scene.view_layers[0]):
            bpy.ops.export_scene.gltf(
                filepath=path,
                export_format="GLB",
                use_active_scene=True,
                export_apply=False,
                export_extras=True,
                export_yup=True,
                export_normals=True,
                export_texcoords=True,
                export_colors=False,
                export_tangents=False,
                export_materials="EXPORT",
                export_image_format="NONE",
                export_cameras=False,
                export_lights=False,
                export_animations=False,
                export_skins=False,
                export_morph=False,
                export_draco_mesh_compression_enable=self.draco,
                export_draco_mesh_compression_level=6,
            )
        nodes = read_glb_nodes(path)
        assert set(nodes) == expected, "%s: exported %d nodes, expected %d" % (
            filename, len(nodes), len(expected))
        return os.path.getsize(path), nodes


# ------------------------------------------------------------ deviation


def deviation(src, dec_mesh):
    """How far the decimated surface strays from the source, in metres:
    nearest-surface distance from every decimated vertex to the source mesh,
    both in the object's local frame. Unsigned is what is wanted here - this is
    a magnitude of drift, not an inside/outside test."""
    sm = src.mesh
    bvh = BVHTree.FromPolygons([v.co for v in sm.vertices],
                               [list(p.vertices) for p in sm.polygons], all_triangles=False)
    ds = []
    for v in dec_mesh.vertices:
        hit = bvh.find_nearest(v.co)
        if hit[0] is not None:
            ds.append(hit[3])
    if not ds:
        return None
    ds.sort()
    corners = [Vector(c[:]) for c in src.ob.bound_box]
    diag = (corners[6] - corners[0]).length if len(corners) == 8 else 0.0
    return {"mean": sum(ds) / len(ds), "p95": ds[int(0.95 * (len(ds) - 1))],
            "max": ds[-1], "diag": diag}


# ------------------------------------------------------------ main


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--no-samples", action="store_true",
                    help="skip samples.glb, the decimation tiers of a few representative meshes")
    ap.add_argument("--regions", help="comma-separated subset, for iteration")
    ap.add_argument("--skip-overview", action="store_true")
    ap.add_argument("--no-measure", action="store_true")
    ap.add_argument("--no-draco", action="store_true")
    args = ap.parse_args(argv)
    outdir = os.path.abspath(args.out)
    os.makedirs(outdir, exist_ok=True)
    which = args.regions.split(",") if args.regions else list(regions.REGIONS)
    for r in which:
        assert r in regions.REGIONS, r

    # -- scope, licence, assignment ----------------------------------------
    rows = inventory_rows()
    kept, excluded, report = scope.partition(rows)
    print(scope.format_report(report))
    assignment = regions.assign(kept)
    csv_path = os.path.join(outdir, "region-assignment.csv")
    regions.write_csv(csv_path, kept, assignment)
    print(regions.summary(kept, assignment))
    log("assignment written to %s" % csv_path)

    # -- corrected geometry -------------------------------------------------
    # Resolved by name against the live source objects, so this runs before
    # the originals are renamed below. A rule that misses its acceptance box
    # raises here and stops the export.
    log("resolving corrected geometry")
    corrected = corrections.resolve_all()
    for name in corrected:
        assert any(r["object_name"] == name for r in kept), "corrected object not in scope: %s" % name
    corrections.write_record(os.path.join(outdir, "corrections.json"), corrected)
    log("corrected geometry: %s" % ", ".join(corrected))

    # -- source meshes ------------------------------------------------------
    # Rename the originals out of the way so exported nodes can carry the
    # exact source names; Source objects keep hold of them.
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for i, r in enumerate(kept):
        r["ob"].name = "src|%04d" % i
    sources = [Source(r, assignment[r["object_name"]], depsgraph, corrected) for r in kept]
    by_name = {s.name: s for s in sources}
    shared = share_evaluated_twins(sources)
    mirror_stats = mirror_check(sources)
    log("mirror pairs: %s (evaluated meshes shared between twins: %d)" % (dict(mirror_stats), shared))
    mod_stats = Counter()
    for s in sources:
        for m in s.modifiers:
            mod_stats[(s.system, m)] += 1
    log("modifiers applied: %s" % ", ".join("%s/%s=%d" % (k[0], k[1], v) for k, v in sorted(mod_stats.items())))
    per_system = defaultdict(lambda: [0, 0, 0])
    for s in sources:
        p = per_system[s.system]
        p[0] += 1
        p[1] += s.inventory_tris
        p[2] += s.source_tris
    for sy, (n, a, b) in sorted(per_system.items()):
        log("source %-9s %4d meshes: inventory %8d -> exported source %8d triangles" % (sy, n, a, b))

    # Double-sided materials: anything thin must not vanish from behind.
    for s in sources:
        for mat in s.mesh.materials:
            if mat is not None:
                mat.use_backface_culling = False

    # -- budgets ------------------------------------------------------------
    dec = Decimator()
    exp = Exporter(outdir, draco=not args.no_draco)
    non_insertion = [s for s in sources if s.system != "insertion"]
    ov_ratio, ov_total = solve_overview_ratio(non_insertion)
    log("overview ratio %.4f -> %d triangles planned" % (ov_ratio, ov_total))

    by_region = defaultdict(list)
    for s in sources:
        by_region[s.region].append(s)

    manifest = {
        "version": 1,
        "units": "metres",
        "up": "Z",
        "sideConvention": {"l": "+X", "r": "-X"},
        "source": {
            "model": "Z-Anatomy/Startup.blend",
            "blender": bpy.app.version_string,
            "scope": "collections 1-4 (skeletal, insertions, joints, muscular); EXCLUSIONS.md applied",
            "inventoryMeshes": report["scope_meshes"],
            "inventoryTriangles": report["scope_triangles"],
            "licenceExcluded": report["excluded_names"],
            "licenceExcludedTriangles": report["excluded_triangles"],
            "keptMeshes": len(sources),
            "keptInventoryTriangles": sum(s.inventory_tris for s in sources),
            "keptSourceTriangles": sum(s.source_tris for s in sources),
            "perSystem": {sy: {"meshes": n, "inventoryTriangles": a, "sourceTriangles": b}
                          for sy, (n, a, b) in sorted(per_system.items())},
        },
        "geometry": {
            "coordinates": "world space baked; every node has an identity transform",
            "yUp": "exported with glTF Y-up: Blender +Z -> +Y, Blender -Y -> +Z; sides unchanged (.l at +X)",
            "modifiers": "viewport-evaluated for skeletal, muscular and articular; base mesh for insertions",
            "modifiersApplied": {"%s/%s" % k: v for k, v in sorted(mod_stats.items())},
            "mirrorPairs": dict(mirror_stats),
            "windingCorrected": [],
            "materials": "atlas materials, exported double-sided, no textures",
        },
        "overview": None,
        "regions": [],
        "nerves": {"file": "nerves.glb", "authored": True, "source": "schematic"},
        "objects": [],
    }
    stats = {"deviation": defaultdict(list), "raised": []}

    # A decimated mesh whose surface has drifted more than this fraction of
    # its own bounding-box diagonal has lost its shape. It is re-decimated at
    # a gentler ratio, up to keeping the source, and the retreat is recorded.
    # This is the brief's "raise the ratio for that class" made measurable.
    MAX_DRIFT = 0.05
    RETREAT = [0.75, 1.0]

    def decimate_checked(tier, s, ratio, floor):
        me, n = dec.get(s.mesh, dec.target(s.source_tris, ratio, floor))
        if args.no_measure or me is s.mesh:
            return me, n
        d = deviation(s, me)
        used = ratio
        for r in RETREAT:
            if d is None or d["diag"] <= 0 or d["max"] <= MAX_DRIFT * d["diag"] or r <= used:
                break
            me, n = dec.get(s.mesh, dec.target(s.source_tris, r, floor))
            used = r
            d = deviation(s, me) if me is not s.mesh else None
        if used != ratio:
            rec = {"sourceName": s.name, "system": s.system, "tier": tier,
                   "from": round(ratio, 5), "to": used, "triangles": n}
            if rec not in stats["raised"]:       # context meshes are measured once per region
                stats["raised"].append(rec)
        if d:
            stats["deviation"][tier].append((s.name, s.system, d))
        return me, n

    # -- overview -----------------------------------------------------------
    if not args.skip_overview:
        for s in non_insertion:
            me, n = decimate_checked("overview", s, ov_ratio, FLOOR_OVERVIEW)
            exp.add(bake(s, me, False))
        nbytes, nodes = exp.write("overview.glb")
        exp.clear()
        total = sum(nodes.values())
        manifest["overview"] = {"file": "overview.glb", "triangles": total, "bytes": nbytes,
                                "meshCount": len(nodes), "target": OVERVIEW_TARGET,
                                "ratio": round(ov_ratio, 5),
                                "note": "skeletal, muscular and articular meshes; insertions are "
                                        "per-region layers and are not in the overview"}
        log("overview: %d meshes, %d triangles, %d bytes" % (len(nodes), total, nbytes))

    # -- regions ------------------------------------------------------------
    for region in which:
        own = [s for s in by_region[region] if s.system != "insertion"]
        ins = [s for s in by_region[region] if s.system == "insertion"]
        ctx = [s for n in regions.NEIGHBOURS[region] for s in by_region[n] if s.system != "insertion"]
        own_src = sum(s.source_tris for s in own)
        for s in own:
            me, n = decimate_checked("region", s, REGION_RATIO, FLOOR_REGION)
            exp.add(bake(s, me, False))
        for s in ctx:
            me, n = decimate_checked("context", s, CONTEXT_RATIO, FLOOR_CONTEXT)
            exp.add(bake(s, me, True))
        nbytes, nodes = exp.write("%s.glb" % region)
        exp.clear()
        own_tris = sum(nodes[s.name] for s in own)
        ctx_tris = sum(nodes[s.name] for s in ctx)
        for s in own:
            s.exported_tris = nodes[s.name]

        for s in ins:
            exp.add(bake(s, s.mesh, False))
        ins_bytes, ins_nodes = exp.write("%s-insertions.glb" % region)
        exp.clear()
        for s in ins:
            s.exported_tris = ins_nodes[s.name]
        ins_tris = sum(ins_nodes.values())

        sides = Counter(s.side for s in by_region[region])
        target = int(round(own_src * REGION_RATIO))
        manifest["regions"].append({
            "id": region,
            "file": "%s.glb" % region,
            "triangles": own_tris + ctx_tris,
            "ownTriangles": own_tris,
            "contextTriangles": ctx_tris,
            "sourceTriangles": own_src,
            "inventoryTriangles": sum(s.inventory_tris for s in own),
            "targetTriangles": target,
            "bytes": nbytes,
            "meshCount": len(own),
            "contextMeshCount": len(ctx),
            "contextRegions": regions.NEIGHBOURS[region],
            "sides": {"l": sides["l"], "r": sides["r"], "": sides[""]},
            "insertionLayer": {"file": "%s-insertions.glb" % region, "triangles": ins_tris,
                               "bytes": ins_bytes, "meshCount": len(ins)},
        })
        log("%s: own %d meshes %d->%d tris (target %d, %+.1f%%), context %d meshes %d tris, "
            "%d bytes; insertions %d meshes %d tris %d bytes" % (
                region, len(own), own_src, own_tris, target, 100.0 * (own_tris - target) / max(target, 1),
                len(ctx), ctx_tris, nbytes, len(ins), ins_tris, ins_bytes))

    # -- join table ---------------------------------------------------------
    for s in sources:
        manifest["objects"].append({
            "sourceName": s.name, "region": s.region, "side": s.side, "system": s.system,
            "triangles": s.exported_tris,
            "sourceTriangles": s.source_tris,
            "inventoryTriangles": s.inventory_tris,
            "signal": s.signal,
        })
    manifest["objects"].sort(key=lambda o: o["sourceName"])
    manifest["geometry"]["windingCorrected"] = sorted(winding_corrected)

    # -- deviation summary --------------------------------------------------
    dev_summary = {}
    for tier, items in stats["deviation"].items():
        per_sys = defaultdict(list)
        for name, system, d in items:
            per_sys[system].append((name, d))
        dev_summary[tier] = {}
        for system, lst in sorted(per_sys.items()):
            maxes = [d["max"] for _, d in lst]
            rel = sorted(((d["max"] / d["diag"] if d["diag"] else 0.0, n, d) for n, d in lst), reverse=True)
            dev_summary[tier][system] = {
                "meshes": len(lst),
                "meanOfMean_mm": round(1000 * sum(d["mean"] for _, d in lst) / len(lst), 3),
                "meanOfP95_mm": round(1000 * sum(d["p95"] for _, d in lst) / len(lst), 3),
                "meanOfMax_mm": round(1000 * sum(maxes) / len(maxes), 3),
                "worstMax_mm": round(1000 * max(maxes), 3),
                "worstRelative": [
                    {"sourceName": n, "max_mm": round(1000 * d["max"], 2),
                     "maxOverDiagonal": round(r, 4)} for r, n, d in rel[:6]],
            }
    manifest["decimation"] = {
        "method": "Blender Decimate modifier, COLLAPSE, triangulated, per datablock; "
                  "twins sharing data decimated once and baked twice",
        "overviewTarget": OVERVIEW_TARGET, "overviewRatio": round(ov_ratio, 5),
        "regionRatio": REGION_RATIO, "contextRatio": CONTEXT_RATIO,
        "floors": {"overview": FLOOR_OVERVIEW, "region": FLOOR_REGION, "context": FLOOR_CONTEXT},
        "maxDriftOfDiagonal": MAX_DRIFT,
        "ratioRaised": stats["raised"],
        "deviation": dev_summary,
    }

    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    log("manifest written; winding corrected on %d objects; ratio raised on %d decimations" % (
        len(winding_corrected), len(stats["raised"])))

    # -- decimation samples ---------------------------------------------------
    # A few representative meshes at every tier, in one gitignored file, for
    # tools/render_export.py to lay out side by side. Rendering happens in a
    # separate factory-startup Blender from the exported files: Cycles crashes
    # syncing the baked meshes in this process, and rendering what was shipped
    # is the better review anyway.
    if not args.no_samples:
        SAMPLES = ["Iliotibial tract.l", "Scapula.l", "Rectus femoris muscle.l",
                   "External intercostal muscles.l", "Articular capsule of knee joint.l",
                   "Fibular collateral ligament.l", "Costal cartilage of seventh rib.l",
                   "Diaphragm", "Superficial part of masseter.l", "Fascia lata.l",
                   "Lumbrical muscles of hand.l", "Anterior cruciate ligament.l"]
        for name in SAMPLES:
            s = by_name.get(name)
            if s is None:
                log("sample %s not found" % name)
                continue
            tiers = [("source", 1.0, None)]
            tiers += [("50%", REGION_RATIO, FLOOR_REGION), ("12.5% context", CONTEXT_RATIO, FLOOR_CONTEXT),
                      ("overview %.1f%%" % (100 * ov_ratio), ov_ratio, FLOOR_OVERVIEW)]
            for i, (label, ratio, floor) in enumerate(tiers):
                if floor is None:
                    me, n = s.mesh, s.source_tris
                else:
                    me, n = dec.get(s.mesh, dec.target(s.source_tris, ratio, floor))
                ob = bpy.data.objects.new("%s|%d" % (name, i), bake_mesh(s, me, "sample"))
                ob["sourceName"] = name
                ob["tier"] = i
                ob["label"] = label
                ob["triangles"] = n
                ob["system"] = s.system
                exp.add(ob)
        sb, _ = exp.write("samples.glb")
        exp.clear()
        log("samples.glb written, %d bytes" % sb)

    total_bytes = (manifest["overview"]["bytes"] if manifest["overview"] else 0) + sum(
        r["bytes"] + r["insertionLayer"]["bytes"] for r in manifest["regions"])
    print("EXPORT_OK meshes=%d regions=%d files=%d bytes=%d decimations=%d" % (
        len(sources), len(manifest["regions"]),
        (0 if args.skip_overview else 1) + 2 * len(manifest["regions"]), total_bytes, dec.calls))


if __name__ == "__main__":
    main()
