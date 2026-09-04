"""Verify the exported region assets against the manifest, the assignment CSV
and the inventory - by reading the files back, not by trusting the writer.

    blender -b --factory-startup --python tools/verify_export.py -- \
        [--manifest manifest.json] [--inventory inventory.csv] \
        [--assignment region-assignment.csv] [--no-geometry]

Two layers of checks:

  1. The glTF JSON chunk of every file, parsed directly: node names, extras,
     triangle counts from the index accessors (Draco-compressed primitives
     still declare them), bytes on disk. This is where sourceName is checked
     against the inventory, exactly, for every node.

  2. The decoded geometry, through Blender's importer (which decodes Draco):
     triangle counts agree with the accessors, and winding. Winding is judged
     by signed volume: for every .l/.r pair both volumes must have the same
     sign and agree in magnitude, which a mirror exported inside-out cannot
     satisfy, and every closed mesh must have positive volume, i.e. outward
     normals. Signed volume is used rather than a dot product with the normal
     because, per CLAUDE.md, the normal test silently misreports on these
     meshes.

Prints VERIFY_EXPORT_OK or VERIFY_EXPORT_FAIL with counts and exits non-zero
on any failure.
"""

import argparse
import csv
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import corrections  # noqa: E402
import regions  # noqa: E402
import scope  # noqa: E402

results = []


def check(name, ok, detail):
    results.append((name, bool(ok), detail))
    print("  %-4s %-44s %s" % ("PASS" if ok else "FAIL", name, detail))
    sys.stdout.flush()


BLENDER_SUFFIX = re.compile(r"\.\d{3}$")


def read_glb_json(path):
    with open(path, "rb") as f:
        b = f.read()
    magic, _, _ = struct.unpack("<III", b[:12])
    if magic != 0x46546C67:
        raise ValueError("%s is not a GLB" % path)
    clen, ctype = struct.unpack("<II", b[12:20])
    return json.loads(b[20:20 + clen])


def nodes_of(gltf):
    """[(name, extras, triangles)] for every mesh node."""
    out = []
    for n in gltf["nodes"]:
        if "mesh" not in n:
            continue
        tris = 0
        for pr in gltf["meshes"][n["mesh"]]["primitives"]:
            if "indices" in pr:
                tris += gltf["accessors"][pr["indices"]]["count"] // 3
            else:
                tris += gltf["accessors"][pr["attributes"]["POSITION"]]["count"] // 3
        out.append((n.get("name", ""), n.get("extras", {}), tris,
                    any(k in n for k in ("matrix", "translation", "rotation", "scale"))))
    return out


