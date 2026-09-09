"""Carry our layers onto the BodyParts3D body and write them in Human Atlas's chunk format.

What goes across, from the exported region files, the insertion layers and
nerves.glb - never from the .blend:

    fascia           muscular meshes whose material is Fascia, Bursa or Fat, and any
                     mesh an MVMT structure of system "fascial" claims
    ligaments        every articular mesh (joints & ligaments)
    insertions       every insertion patch, projected onto the nearest BP3D bone
    peripheral-nerves the authored nerves, transformed as geometry
    central-nerves   the authored cervical roots and lumbosacral plexus, plus a
                     spinal cord and cauda equina authored here through the BP3D
                     vertebral canal - all schematic, all labelled so
    landmarks        the 42 landmarks as resolved on the BP3D bones by the fit,
                     as small spheres, with the fit's confidence

Fascia, ligaments and nerves are transformed through bp3d-fit.json and left
where the fit puts them. Insertion patches are then projected onto the nearest
BP3D bone surface, and how far each moved is recorded. Landmarks are the BP3D
rule results themselves, so they sit on BP3D bone by construction; the record
confirms it. Skeletal and muscular meshes are BP3D's own and do not come across.

Chunks: one per MVMT region, holding that region's parts and nothing else, so
a region can be fetched on its own. A part lives in the region the fit's blend
weights give its centroid (or the region our export assigned it); the parts
that span into a neighbouring region are listed under that region as well.

Runs in a factory-startup Blender 3.6 (it decodes the Draco files); opens no
.blend.

    blender -b --python tools/bp3d_export.py -- --atlas <mvmt-atlas/public/models>
        --glb <dir with the region .glb files> --nerves <nerves.glb>
        --join <mvmt-program/assets/structure-meshes.json> --anatomy <anatomy.json>
        --out <dir for mvmt-*.bin and mvmt-layers.json> [--render <dir>]

Prints BP3D_EXPORT_OK or exits non-zero.
"""

import argparse
import json
import math
import os
import re
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.append(HERE)
import bp3d_fit as FIT  # noqa: E402
from regions import REGIONS, NEIGHBOURS  # noqa: E402

REGION_NAMES = {"head-jaw": "Head & jaw", "cervical": "Cervical", "shoulder": "Shoulder",
                "elbow-wrist": "Elbow & wrist", "thoracic": "Thoracic", "lumbar": "Lumbar",
                "hip": "Hip", "knee": "Knee", "ankle-foot": "Ankle & foot"}
FASCIA_MATERIALS = ("Fascia", "Bursa", "Fat")
CENTRAL_NERVES = ("nerve-cervical-roots", "nerve-lumbosacral-plexus")
INSERTION_LIFT = 0.0005        # metres off the bone after projection, so the patch is not in the surface
LANDMARK_RADIUS = 0.004
LOW_CONFIDENCE = 0.010         # a landmark whose fit residual exceeds this is fitConfidence: low
PROJECTION_FLAG = 0.005        # an insertion patch that moved more than this is counted
SEAM_STRUCTURES = ("Iliotibial tract", "nerve-sciatic", "thoracolumbar fascia", "Fascia lata",
                   "nerve-tibial", "nerve-common-fibular", "nerve-median", "nerve-ulnar", "nerve-radial",
                   "Plantar aponeurosis", "Crural fascia", "Brachial fascia", "Antebrachial fascia",
                   "Epicranial aponeurosis", "Linea alba", "Investing abdominal fascia")

LANDMARK_REGION = {  # landmark_anchors region tag -> MVMT region, with the exceptions named
    "head-neck": "head-jaw", "shoulder": "shoulder", "thorax": "thoracic", "elbow": "elbow-wrist",
    "wrist": "elbow-wrist", "pelvis": "hip", "hip": "hip", "knee": "knee", "ankle": "ankle-foot", "foot": "ankle-foot"}
LANDMARK_REGION_BY_ID = {"lm-c1-transverse": "cervical", "lm-c2-spinous": "cervical", "lm-c7-spinous": "cervical",
                         "lm-sacral-base": "lumbar", "lm-psis": "lumbar"}


def log(msg):
    print("[bp3d_export] " + msg, flush=True)


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


# ------------------------------------------------------------- geometry

def vertex_normals(V, F):
    n = np.zeros_like(V)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    fn = np.cross(b - a, c - a)
    for k in range(3):
        np.add.at(n, F[:, k], fn)
    length = np.linalg.norm(n, axis=1)
    length[length == 0] = 1
    return n / length[:, None]


def tube(points, radius, segments=12):
    """A closed tube along a polyline, parallel-transport frames, triangle faces."""
    P = np.asarray(points, dtype=np.float64)
    n = len(P)
    T = np.zeros_like(P)
    T[:-1] = P[1:] - P[:-1]
    T[-1] = T[-2]
    T[1:-1] = (P[2:] - P[:-2])
    T /= np.linalg.norm(T, axis=1)[:, None]
    # initial normal: anything not parallel to T[0]
    ref = np.array([1.0, 0, 0]) if abs(T[0][0]) < 0.9 else np.array([0, 1.0, 0])
    N = np.cross(T[0], ref)
    N /= np.linalg.norm(N)
    rings = []
    for i in range(n):
        if i:
            # transport N across the bend
            b = np.cross(T[i - 1], T[i])
            s = np.linalg.norm(b)
            if s > 1e-9:
                b /= s
                ang = math.atan2(s, float(np.dot(T[i - 1], T[i])))
                N = N * math.cos(ang) + np.cross(b, N) * math.sin(ang) + b * np.dot(b, N) * (1 - math.cos(ang))
            N -= T[i] * np.dot(N, T[i])
            N /= np.linalg.norm(N)
        B = np.cross(T[i], N)
        ring = [P[i] + radius * (math.cos(2 * math.pi * k / segments) * N + math.sin(2 * math.pi * k / segments) * B)
                for k in range(segments)]
        rings.append(ring)
    V = np.array([v for ring in rings for v in ring])
    F = []
    for i in range(n - 1):
        for k in range(segments):
            a = i * segments + k
            b = i * segments + (k + 1) % segments
            c = (i + 1) * segments + k
            d = (i + 1) * segments + (k + 1) % segments
            F.append((a, c, b))
            F.append((b, c, d))
    # caps
    V = np.vstack([V, P[0][None, :], P[-1][None, :]])
    s0, s1 = len(V) - 2, len(V) - 1
    for k in range(segments):
        F.append((s0, (k + 1) % segments, k))
        F.append((s1, (n - 1) * segments + k, (n - 1) * segments + (k + 1) % segments))
    return V, np.array(F, dtype=np.uint32)


