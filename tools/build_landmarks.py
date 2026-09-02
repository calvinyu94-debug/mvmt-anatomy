"""Resolve the 42 palpable landmarks against the source model.

    blender -b source/Z-Anatomy/Startup.blend \
            --python tools/build_landmarks.py -- landmarks.json

Prints LANDMARKS_OK count=42 and exits zero. An anchor object that does not
resolve, a rule that selects nothing, or a resolved point that lands inside
its bone is a hard error, never a silent skip.

For every landmark this resolves the rule in tools/landmark_anchors.py to a
vertex of the bone's evaluated mesh, steps PUSH metres outward, and records:

    anchor            object, uvw in its world bounding box, offset in metres -
                      the scheme the viewer reads; reproduces `resolved`
    resolved          world coordinates, l and r (r is l with X negated), or a
                      single m entry for the six midline landmarks
    surfaceDistance   signed distance to the bone's own surface, metres;
                      positive is outside, by ray-cast parity
    depth             distance to the nearest skin-region surface, metres
    hullDepth         depth beneath the limb's convex cross-section, metres,
                      for limb landmarks; the proxy the nerve job used
    firstPass         where the brief's bounding-box estimate landed, and how
                      far it was from the rule's point

Nothing here is geometry. No glTF is written; the viewer places a marker.
"""

import bpy
import json
import math
import os
import sys

from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from landmark_anchors import LANDMARKS, PUSH, ext, resolve_bounds  # noqa: E402

SKELETON = "1: Skeletal system"
MUSCLE = "4: Muscular system"
REGIONS = "9: Regions of human body"

# Distances a viewer should never see: the checks in verify_landmarks.py use
# the same numbers, and the build refuses to write a point that fails the one
# it can judge alone - inside its own bone.
SURFACE_MAX = 0.005

_depsgraph = None
_bvh_cache = {}
_paths = None


def depsgraph():
    global _depsgraph
    if _depsgraph is None:
        _depsgraph = bpy.context.evaluated_depsgraph_get()
    return _depsgraph


def collection_paths():
    global _paths
    if _paths is None:
        _paths = {}

        def walk(coll, prefix):
            p = (prefix + "/" + coll.name) if prefix else coll.name
            _paths[coll.name] = p
            for child in coll.children:
                walk(child, p)

        walk(bpy.context.scene.collection, "")
    return _paths


def in_collection(ob, key):
    paths = collection_paths()
    return any(key in paths.get(c.name, c.name) for c in ob.users_collection)


def is_label(name):
    return name.endswith((".j", ".t", ".g", ".i", ".s")) or "-txt" in name


def get_object(name):
    ob = bpy.data.objects.get(name)
    if ob is None:
        raise KeyError("Anchor object not found: %s" % name)
    return ob


def world_bbox(ob):
    """The object's world bounding box, as the nerve anchors use it: the
    object's own bound_box (base mesh), transformed."""
    corners = [ob.matrix_world @ Vector(c[:]) for c in ob.bound_box]
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return lo, hi


def eval_geometry(ob):
    """World-space vertices and polygons of the evaluated mesh."""
    ev = ob.evaluated_get(depsgraph())
    me = ev.to_mesh()
    mw = ob.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return verts, polys


def bvh_for(ob):
    """(BVH, vertices) of the evaluated mesh - only vertices that belong to a
    face. Five of the anchor bones carry loose vertices (the sacrum 21, the
    scapula 25, the fibula 19, the atlas 13, the manubrium 3, the occipital
    bone 4): a rule that picked one would return a point that is not on any
    surface, which is how the sacral base first came out 7 mm off the bone."""
    if ob.name not in _bvh_cache:
        verts, polys = eval_geometry(ob)
        used = set(i for poly in polys for i in poly)
        _bvh_cache[ob.name] = (BVHTree.FromPolygons(verts, polys, all_triangles=False),
                               [verts[i] for i in sorted(used)],
                               len(verts) - len(used))
    return _bvh_cache[ob.name][:2]


def loose_vertices(ob):
    bvh_for(ob)
    return _bvh_cache[ob.name][2]


# Three fixed, non-axis-aligned directions: parity along one ray can be fooled
# by grazing an edge, three rarely agree wrongly.
_RAY_DIRS = [Vector(d).normalized() for d in ((0.31, 0.57, 0.76), (-0.83, 0.21, 0.52), (0.44, -0.79, -0.42))]


def inside(bvh, p):
    """Ray-cast parity. Not the normal dot - these meshes are not consistently
    wound, and that test reported everything as inside (CLAUDE.md)."""
    votes = 0
    for d in _RAY_DIRS:
        n = 0
        origin = Vector(p)
        for _ in range(64):
            loc, _nrm, _idx, _dist = bvh.ray_cast(origin, d, 10.0)
            if loc is None:
                break
            n += 1
            origin = loc + d * 1e-5
        votes += n % 2
    return votes >= 2