def signed_volume_and_closed(ob):
    """World-space signed volume and whether the mesh is closed (no boundary
    edges). Computed with bmesh so open sheets are recognised rather than
    silently scored."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    closed = all(not e.is_boundary for e in bm.edges)
    vol = bm.calc_volume(signed=True)
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    bm.free()
    return vol, closed, tris


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="manifest.json")
    ap.add_argument("--inventory", default="inventory.csv")
    ap.add_argument("--assignment", default="region-assignment.csv")
    ap.add_argument("--no-geometry", action="store_true")
    args = ap.parse_args(argv)

    base = os.path.dirname(os.path.abspath(args.manifest))
    manifest = json.load(open(args.manifest, encoding="utf-8"))

    # ---- the independent truth: inventory.csv through the same filters ----
    inv = regions.load_inventory(args.inventory)
    kept, excluded, report = scope.partition(inv)
    inv_names = {r["object_name"] for r in kept}
    inv_tris = {r["object_name"]: int(r["triangles"]) for r in kept}
    inv_system = {r["object_name"]: r["system"] for r in kept}
    print(scope.format_report(report))

    assignment = {r["sourceName"]: r for r in csv.DictReader(open(args.assignment, encoding="utf-8"))}
    check("assignment-covers-inventory", set(assignment) == inv_names,
          "%d in CSV, %d kept in inventory" % (len(assignment), len(inv_names)))
    per_region = Counter(r["region"] for r in assignment.values())
    check("every-region-populated", all(per_region[rg] > 0 for rg in regions.REGIONS),
          " ".join("%s=%d" % (rg, per_region[rg]) for rg in regions.REGIONS))

    # ---- manifest join table ------------------------------------------------
    objs = {o["sourceName"]: o for o in manifest["objects"]}
    check("manifest-objects-match-inventory", set(objs) == inv_names and len(manifest["objects"]) == len(inv_names),
          "%d objects" % len(objs))
    check("manifest-objects-match-assignment",
          all(objs[n]["region"] == assignment[n]["region"] and objs[n]["side"] == assignment[n]["side"]
              and objs[n]["system"] == assignment[n]["system"] for n in objs if n in assignment),
          "region, side and system agree for every object")
    check("manifest-inventory-triangles-match-inventory",
          all(objs[n]["inventoryTriangles"] == inv_tris[n] for n in objs),
          "objects[].inventoryTriangles is the base-mesh count from inventory.csv")
    modified = sum(1 for o in objs.values() if o["sourceTriangles"] != o["inventoryTriangles"])
    check("insertions-are-base-meshes",
          all(o["sourceTriangles"] == o["inventoryTriangles"] for o in objs.values() if o["system"] == "insertion"),
          "%d non-insertion objects exported from their evaluated (modifier-applied) mesh" % modified)

    # ---- side counts per region -----------------------------------------------
    unpaired = sorted(n for n in inv_names if scope.twin_of(n) and scope.twin_of(n) not in inv_names)
    side_msgs = []
    for rg in regions.REGIONS:
        l = sum(1 for n, a in assignment.items() if a["region"] == rg and a["side"] == "l")
        r = sum(1 for n, a in assignment.items() if a["region"] == rg and a["side"] == "r")
        u = [n for n in unpaired if assignment[n]["region"] == rg]
        ul = sum(1 for n in u if scope.side_of(n) == "l")
        ur = len(u) - ul
        if l - ul != r - ur:
            side_msgs.append("%s l=%d r=%d unexplained" % (rg, l, r))
    check("sides-match-per-region-after-unpaired", not side_msgs,
          "%d upstream-unpaired objects explain every difference" % len(unpaired)
          if not side_msgs else "; ".join(side_msgs))
    for n in unpaired:
        print("       unpaired upstream: %-48s %s" % (n, assignment[n]["region"]))

    # ---- every file, JSON chunk ----------------------------------------------------
    files = []
    if manifest.get("overview"):
        files.append(("overview", manifest["overview"]["file"], manifest["overview"]))
    for r in manifest["regions"]:
        files.append((r["id"], r["file"], r))
        files.append((r["id"] + "-insertions", r["insertionLayer"]["file"], r["insertionLayer"]))

    all_names_ok = True
    bad_names = []
    bad_corrected = []                   # (file, name, extras) with the wrong corrected/source extras
    corrected_seen = defaultdict(set)    # name -> files it appeared in
    corrections_rec = None
    cpath = os.path.join(base, "corrections.json")
    if os.path.exists(cpath):
        corrections_rec = {o["object"]: o for o in json.load(open(cpath, encoding="utf-8"))["objects"]}
    seen_in_file = defaultdict(set)      # region -> non-context sourceNames
    exported_tris = {}                   # (file, name) -> tris
    for label, fname, rec in files:
        path = os.path.join(base, fname)
        if not os.path.exists(path):
            check("file-exists:" + fname, False, "missing")
            continue
        size = os.path.getsize(path)
        check("bytes:" + fname, size == rec["bytes"], "%d on disk, %d in manifest" % (size, rec["bytes"]))
        g = read_glb_json(path)
        nodes = nodes_of(g)
        names = [n for n, _, _, _ in nodes]
        dup = [n for n, c in Counter(names).items() if c > 1]
        total = sum(t for _, _, t, _ in nodes)
        check("triangles:" + fname, total == rec["triangles"],
              "%d from index accessors, %d in manifest" % (total, rec["triangles"]))
        check("draco:" + fname, "KHR_draco_mesh_compression" in g.get("extensionsRequired", []),
              "extensionsRequired=%s" % g.get("extensionsRequired"))
        check("identity-transforms:" + fname, not any(tr for _, _, _, tr in nodes),
              "%d nodes carry a transform" % sum(1 for _, _, _, tr in nodes if tr))
        for n, ex, t, _ in nodes:
            exported_tris[(fname, n)] = t
            ok = (n in inv_names and ex.get("sourceName") == n and not BLENDER_SUFFIX.search(n)
                  and ex.get("system") == inv_system.get(n)
                  and ex.get("side") == scope.side_of(n)
                  and ex.get("region") == assignment.get(n, {}).get("region")
                  and isinstance(ex.get("context"), bool))
            if not ok:
                all_names_ok = False
                bad_names.append((fname, n, ex))
            want = n in corrections.CORRECTED
            has = ex.get("corrected") is True and ex.get("source") == "redrawn"
            if want != has or (not want and ("corrected" in ex or "source" in ex)):
                bad_corrected.append((fname, n, ex))
            if want:
                corrected_seen[n].add(fname)
                if corrections_rec and n in corrections_rec and corrections_rec[n]["triangles"] != t:
                    bad_corrected.append((fname, n, {"triangles": t, "corrections.json": corrections_rec[n]["triangles"]}))
        check("names-and-extras:" + fname, not dup and all(
            (n in inv_names and ex.get("sourceName") == n) for n, ex, _, _ in nodes),
            "%d nodes, %d duplicates" % (len(nodes), len(dup)))
        # membership
        if label == "overview":
            expect = {n for n in inv_names if inv_system[n] != "insertion"}
            got = {n for n, ex, _, _ in nodes}
            check("membership:overview", got == expect and all(ex["context"] is False for _, ex, _, _ in nodes),
                  "%d nodes, expected %d" % (len(got), len(expect)))
        elif label.endswith("-insertions"):
            rg = label[:-len("-insertions")]
            expect = {n for n, a in assignment.items() if a["region"] == rg and a["system"] == "insertion"}
            got = {n for n, ex, _, _ in nodes}
            check("membership:" + fname, got == expect and all(ex["context"] is False for _, ex, _, _ in nodes),
                  "%d nodes, expected %d" % (len(got), len(expect)))
            check("full-resolution:" + fname,
                  all(t == inv_tris[n] for n, _, t, _ in nodes if n in inv_tris),
                  "every insertion at its source triangle count")
        else:
            rg = label
            own = {n for n, ex, _, _ in nodes if ex.get("context") is False}
            ctx = {n for n, ex, _, _ in nodes if ex.get("context") is True}
            expect_own = {n for n, a in assignment.items() if a["region"] == rg and a["system"] != "insertion"}
            expect_ctx = {n for n, a in assignment.items()
                          if a["region"] in regions.NEIGHBOURS[rg] and a["system"] != "insertion"}
            check("membership:" + fname, own == expect_own and ctx == expect_ctx,
                  "own %d/%d, context %d/%d" % (len(own), len(expect_own), len(ctx), len(expect_ctx)))
            seen_in_file[rg] = own
            own_tris = sum(t for n, ex, t, _ in nodes if ex.get("context") is False)
            tgt = rec["targetTriangles"]
            check("within-10pct-of-target:" + fname, abs(own_tris - tgt) <= 0.10 * tgt,
                  "%d own triangles vs target %d (%+.1f%%)" % (own_tris, tgt, 100.0 * (own_tris - tgt) / tgt))
            # the manifest's per-object triangle count is the region-tier count
            check("manifest-triangles:" + fname,
                  all(objs[n]["triangles"] == t for n, ex, t, _ in nodes if ex.get("context") is False),
                  "objects[].triangles agrees with the file")

    check("every-node-name-verified", all_names_ok,
          "%d nodes with a wrong name or extras" % len(bad_names))
    for f, n, ex in bad_names[:10]:
        print("       BAD %s: %r extras=%r" % (f, n, ex))
    check("no-blender-suffixes", not any(BLENDER_SUFFIX.search(n) for (_, n) in exported_tris),
          "checked %d exported nodes" % len(exported_tris))
    # Redrawn geometry: exactly the objects tools/corrections.py names carry
    # corrected=True and source="redrawn", in every file they appear in, at
    # the triangle count corrections.json records; nothing else carries either key.
    check("corrected-extras",
          not bad_corrected and set(corrected_seen) == set(corrections.CORRECTED)
          and (corrections_rec is None or set(corrections_rec) == set(corrections.CORRECTED)),
          "%d corrected objects flagged in %d node occurrences; %d wrong" % (
              len(corrected_seen), sum(len(v) for v in corrected_seen.values()), len(bad_corrected)))
    for f, n, ex in bad_corrected[:10]:
        print("       BAD corrected %s: %r extras=%r" % (f, n, ex))

    if manifest.get("overview"):
        ov = manifest["overview"]
        check("overview-within-10pct", abs(ov["triangles"] - ov["target"]) <= 0.10 * ov["target"],
              "%d vs %d" % (ov["triangles"], ov["target"]))

    # each region exported exactly once as own
    if len(seen_in_file) == len(regions.REGIONS):
        union = set().union(*seen_in_file.values())
        expect = {n for n in inv_names if inv_system[n] != "insertion"}
        overlap = sum(len(v) for v in seen_in_file.values()) - len(union)
        check("each-mesh-own-in-exactly-one-region", union == expect and overlap == 0,
              "%d meshes, %d double-assigned" % (len(union), overlap))

    # ---- decoded geometry ----------------------------------------------------------------
    if not args.no_geometry:
        import bpy
        bpy.ops.wm.read_factory_settings(use_empty=True)
        for label, fname, rec in files:
            path = os.path.join(base, fname)
            if not os.path.exists(path):
                continue
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=path)
            imported = [ob for ob in bpy.data.objects if ob not in before and ob.type == "MESH"]
            vols = {}
            closed = {}
            tri_mismatch = 0
            for ob in imported:
                name = ob.get("sourceName", ob.name)
                v, c, t = signed_volume_and_closed(ob)
                vols[name] = v
                closed[name] = c
                if exported_tris.get((fname, name)) != t:
                    tri_mismatch += 1
            check("decoded-triangles:" + fname, tri_mismatch == 0,
                  "%d meshes decoded, %d disagree with the accessors" % (len(imported), tri_mismatch))
            inside_out = [n for n, c in closed.items() if c and vols[n] < 0]
            check("closed-meshes-outward:" + fname, not inside_out,
                  "%d closed meshes, %d with inward normals" % (sum(closed.values()), len(inside_out)))
            for n in inside_out[:5]:
                print("       INSIDE-OUT %s vol=%.3e" % (n, vols[n]))
            # Signed volume only means something for a closed mesh, so the
            # pair test is over pairs where both sides are closed. A mirror
            # exported inside-out flips the sign; a twin that is separate
            # geometry upstream (the parietal bones differ by 9%) only moves
            # the magnitude, so the magnitude tolerance is loose.
            pairs = bad_pairs = open_pairs = 0
            for n, v in vols.items():
                if scope.side_of(n) != "l":
                    continue
                t = scope.twin_of(n)
                if t not in vols:
                    continue
                if not (closed[n] and closed[t]):
                    open_pairs += 1
                    continue
                pairs += 1
                vt = vols[t]
                scale = max(abs(v), abs(vt), 1e-12)
                # Below 1 cm^3 a 0.5 mm Solidify skin decimated to its floor
                # moves the magnitude by more than any tolerance; the sign is
                # still required to agree.
                if (v > 0) != (vt > 0) or (scale > 1e-6 and abs(v - vt) > 0.15 * scale):
                    bad_pairs += 1
                    if bad_pairs <= 5:
                        print("       PAIR %s %.3e vs %s %.3e" % (n, v, t, vt))
            check("mirror-pairs-same-winding:" + fname, bad_pairs == 0,
                  "%d closed pairs compared by signed volume, %d disagree (%d open pairs not scored)"
                  % (pairs, bad_pairs, open_pairs))
            for ob in imported:
                me = ob.data
                bpy.data.objects.remove(ob)
                if me.users == 0:
                    bpy.data.meshes.remove(me)

    failed = [r for r in results if not r[1]]
    if failed:
        print("VERIFY_EXPORT_FAIL checks=%d failed=%d" % (len(results), len(failed)))
        sys.exit(1)
    print("VERIFY_EXPORT_OK checks=%d failed=0" % len(results))


if __name__ == "__main__":
    main()