def icosphere(centre, radius):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radius)
    V = np.array([[v.co.x + centre[0], v.co.y + centre[1], v.co.z + centre[2]] for v in bm.verts])
    F = np.array([[v.index for v in f.verts] for f in bm.faces], dtype=np.uint32)
    bm.free()
    return V, F


def smooth_polyline(P, samples_per_span=6):
    """Catmull-Rom through the points, sampled evenly per span."""
    P = np.asarray(P, dtype=np.float64)
    ext_ = np.vstack([P[0] + (P[0] - P[1]), P, P[-1] + (P[-1] - P[-2])])
    out = []
    for i in range(1, len(ext_) - 2):
        p0, p1, p2, p3 = ext_[i - 1], ext_[i], ext_[i + 1], ext_[i + 2]
        for k in range(samples_per_span):
            t = k / samples_per_span
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(P[-1])
    return np.array(out)


# ------------------------------------------------------------ chunk writer

class Chunk:
    def __init__(self):
        self.segments, self.bytes = [], 0

    def append(self, arr):
        pad = (4 - self.bytes % 4) % 4
        if pad:
            self.segments.append(b"\0" * pad)
            self.bytes += pad
        off = self.bytes
        b = np.ascontiguousarray(arr).tobytes()
        self.segments.append(b)
        self.bytes += len(b)
        return off

    def write(self, path):
        with open(path, "wb") as f:
            for s in self.segments:
                f.write(s)
        return self.bytes


# ---------------------------------------------------------------- blender

def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path, import_shading="NORMALS")
    return [o for o in bpy.data.objects if o not in before]


def extra(ob, key, default=None):
    o = ob
    while o is not None:
        if key in o.keys():
            return o[key]
        o = o.parent
    return default


def object_geometry(ob):
    me = ob.data
    me.calc_loop_triangles()
    n = len(me.vertices)
    V = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    V = V @ M[:3, :3].T + M[:3, 3]
    F = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", F)
    return V, F.reshape(-1, 3).astype(np.uint32)


def clear_objects(objs):
    for o in objs:
        me = o.data if o.type == "MESH" else None
        bpy.data.objects.remove(o)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    for m in list(bpy.data.materials):
        if m.users == 0:
            bpy.data.materials.remove(m)


def material_base(ob):
    m = ob.active_material.name if ob.active_material else ""
    return re.sub(r"\.\d+$", "", m)