def signed_distance(ob, p):
    bvh, _ = bvh_for(ob)
    loc, _nrm, _idx, dist = bvh.find_nearest(p)
    if loc is None:
        return None
    return -dist if inside(bvh, p) else dist


# ---------------------------------------------------------------- skin

_skin = None


def skin_patches():
    """A BVH per skin-region patch in "9: Regions of human body".

    These are the atlas's own surface regions - thin Solidify shells over the
    body envelope, 130 of them from the frontal region to the sole. Hairs,
    nails and the label objects are left out. Distance to the nearest patch is
    how far beneath the skin a landmark sits, and the patch's name is a check
    of its own: the lateral malleolus should be nearest the "Lateral
    malleolus" patch. Used only as a measuring reference; nothing from that
    collection is exported.
    """
    global _skin
    if _skin is None:
        _skin = []
        skip = ("hair", "nail", "perionyx", "eyelash", "eyebrow")
        for ob in bpy.data.objects:
            if ob.type != "MESH" or ob.data is None or not ob.data.polygons:
                continue
            if not in_collection(ob, REGIONS) or is_label(ob.name):
                continue
            if any(k in ob.name.lower() for k in skip):
                continue
            v, p = eval_geometry(ob)
            if p:
                _skin.append((ob.name, BVHTree.FromPolygons(v, p, all_triangles=False)))
    return _skin


def skin_depth(p):
    """(distance, patch name) to the nearest skin-region surface."""
    best = None
    for name, bvh in skin_patches():
        loc, _nrm, _idx, dist = bvh.find_nearest(p)
        if loc is not None and (best is None or dist < best[0]):
            best = (dist, name)
    return best


# ---------------------------------------------------------------- hull

_slices = {}
BUCKET = 0.005


def limb_buckets(limb):
    """Skeletal and muscular vertices of one left limb, bucketed by height.

    Objects are taken by centroid. The lower limb is everything left of the
    midline below the iliac crests and medial of X=0.21 - the last bound is
    there because in the A-pose the hand hangs at the height of the greater
    trochanter, 7 cm lateral of it, and without it the hull at that height
    reached the fingers and reported the trochanter 47 mm deep. The upper
    limb is everything lateral of the scapula between the wrist and the
    acromion. The deltoid and the glutei come along, the pectoralis major and
    the trunk do not, so the cross-section is the limb's own envelope.
    """
    if limb in _slices:
        return _slices[limb]
    buckets = {}
    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.data is None or not ob.data.polygons:
            continue
        if not (in_collection(ob, SKELETON) or in_collection(ob, MUSCLE)):
            continue
        if is_label(ob.name):
            continue
        lo, hi = world_bbox(ob)
        c = (lo + hi) / 2.0
        if limb == "lower" and not (0.005 < c.x < 0.21 and c.z < 0.95):
            continue
        if limb == "upper" and not (c.x > 0.16 and 0.65 < c.z < 1.45):
            continue
        mw = ob.matrix_world
        for v in ob.data.vertices:
            w = mw @ v.co
            buckets.setdefault(int(w.z / BUCKET), []).append((w.x, w.y))
    _slices[limb] = buckets
    return buckets


def convex_hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def hull_depth(p, limb):
    """Signed distance from p to the convex hull of the limb's cross-section
    in a fixed 25 mm window about p's height. Positive is inside the hull."""
    buckets = limb_buckets(limb)
    k = int(p.z / BUCKET)
    pts = []
    for i in range(k - 2, k + 3):
        pts += buckets.get(i, [])
    if len(pts) < 32:
        return None
    hull = convex_hull(pts)
    best = None
    ins = True
    for a, b in zip(hull, hull[1:] + hull[:1]):
        ex, ey = b[0] - a[0], b[1] - a[1]
        L2 = ex * ex + ey * ey
        t = max(0.0, min(1.0, ((p.x - a[0]) * ex + (p.y - a[1]) * ey) / L2)) if L2 else 0.0
        qx, qy = a[0] + t * ex, a[1] + t * ey
        d = math.hypot(p.x - qx, p.y - qy)
        if best is None or d < best:
            best = d
        if ex * (p.y - a[1]) - ey * (p.x - a[0]) < 0:
            ins = False
    return best if ins else -best


# ---------------------------------------------------------------- resolve


def lerp_bbox(lo, hi, uvw):
    return Vector((lo.x + (hi.x - lo.x) * uvw[0],
                   lo.y + (hi.y - lo.y) * uvw[1],
                   lo.z + (hi.z - lo.z) * uvw[2]))


def right_object(name):
    if name.endswith(".l"):
        return get_object(name[:-2] + ".r")
    return get_object(name)


def resolve_one(spec):
    ob = get_object(spec["object"])
    lo, hi = world_bbox(ob)
    _bvh, V = bvh_for(ob)

    rule = spec["rule"]
    if callable(rule):
        v = rule(V, lo, hi)
    else:
        d, bounds = rule
        v = ext(V, d, **resolve_bounds(bounds, lo, hi))

    push = spec["push"]
    if callable(rule):
        # a function rule has no single direction to check the push against;
        # parity below is the guarantee
        pass
    elif push.dot(rule[0]) <= 0:
        raise ValueError("%s: push direction has no component along the rule" % spec["id"])

    p = v + push * PUSH
    sd = signed_distance(ob, p)
    if sd is None or sd < 0:
        raise ValueError("%s: resolved point is inside %s (%.2f mm)"
                         % (spec["id"], ob.name, (sd or 0) * 1000))

    span = hi - lo
    uvw = [(v[i] - lo[i]) / span[i] if span[i] > 1e-9 else 0.0 for i in range(3)]
    offset = push * PUSH

    rec = {
        "id": spec["id"],
        "name": spec["name"],
        "region": spec["region"],
        "limb": spec["limb"],
        "hull": spec["hull"],
        "paired": spec["paired"],
        "target": spec["target"],
        "anchor": {
            "object": ob.name,
            "uvw": [round(c, 4) for c in uvw],
            "offset": [round(c, 5) for c in offset],
        },
    }

    pr = Vector((-p.x, p.y, p.z))
    if spec["paired"]:
        rec["resolved"] = {"l": [round(c, 5) for c in p], "r": [round(c, 5) for c in pr]}
    else:
        rec["resolved"] = {"m": [round(c, 5) for c in p]}

    rec["surfaceDistance"] = round(sd, 5)
    depth, patch = skin_depth(p)
    rec["depth"] = round(depth, 5)
    rec["nearestSkin"] = patch
    if spec["hull"]:
        hd = hull_depth(p, spec["hull"])
        rec["hullDepth"] = None if hd is None else round(hd, 5)

    # the right side, measured on the right bone
    obr = right_object(ob.name)
    rec["surfaceDistanceRight"] = round(signed_distance(obr, pr), 5)

    if spec["first_pass"] is not None:
        p0 = lerp_bbox(lo, hi, spec["first_pass"]) + Vector(spec["first_pass_offset"])
        sd0 = signed_distance(ob, p0)
        rec["firstPass"] = {
            "uvw": list(spec["first_pass"]),
            "resolved": [round(c, 5) for c in p0],
            "surfaceDistance": round(sd0, 5),
            "movedBy": round((p - p0).length, 5),
            "moved": [round(c, 5) for c in (p - p0)],
        }
    else:
        rec["firstPass"] = None

    rec["_p"] = p
    rec["_v"] = v
    rec["_lo"] = lo
    rec["_hi"] = hi
    return rec


def resolve_all(verbose=True):
    out = []
    for spec in LANDMARKS:
        rec = resolve_one(spec)
        out.append(rec)
        if verbose:
            fp = rec["firstPass"]
            print("  %-28s %-22s v=(%.4f %.4f %.4f) surf=%+.1fmm skin=%5.1fmm %-32s hull=%s  first-pass: %s"
                  % (rec["id"], rec["anchor"]["object"], rec["_v"].x, rec["_v"].y, rec["_v"].z,
                     rec["surfaceDistance"] * 1000, rec["depth"] * 1000, rec["nearestSkin"],
                     ("%.1fmm" % (rec["hullDepth"] * 1000)) if rec.get("hullDepth") is not None else "-",
                     ("surf=%+.1fmm moved=%.1fmm" % (fp["surfaceDistance"] * 1000, fp["movedBy"] * 1000)) if fp else "-"))
    return out


def strip(rec):
    return {k: v for k, v in rec.items() if not k.startswith("_")}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    json_path = argv[0] if argv else "landmarks.json"

    print("-- resolve")
    recs = resolve_all()

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": 1,
            "note": ("Palpable landmarks as points on the model's bones. Each is "
                     "the vertex its anatomical rule selects on the bone's "
                     "evaluated mesh, stepped %.0f mm outward. The anchor "
                     "(object, uvw, offset) reproduces the resolved point; uvw "
                     "is an output of the rule, not an estimate. Right side is "
                     "the left with X negated." % (PUSH * 1000)),
            "units": "metres",
            "up": "Z",
            "sideConvention": {"l": "+X", "r": "-X"},
            "push": PUSH,
            "landmarks": [strip(r) for r in recs],
        }, f, indent=1)

    print("LANDMARKS_OK count=%d json=%s" % (len(recs), json_path))


if __name__ == "__main__":
    main()