# ------------------------------------------------------------------ main

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True)
    ap.add_argument("--glb", required=True)
    ap.add_argument("--nerves", required=True)
    ap.add_argument("--join", required=True)
    ap.add_argument("--anatomy", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--render", default=None)
    args = ap.parse_args(argv)
    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)

    # ---- inputs
    atlas, chunks, bp_parts = FIT.load_atlas(args.atlas)
    fitrec = json.load(open(os.path.join(ROOT, "bp3d-fit.json"), encoding="utf-8"))
    fit = FIT.Fit.from_record(fitrec)
    join = json.load(open(args.join, encoding="utf-8"))
    anatomy = {s["id"]: s for s in json.load(open(args.anatomy, encoding="utf-8"))}
    claims = {}          # sourceName -> [structure ids]
    fascial_claim = set()
    for s in join["structures"]:
        for name in s.get("meshes", []) + s.get("insertions", []):
            claims.setdefault(name, []).append(s["id"])
            if anatomy.get(s["id"], {}).get("system") == "fascial":
                fascial_claim.add(name)

    # Blender's glTF importer converts to Z-up on import, so every mesh read
    # from our .glb files arrives in the Z-Anatomy frame the fit is written
    # in. Geometry is fitted there and converted to the BP3D frame once, on the
    # way out; the BP3D bones, read from the chunks, are in their own frame
    # throughout.
    def allowed_for(home):
        return {home} | set(NEIGHBOURS.get(home, []))

    def T(P, home):                 # Z-Anatomy frame -> fitted, BP3D frame; blended from home and its neighbours
        return FIT.za_to_bp3d(fit(np.asarray(P, dtype=np.float64), allowed=allowed_for(home)))

    def region_of(P, allowed=None):  # P in the Z-Anatomy frame
        w = fit.weights(np.asarray(P, dtype=np.float64))
        ids = [r for r in w if allowed is None or r in allowed]
        W = np.stack([w[r] for r in ids], axis=1)
        return [ids[i] for i in W.argmax(axis=1)]

    # ---- BP3D bone surface
    log("building the BP3D bone surface")
    bone_verts, bone_faces, bone_face_part = [], [], []
    base = 0
    for p in atlas["parts"]:
        if p["system"] != "skeletal":
            continue
        b = chunks[p["chunk"]]
        pos = np.frombuffer(b, dtype=np.float32, count=p["vertexCount"] * 3, offset=p["positions"]).reshape(-1, 3)
        idx = np.frombuffer(b, dtype=np.uint32, count=p["indexCount"], offset=p["indices"]).reshape(-1, 3)
        bone_verts.append(pos.astype(np.float64))
        bone_faces.append(idx.astype(np.int64) + base)
        bone_face_part.extend([p["name"]] * len(idx))
        base += len(pos)
    BV = np.vstack(bone_verts)
    BF = np.vstack(bone_faces)
    bvh = BVHTree.FromPolygons([tuple(v) for v in BV], [tuple(int(i) for i in f) for f in BF])
    log("bone surface: %d parts, %d triangles" % (len(bone_verts), len(BF)))

    def nearest_bone(p):
        loc, nrm, idx, dist = bvh.find_nearest(Vector(p))
        return np.array(loc), np.array(nrm), bone_face_part[idx], dist

    # ---- collect our meshes
    meshes = []        # dicts: name, side, system, region(home or None), V (fitted), F, material, extras

    def add_mesh(name, V, F, system, material="", home=None, side=None, authored=False, extras=None):
        if side is None:
            side = name[-1] if re.search(r"\.[lr]$", name) else ""
        meshes.append(dict(name=name, side=side, system=system, material=material, home=home,
                           V=V, F=F, authored=authored, extras=extras or {}))

    zbone_verts, zbone_faces, zbase = [], [], 0      # Z-Anatomy's own bones: which bone a patch sits on, and whether it sits on one
    zbone_face_name = []
    for region in REGIONS:
        path = os.path.join(args.glb, region + ".glb")
        log("importing " + path)
        objs = import_glb(path)
        kept = 0
        for ob in objs:
            if ob.type != "MESH" or extra(ob, "context", False):
                continue
            name = extra(ob, "sourceName")
            system = extra(ob, "system")
            if not name:
                continue
            mat = material_base(ob)
            if system == "skeletal":
                V, F = object_geometry(ob)
                zbone_verts.append(V)
                zbone_faces.append(F.astype(np.int64) + zbase)
                zbone_face_name.extend([name] * len(F))
                zbase += len(V)
                continue
            if system == "articular":
                target = "ligaments"
            elif system == "muscular" and (mat in FASCIA_MATERIALS or name in fascial_claim):
                target = "fascia"
            else:
                continue
            V, F = object_geometry(ob)
            add_mesh(name, V, F, target, material=mat, home=extra(ob, "region"), side=extra(ob, "side"))
            kept += 1
        log("  %s: kept %d of %d objects" % (region, kept, len(objs)))
        clear_objects(objs)
        path = os.path.join(args.glb, region + "-insertions.glb")
        objs = import_glb(path)
        kept = 0
        for ob in objs:
            if ob.type != "MESH":
                continue
            name = extra(ob, "sourceName")
            if not name:
                continue
            V, F = object_geometry(ob)
            add_mesh(name, V, F, "insertions", material=material_base(ob), home=extra(ob, "region"), side=extra(ob, "side"))
            kept += 1
        log("  %s insertions: %d" % (region, kept))
        clear_objects(objs)

    objs = import_glb(args.nerves)
    for ob in objs:
        if ob.type != "MESH":
            continue
        name = ob.name if not ob.parent else ob.parent.name
        name = re.sub(r"\.\d+$", "", name)
        V, F = object_geometry(ob)
        nid = re.sub(r"\.[lr]$", "", name)
        add_mesh(name, V, F, "central-nerves" if nid in CENTRAL_NERVES else "peripheral-nerves",
                 material="Nerve", authored=True, extras=dict(source="schematic"))
    log("nerves: %d objects" % sum(1 for m in meshes if m["system"].endswith("nerves")))
    clear_objects(objs)

    ZV = np.vstack(zbone_verts)
    ZF = np.vstack(zbone_faces)
    zbvh = BVHTree.FromPolygons([tuple(v) for v in ZV], [tuple(int(i) for i in f) for f in ZF])
    log("Z-Anatomy bone surface: %d triangles" % len(ZF))

    # A patch is projected onto the BP3D bone of the same name as the Z-Anatomy bone it sits on -
    # an insertion stays on its bone - and only onto the nearest bone when the name does not resolve.
    bp_skeletal = [p for p in atlas["parts"] if p["system"] == "skeletal"]
    bp_by_norm = {}
    for p in bp_skeletal:
        bp_by_norm.setdefault(FIT_norm(p["name"]), []).append(p)
    part_bvh = {}

    def bvh_of(part):
        if part["name"] not in part_bvh:
            b = chunks[part["chunk"]]
            pos = np.frombuffer(b, dtype=np.float32, count=part["vertexCount"] * 3, offset=part["positions"]).reshape(-1, 3)
            idx = np.frombuffer(b, dtype=np.uint32, count=part["indexCount"], offset=part["indices"]).reshape(-1, 3)
            part_bvh[part["name"]] = BVHTree.FromPolygons([tuple(v) for v in pos.astype(np.float64)],
                                                          [tuple(int(i) for i in f) for f in idx])
        return part_bvh[part["name"]]

    ORDINAL = {"C": "cervical", "T": "thoracic", "L": "lumbar"}
    ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"]
    FINGERS = {"first": "thumb", "second": "index finger", "third": "middle finger", "fourth": "ring finger", "fifth": "little finger"}
    TOES = {"first": "big toe", "second": "second toe", "third": "third toe", "fourth": "fourth toe", "fifth": "little toe"}

    def za_bone_aliases(base):
        """Z-Anatomy's bone name in BodyParts3D's words. Vertebra T10 is the tenth thoracic vertebra,
        the fifth finger of the foot is the little toe, the triquetrum is triquetral."""
        out = [base, re.sub(r"\bbone\b", "", base), re.sub(r"^Costal cartilage of (\w+) rib$", r"\1 costal cartilage", base)]
        m = re.match(r"^Vertebra ([CTL])(\d+)$", base)
        if m:
            out.append("%s %s vertebra" % (ORDINALS[int(m.group(2)) - 1], ORDINAL[m.group(1)]))
        m = re.match(r"^(Distal|Middle|Proximal) phalanx of (\w+) finger of (hand|foot)$", base)
        if m:
            digit = (FINGERS if m.group(3) == "hand" else TOES).get(m.group(2))
            if digit:
                out.append("%s phalanx of %s" % (m.group(1), digit))
        out += {"Atlas (C1)": ["Atlas"], "Axis (C2)": ["Axis"], "Manubrium of sternum": ["Manubrium"],
                "Triquetrum bone": ["Triquetral"], "Sesamoid bones of foot": ["Sesamoid bone of foot"]}.get(base, [])
        return out

    def bp3d_bone_for(source_bone, side):
        """The BP3D skeletal part carrying the same bone as a Z-Anatomy bone name, on the same side."""
        base = re.sub(r"\.[lr]$", "", source_bone)
        sided = bool(re.search(r"\.[lr]$", source_bone))
        cands = []
        for alias in za_bone_aliases(base):
            cands += bp_by_norm.get(FIT_norm(alias), [])
        if not cands:
            return None
        if sided:
            want = {"l": "left", "r": "right"}[side or source_bone[-1]]
            sided_c = [c for c in cands if want in c["name"].lower()]
            return sided_c[0] if sided_c else None
        unsided = [c for c in cands if "left" not in c["name"].lower() and "right" not in c["name"].lower()]
        return unsided[0] if unsided else cands[0]

    # ---- transform
    log("transforming %d meshes" % len(meshes))
    probe = next((m for m in meshes if m["name"] == "Anterior cruciate ligament.l"), None)
    if probe is not None:
        log("frame check: ACL.l centroid in the Z-Anatomy frame = %s (expect x~0.09, y~0.02, z~0.43)"
            % np.round(probe["V"].mean(axis=0), 3).tolist())
    for m in meshes:
        m["V0"] = m["V"]            # Z-Anatomy frame, as imported
        if not m["home"]:           # the nerves carry no region: the fit's weights at the centroid decide
            m["home"] = region_of(m["V0"].mean(axis=0)[None, :])[0]
        m["V"] = T(m["V"], m["home"])   # BP3D frame, fitted

    # ---- project insertions: those that sit on bone in the source go onto BP3D bone; the
    # ones that attach to soft tissue there (an aponeurosis, a fascia) are left where the fit puts them
    log("projecting insertions")
    proj_rows = []
    for m in meshes:
        if m["system"] != "insertions":
            continue
        hits = [zbvh.find_nearest(Vector(v)) for v in m["V0"]]
        d0 = np.array([h[3] for h in hits])
        on_bone = bool(d0.mean() < 0.004)
        src_names = {}
        for h in hits:
            n = zbone_face_name[h[2]]
            src_names[n] = src_names.get(n, 0) + 1
        source_bone = max(src_names, key=src_names.get)
        m["extras"]["sourceBone"] = source_bone
        m["extras"]["sourceBoneDistance"] = round(float(d0.mean()), 5)
        m["extras"]["onBone"] = on_bone
        if not on_bone:
            m["extras"]["projection"] = None
            proj_rows.append(dict(name=m["name"], projected=False, sourceBone=source_bone, sourceBoneDistance=float(d0.mean()),
                                  mean=0.0, max=0.0, bone=None, matched=False, bones=0))
            continue
        # the side comes from the bone the patch sits on, not from the name: some insertion names end
        # in .l while their geometry lies on the right bone (recorded below as sideMismatch)
        bone_side = source_bone[-1] if re.search(r"\.[lr]$", source_bone) else None
        m["extras"]["geometrySide"] = bone_side or ""
        side_mismatch = bool(bone_side and m["side"] and bone_side != m["side"])
        m["extras"]["sideMismatch"] = side_mismatch
        target = bp3d_bone_for(source_bone, bone_side)
        if target is None:
            # the bone the patch sits on has no BP3D counterpart (the eighth and tenth costal
            # cartilages): pulling it to the nearest other bone would be a wrong attachment
            m["extras"]["projection"] = None
            m["extras"]["projectionSkipped"] = "no BP3D bone for " + source_bone
            proj_rows.append(dict(name=m["name"], projected=False, sourceBone=source_bone, sourceBoneDistance=float(d0.mean()),
                                  mean=0.0, max=0.0, bone=None, matched=False, bones=0, reason="bone absent in BP3D"))
            continue
        V = m["V"]
        moved = np.zeros(len(V))
        bones = {}
        out = np.empty_like(V)
        for i, v in enumerate(V):
            if target is not None:
                loc, nrm, _idx, dist = bvh_of(target).find_nearest(Vector(v))
                loc, nrm = np.array(loc), np.array(nrm)
                part = target["name"]
            else:
                loc, nrm, part, dist = nearest_bone(v)
            moved[i] = dist
            bones[part] = bones.get(part, 0) + 1
            d = v - loc
            dn = np.linalg.norm(d)
            direction = d / dn if dn > 1e-9 else nrm
            out[i] = loc + direction * INSERTION_LIFT
        m["V"] = out
        bone = max(bones, key=bones.get)
        m["extras"].update(projection=dict(mean=round(float(moved.mean()), 5), max=round(float(moved.max()), 5),
                                           bone=bone, boneMatched=target is not None, bones=len(bones)))
        proj_rows.append(dict(name=m["name"], projected=True, sourceBone=source_bone, sourceBoneDistance=float(d0.mean()),
                              mean=float(moved.mean()), max=float(moved.max()), bone=bone, matched=target is not None,
                              bones=len(bones), sideMismatch=side_mismatch))

    # ---- landmarks
    log("landmarks")
    lm_by_id = {}
    for r in fitrec["landmarks"]:
        lm_by_id.setdefault(r["id"], []).append(r)
    zl = json.load(open(os.path.join(ROOT, "landmarks.json"), encoding="utf-8"))
    zl_by_id = {x["id"]: x for x in zl["landmarks"]}
    landmark_rows = []
    for lid, sides in lm_by_id.items():
        worst = max(s["residualBlended"] for s in sides)
        conf = "low" if worst > LOW_CONFIDENCE else "high"
        spec = zl_by_id[lid]
        region = LANDMARK_REGION_BY_ID.get(lid, LANDMARK_REGION[spec["region"]])
        for s in sides:
            p = FIT.za_to_bp3d(np.array(s["bp3d"], dtype=np.float64))
            loc, nrm, part, dist = nearest_bone(p)
            V, F = icosphere(p, LANDMARK_RADIUS)
            side = s["side"] if s["side"] != "m" else ""
            name = spec["name"] + ({"l": " (left)", "r": " (right)"}.get(s["side"], ""))
            meshes.append(dict(name=lid + ("." + side if side else ""), display=name, side=side, system="landmarks",
                               material="Landmark", home=region, V=V, F=F, authored=False,
                               extras=dict(landmark=lid, fitConfidence=conf, fitResidual=round(worst, 5),
                                           fitResidualSide=round(s["residualBlended"], 5), surfaceDistance=round(dist, 5),
                                           bone=part, target=spec["target"]),
                               concept=lid))
            landmark_rows.append(dict(id=lid, side=s["side"], residual=s["residualBlended"], confidence=conf,
                                      surfaceDistance=dist, bone=part))

    # ---- schematic spinal cord through the BP3D canal
    log("authoring the schematic spinal cord")
    order = (["Atlas", "Axis"] + ["%s cervical vertebra" % n for n in ("Third", "Fourth", "Fifth", "Sixth", "Seventh")]
             + ["%s thoracic vertebra" % n for n in ("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
                                                     "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth")]
             + ["%s lumbar vertebra" % n for n in ("First", "Second", "Third", "Fourth", "Fifth")])

    def canal_centre(name, y=None, xband=0.004, min_gap=0.006):
        p = bp_parts[name.lower()]
        V = FIT.part_vertices(p, chunks)
        lo, hi = V.min(axis=0), V.max(axis=0)
        ym = (lo[1] + hi[1]) / 2 if y is None else y
        for band in (0.004, 0.008, 0.012):
            s = V[(abs(V[:, 0]) < xband + band) & (abs(V[:, 1] - ym) < band)]
            if len(s) < 6:
                continue
            z = np.sort(s[:, 2])
            gaps = z[1:] - z[:-1]
            k = int(gaps.argmax())
            if gaps[k] >= min_gap:
                return np.array([0.0, ym, (z[k] + z[k + 1]) / 2]), float(gaps[k])
        raise ValueError("no canal gap found in " + name)

    canal = []
    canal_report = []
    for name in order:
        c, gap = canal_centre(name)
        canal.append(c)
        canal_report.append(dict(vertebra=name, centre=[round(float(x), 4) for x in c], gapWidth=round(gap, 4)))
    canal = np.array(canal)
    # foramen magnum: above the atlas canal, curving forward into the brainstem
    fm = canal[0] + np.array([0.0, 0.020, 0.006])
    # levels: cervical = fm..C7, thoracic = T1..T12, lumbar = L1 (conus at its mid-height)
    cord_pts = np.vstack([fm[None, :], canal[:20]])          # fm, C1..C7 (7), T1..T12 (12) = 20 vertebrae -> L1 is index 19
    cord = smooth_polyline(cord_pts, 8)
    y_c7t1 = (canal[6][1] + canal[7][1]) / 2
    y_t12l1 = (canal[18][1] + canal[19][1]) / 2
    segments = {"cervical": cord[cord[:, 1] >= y_c7t1 - 1e-9], "thoracic": cord[(cord[:, 1] < y_c7t1) & (cord[:, 1] >= y_t12l1)],
                "lumbar": cord[cord[:, 1] < y_t12l1]}
    # overlap one sample so the segments meet
    keys = ["cervical", "thoracic", "lumbar"]
    for a, b in zip(keys, keys[1:]):
        if len(segments[a]) and len(segments[b]):
            segments[b] = np.vstack([segments[a][-1][None, :], segments[b]])
    for rid, pts in segments.items():
        if len(pts) < 2:
            continue
        V, F = tube(pts, 0.005)
        meshes.append(dict(name="Spinal cord (schematic) %s" % rid, side="", system="central-nerves", material="Nerve",
                           home=rid, V=V, F=F, authored=True, extras=dict(source="schematic", segment=rid),
                           concept="nerve-spinal-cord", display="Spinal cord"))
    # cauda equina: six strands from the conus, spreading across the canal, staggered ends L5 / S1 / S2
    sac = bp_parts["sacrum"]
    SV = FIT.part_vertices(sac, chunks)
    s_top = SV[:, 1].max()
    s1, _ = canal_centre("Sacrum", y=s_top - 0.020, min_gap=0.004)
    s2, _ = canal_centre("Sacrum", y=s_top - 0.050, min_gap=0.003)
    conus = canal[19]
    lower = [canal[20], canal[21], canal[22], canal[23], s1, s2]       # L2..L5, S1, S2
    offsets = [(-0.004, -0.002), (0.004, -0.002), (-0.002, 0.003), (0.002, 0.003), (-0.005, 0.001), (0.005, 0.001)]
    ends = [5, 5, 4, 4, 3, 3]
    for k, ((dx, dz), end) in enumerate(zip(offsets, ends)):
        pts = [conus]
        for i, c in enumerate(lower[:end + 1]):
            f = min(1.0, (i + 1) / 2.0)
            pts.append(c + np.array([dx * f, 0.0, dz * f]))
        V, F = tube(smooth_polyline(np.array(pts), 6), 0.0012, segments=8)
        meshes.append(dict(name="Cauda equina (schematic) strand %d" % (k + 1), side="", system="central-nerves",
                           material="Nerve", home="lumbar", V=V, F=F, authored=True,
                           extras=dict(source="schematic", strand=k + 1), concept="nerve-cauda-equina",
                           display="Cauda equina"))

    # ---- regions, spanning, seam check
    log("regions and seams")
    seam = {}
    for m in meshes:
        if "V0" not in m:           # landmarks and the cord are authored in the BP3D frame
            m["V0"] = FIT.bp3d_to_za(m["V"])
        dom = region_of(m["V0"], allowed_for(m["home"]))
        counts = {}
        for r in dom:
            counts[r] = counts.get(r, 0) + 1
        m["regions"] = sorted(counts, key=counts.get, reverse=True)
        m["home"] = m["home"] or m["regions"][0]
        if m["home"] not in counts:
            counts[m["home"]] = 0
        m["spans"] = [r for r in m["regions"] if r != m["home"] and counts[r] >= 0.05 * len(dom)]
        # seam: residual displacement per vertex, compared along edges that cross a region boundary
        if any(k.lower() in m["name"].lower() for k in SEAM_STRUCTURES) and len(m["spans"]):
            za0 = m["V0"]
            G = FIT.apply_sim(fit.glob, za0)
            D = fit(za0, allowed=allowed_for(m["home"])) - G
            F = m["F"]
            dom = np.array(dom)
            for e in ((0, 1), (1, 2), (2, 0)):
                a, b = F[:, e[0]], F[:, e[1]]
                cross = dom[a] != dom[b]
                if not cross.any():
                    continue
                dd = np.linalg.norm(D[a[cross]] - D[b[cross]], axis=1)
                ln = np.linalg.norm(za0[a[cross]] - za0[b[cross]], axis=1)
                for i in np.nonzero(cross)[0]:
                    pass
                pairs = ["|".join(sorted((dom[x], dom[y]))) for x, y in zip(a[cross], b[cross])]
                for pair, d1, l1 in zip(pairs, dd, ln):
                    rec = seam.setdefault(pair, {}).setdefault(m["name"], dict(edges=0, maxDelta=0.0, maxDeltaPerCm=0.0))
                    rec["edges"] += 1
                    rec["maxDelta"] = max(rec["maxDelta"], float(d1))
                    if l1 > 1e-6:
                        rec["maxDeltaPerCm"] = max(rec["maxDeltaPerCm"], float(d1 / l1 * 0.01))

    # ---- write chunks, one per region
    log("writing chunks")
    out_chunks, out_parts, region_table = [], [], {}
    concept_elems = {}       # concept id -> [part ids]
    concept_names = {}
    fma_by_name = {}
    for c in atlas["concepts"]:
        fma_by_name.setdefault(FIT_norm(c["name"]), c["id"])
    counters = {}
    for ri, rid in enumerate(REGIONS):
        ch = Chunk()
        members = [m for m in meshes if m["home"] == rid]
        tris = 0
        for m in members:
            V = m["V"].astype(np.float32)
            N = np.clip(np.round(vertex_normals(m["V"], m["F"]) * 32767), -32767, 32767).astype(np.int16)
            F = m["F"].astype(np.uint32)
            po, no, io = ch.append(V), ch.append(N), ch.append(F)
            base_name = re.sub(r"\.[lr]$", "", m["name"])
            key = slug(m["name"])
            counters[key] = counters.get(key, 0) + 1
            pid = ("LM-" if m["system"] == "landmarks" else "SC-" if m["authored"] and m.get("concept") else
                   "NV-" if m["authored"] else "ZA-") + key + ("-%d" % counters[key] if counters[key] > 1 else "")
            struct_ids = claims.get(m["name"], [])
            group = m.get("concept") or ("ZA-" + slug(base_name))
            fma = fma_by_name.get(FIT_norm(base_name))
            concept_id = fma or (struct_ids[0] if struct_ids else group)
            display = m.get("display") or base_name + ({"l": " (left)", "r": " (right)"}.get(m["side"], ""))
            rec = dict(id=pid, name=display, conceptId=concept_id, system=m["system"], chunk=ri,
                       positions=po, normals=no, indices=io, vertexCount=int(len(V)), indexCount=int(len(F) * 3),
                       bounds=[[float(x) for x in m["V"].min(axis=0)], [float(x) for x in m["V"].max(axis=0)]],
                       region=rid, regions=m["regions"], spans=m["spans"], side=m["side"],
                       source="schematic" if m["authored"] else "zanatomy", sourceName=m["name"], material=m["material"],
                       structures=struct_ids, fma=fma, authored=bool(m["authored"]))
            rec.update(m["extras"])
            out_parts.append(rec)
            tris += len(F)
            # concepts: the l/r group, every claiming MVMT structure, the FMA concept
            for cid, cname in [(group, m.get("display") or base_name)] + [(s, anatomy[s]["name"] if s in anatomy else s) for s in struct_ids] \
                    + ([(fma, next(c["name"] for c in atlas["concepts"] if c["id"] == fma))] if fma else []):
                concept_elems.setdefault(cid, []).append(pid)
                concept_names.setdefault(cid, cname)
        file = "mvmt-%s.bin" % rid
        size = ch.write(os.path.join(args.out, file))
        out_chunks.append(dict(url="/models/" + file, bytes=size, region=rid, triangles=tris, parts=len(members)))
        region_table[rid] = dict(id=rid, name=REGION_NAMES[rid], chunk=ri, parts=len(members), triangles=tris, bytes=size,
                                 bounds=None, spanningParts=[])
        log("  %s: %d parts, %d triangles, %d bytes" % (rid, len(members), tris, size))
    for p in out_parts:
        for r in p["spans"]:
            region_table[r]["spanningParts"].append(p["id"])
        rt = region_table[p["region"]]
        b = p["bounds"]
        rt["bounds"] = b if rt["bounds"] is None else [[min(a, c) for a, c in zip(rt["bounds"][0], b[0])],
                                                        [max(a, c) for a, c in zip(rt["bounds"][1], b[1])]]
    concepts = [dict(id=cid, name=concept_names[cid], elements=sorted(set(els)),
                     source="mvmt" if cid in anatomy else "fma" if cid.startswith("FMA") else "landmark" if cid.startswith("lm-") else "mvmt-atlas")
                for cid, els in concept_elems.items()]

    # ---- report
    n_ins = len(proj_rows)
    projected = [r for r in proj_rows if r["projected"]]
    soft = [r for r in proj_rows if not r["projected"] and not r.get("reason")]
    absent = [r for r in proj_rows if r.get("reason")]
    over_mean = sum(1 for r in projected if r["mean"] > PROJECTION_FLAG)
    over_max = sum(1 for r in projected if r["max"] > PROJECTION_FLAG)
    multi = sum(1 for r in projected if r["bones"] > 1)
    matched = sum(1 for r in projected if r["matched"])
    unmatched_bones = sorted(set(r["sourceBone"] for r in projected if not r["matched"]))
    side_mismatches = sorted(r["name"] for r in projected if r.get("sideMismatch"))
    report = dict(
        meshes=len(meshes), parts=len(out_parts), concepts=len(concepts),
        bySystem={s: dict(parts=sum(1 for p in out_parts if p["system"] == s),
                          triangles=sum(p["indexCount"] // 3 for p in out_parts if p["system"] == s)) for s in
                  sorted(set(p["system"] for p in out_parts))},
        insertions=dict(patches=n_ins, onBoneInSource=len(projected), softTissueInSource=len(soft),
                        projectedOntoSameBone=matched, projectedOntoNearestBone=len(projected) - matched,
                        sourceBonesWithoutBp3dMatch=unmatched_bones,
                        boneAbsentInBp3d=[dict(name=r["name"], sourceBone=r["sourceBone"]) for r in absent],
                        sideMismatches=dict(count=len(side_mismatches), names=side_mismatches,
                                            note="insertion names whose .l/.r disagrees with the side of the Z-Anatomy bone the patch sits on; the geometry's side is used"),
                        movedOver5mmMean=over_mean, movedOver5mmMax=over_max, spanningTwoBones=multi,
                        meanOfMeans=round(float(np.mean([r["mean"] for r in projected])), 5) if projected else None,
                        medianOfMeans=round(float(np.median([r["mean"] for r in projected])), 5) if projected else None,
                        worst=sorted(projected, key=lambda r: -r["mean"])[:15],
                        softTissue=sorted(soft, key=lambda r: -r["sourceBoneDistance"])),
        landmarks=dict(count=len(landmark_rows), low=sorted(set(r["id"] for r in landmark_rows if r["confidence"] == "low")),
                       surfaceDistance=dict(min=round(min(r["surfaceDistance"] for r in landmark_rows), 5),
                                            max=round(max(r["surfaceDistance"] for r in landmark_rows), 5))),
        spinalCord=dict(canal=canal_report, foramenMagnum=[round(float(x), 4) for x in fm],
                        conus=[round(float(x), 4) for x in conus], s2=[round(float(x), 4) for x in s2]),
        seams={pair: {name: dict(edges=v["edges"], maxDeltaMm=round(v["maxDelta"] * 1000, 3),
                                 maxDeltaMmPerCm=round(v["maxDeltaPerCm"] * 1000, 3)) for name, v in names.items()}
               for pair, names in seam.items()},
        seamMaxMm=round(max((v["maxDelta"] for names in seam.values() for v in names.values()), default=0.0) * 1000, 3),
        seconds=round(time.time() - t0, 1),
    )
    layers = dict(version=1, generatedFrom="mvmt-anatomy tools/bp3d_export.py", fit="bp3d-fit.json",
                  units="metres", up="Y", frame="+X left, +Z anterior (BodyParts3D)",
                  systems=dict(fascia="Fascia", ligaments="Joints & ligaments", insertions="Insertions",
                               **{"peripheral-nerves": "Peripheral nerves", "central-nerves": "Central nerves"},
                               landmarks="Landmarks"),
                  chunks=out_chunks, parts=out_parts, concepts=concepts, regions=[region_table[r] for r in REGIONS],
                  report=report)
    with open(os.path.join(args.out, "mvmt-layers.json"), "w", encoding="utf-8") as f:
        json.dump(layers, f)
    rec = dict(k for k in layers.items() if k[0] not in ("parts", "concepts"))
    rec["parts"] = len(out_parts)
    rec["concepts"] = len(concepts)
    with open(os.path.join(ROOT, "bp3d-export.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    log("insertions: %d patches, %d on bone in the source and projected (%d onto the same-named BP3D bone, %d onto the nearest; "
        "%d moved > 5 mm by mean, %d by max), %d on soft tissue and left to the fit, %d on a bone BP3D lacks and left to the fit (%s)"
        % (n_ins, len(projected), matched, len(projected) - matched, over_mean, over_max, len(soft), len(absent),
           ", ".join(sorted(set(r["sourceBone"] for r in absent))) or "none"))
    log("insertion names whose side disagrees with their geometry: %d" % len(side_mismatches))
    log("seam max delta %.3f mm" % report["seamMaxMm"])

    if args.render:
        render(args.render, meshes, atlas, chunks, region_table)
    log("done in %.0f s" % (time.time() - t0))
    print("BP3D_EXPORT_OK parts=%d" % len(out_parts))


def FIT_norm(s):
    """The name normalisation of CLAUDE.md: content words as a set, colli = cervicis."""
    s = re.sub(r"\.[lr]$", "", s.lower()).replace("(", "").replace(")", "")
    s = re.sub(r"\bcolli\b", "cervicis", s)
    drop = {"muscle", "of", "part", "the", "bone", "left", "right", "and"}
    return " ".join(sorted(w for w in re.split(r"[^a-z0-9-]+", s) if w and w not in drop))


# ---------------------------------------------------------------- render

COLOURS = {"bone": (0.93, 0.90, 0.83, 1), "ligaments": (0.71, 0.76, 0.80, 1), "insertions": (0.56, 0.23, 0.18, 1),
           "fascia": (0.85, 0.81, 0.76, 1), "peripheral-nerves": (0.88, 0.64, 0.15, 1), "central-nerves": (0.88, 0.64, 0.15, 1),
           "landmarks": (0.17, 0.37, 0.62, 1)}


def make_object(name, V, F, colour, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], [tuple(int(i) for i in f) for f in F])
    me.validate()
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.color = colour
    coll.objects.link(ob)
    return ob


def render(outdir, meshes, atlas, chunks, region_table):
    log("rendering to " + outdir)
    os.makedirs(outdir, exist_ok=True)
    scene = bpy.context.scene
    # the factory scene holds a 2 m cube, a light and a camera; the cube hid everything below y = 1 m
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    coll = bpy.data.collections.new("bp3d")
    scene.collection.children.link(coll)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = scene.render.resolution_y = 1600
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new("w") if scene.world is None else scene.world
    scene.world.color = (0.96, 0.94, 0.91)
    bones = []
    for p in atlas["parts"]:
        if p["system"] != "skeletal":
            continue
        b = chunks[p["chunk"]]
        pos = np.frombuffer(b, dtype=np.float32, count=p["vertexCount"] * 3, offset=p["positions"]).reshape(-1, 3)
        idx = np.frombuffer(b, dtype=np.uint32, count=p["indexCount"], offset=p["indices"]).reshape(-1, 3)
        bones.append(make_object("bone " + p["name"], pos, idx, COLOURS["bone"], coll))
    ours = {}
    for m in meshes:
        ob = make_object(m["name"], m["V"], m["F"], COLOURS[m["system"]], coll)
        ours.setdefault(m["system"], []).append(ob)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = "ORTHO"
    coll.objects.link(cam)
    scene.camera = cam

    def show(systems):
        for s, obs in ours.items():
            for ob in obs:
                ob.hide_render = s not in systems

    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (0.96, 0.94, 0.91)

    def shoot(name, centre, size, view):
        # the scene is in the BP3D frame: Y up, +Z anterior, +X left. A camera looks down its own -Z,
        # so the anterior view is the unrotated camera on +Z, and the lateral view turns it about Y.
        d = {"anterior": (0, 0, 1), "lateral": (1, 0, 0), "posterior": (0, 0, -1)}[view]
        cam.location = Vector(centre) + Vector(d) * 3.0
        cam.rotation_euler = {"anterior": (0, 0, 0), "lateral": (0, math.pi / 2, 0), "posterior": (0, math.pi, 0)}[view]
        cam.data.ortho_scale = size
        cam.data.clip_end = 10
        scene.render.filepath = os.path.join(outdir, name + ".png")
        bpy.ops.render.render(write_still=True)

    for rid in ("knee", "hip", "shoulder"):
        b = region_table[rid]["bounds"]
        centre = [(b[0][i] + b[1][i]) / 2 for i in range(3)]
        size = max(b[1][i] - b[0][i] for i in range(3)) * 1.15
        # left side only: shift the centre to the left member for the paired regions
        if rid != "hip":
            left = [m for m in meshes if m["home"] == rid and m["side"] == "l" and m["system"] in ("ligaments", "insertions")]
            if left:
                V = np.vstack([m["V"] for m in left])
                lo, hi = V.min(axis=0), V.max(axis=0)
                centre = [(lo[i] + hi[i]) / 2 for i in range(3)]
                size = max(hi - lo) * 1.2
        show({"ligaments", "insertions"})
        for view in ("anterior", "lateral"):
            shoot("%s-%s" % (rid, view), centre, size, view)
    show({"fascia", "peripheral-nerves", "central-nerves"})
    shoot("body-fascia-nerves-anterior", (0, 0.87, 0), 1.85, "anterior")
    shoot("body-fascia-nerves-lateral", (0, 0.87, 0), 1.85, "lateral")
    show({"landmarks", "ligaments"})
    shoot("body-landmarks-anterior", (0, 0.87, 0), 1.85, "anterior")


if __name__ == "__main__":
    main()
