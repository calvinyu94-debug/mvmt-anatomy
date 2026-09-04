"""Source meshes redrawn in the export by anchor rule.

A Z-Anatomy object whose attachment is demonstrably wrong is not hand-edited
in the .blend - a correction that lives only in a saved file is one nobody
can rebuild. It is redrawn here, at export time, from a rule written the way
the landmarks are written: the attachment described anatomically, resolved
to a point on a named bone's real vertices, recomputed on every build. The
object keeps its name, its material, its collection and its parent; only the
mesh data the export writes for it is replaced. The exported node carries
`corrected = True` and `source = "redrawn"` in its extras, the way the
authored nerves carry `authored = True`, so a viewer can say so on screen.

Every rule is written for one side and RUN on each side's own bones - the
right is the rule mirrored, never the left geometry mirrored. The two sides
are then compared, and an asymmetry larger than the bones' own would mean
the rule read something it should not have.

    Calcaneofibular ligament .l / .r

    In the source this is a two-triangle quad, 18 x 6 x 13 mm after its
    modifiers, whose lateral edge touches the fibula 1-10 mm above the tip of
    the malleolus and whose medial edge rests on the top of the calcaneus
    directly beneath it. It runs medially under the malleolus. The real
    ligament is a cord about 2 cm long from the anterior-distal face of the
    lateral malleolus down and back to a tubercle on the lateral wall of the
    calcaneus, crossing the talocrural and subtalar joints lateral to the
    talus (Netter, right foot, lateral view).

    Fibular end: the resolved lm-lateral-malleolus landmark - the most
    inferior fibular vertex stepped 2 mm out along (lateral, 0, -1) - offset
    2 mm anterior and 1 mm distal.

    Calcaneal end: the vertex on the lateral face of the calcaneus nearest
    to lateral malleolus + (0 lateral, 10 mm posterior, 13 mm distal). The
    lateral face is the set of vertices whose outward normal has a positive
    component away from the midline, the normal oriented by ray-cast parity
    rather than trusted (CLAUDE.md), and the chosen vertex is also required
    to be the first surface a ray from the lateral side meets. Nearest on
    that face, not nearest overall: the target sits 9 mm lateral of the bone
    because the malleolus overhangs the calcaneal wall, so the nearest
    vertex overall could in principle be one on the superior surface.

    Acceptance, asserted: the calcaneal point within 3 mm of a calcaneus
    vertex, z between 0.032 and 0.046, posterior to the fibular end in y.
    If the rule lands outside that box the rule is wrong, and the build
    stops and prints the point rather than moving the box.

    The ribbon is a flat box, 7 mm wide and 1.5 mm thick, 12 triangles, its
    long axis from the fibular end to the calcaneal end and its flat face
    turned as far laterally as that axis allows. Its centreline is checked
    for clearance from the talus, which it must not enter.

Coordinates, from tools/inventory.py: metres, Z up, +X left, -Y anterior;
`.l` at +X. Right-side points are checked on the right-side bones.
"""

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import build_landmarks as B
from landmark_anchors import LANDMARKS, PUSH, ext, resolve_bounds

# Every object the export redraws. verify_export.py reads this to demand the
# extras on exactly these nodes and on no others.
CORRECTED = ("Calcaneofibular ligament.l", "Calcaneofibular ligament.r")

CFL_WIDTH = 0.007
CFL_THICKNESS = 0.0015
CFL_FIBULAR_OFFSET = Vector((0.0, -0.002, -0.001))     # 2 mm anterior, 1 mm distal
CFL_CALCANEAL_TARGET = Vector((0.0, 0.010, -0.013))    # 10 mm posterior, 13 mm distal
CFL_ACCEPT_VERTEX = 0.003
CFL_ACCEPT_Z = (0.032, 0.046)

SIDES = ("l", "r")


def sign_of(side):
    return 1.0 if side == "l" else -1.0


def lateral(side):
    return Vector((sign_of(side), 0.0, 0.0))


def mirror(v, side):
    """A left-side vector or point on the given side: X negated for the right."""
    return Vector((-v.x, v.y, v.z)) if side == "r" else Vector(v)


def sided(name, side):
    return name[:-2] + "." + side if name.endswith((".l", ".r")) else name


def rnd(v, n=5):
    return [round(c, n) for c in v]


# ---------------------------------------------------------------- landmarks


def landmark_point(id, side):
    """The landmark's rule from tools/landmark_anchors.py, run on this side's
    bone. Only plain (direction, bounds) rules without an X bound are
    mirrored here; that is all a correction has needed so far."""
    spec = next(s for s in LANDMARKS if s["id"] == id)
    rule = spec["rule"]
    if callable(rule):
        raise NotImplementedError("%s: function rules are not mirrored here" % id)
    d, bounds = rule
    if side == "r" and "x" in bounds:
        raise NotImplementedError("%s: X-bounded rules are not mirrored here" % id)
    ob = B.get_object(sided(spec["object"], side))
    lo, hi = B.world_bbox(ob)
    _bvh, V = B.bvh_for(ob)
    v = ext(V, mirror(d, side), **resolve_bounds(bounds, lo, hi))
    p = v + mirror(spec["push"], side) * PUSH
    return p, v, ob


# ------------------------------------------------------------- bone faces


def oriented_vertices(ob):
    """(point, outward normal) for every face-referenced vertex of the
    evaluated mesh. The normal is oriented by ray-cast parity: a point 1.5 mm
    along it must be outside the bone, else it is flipped."""
    bvh, _ = B.bvh_for(ob)
    ev = ob.evaluated_get(B.depsgraph())
    me = ev.to_mesh()
    mw = ob.matrix_world
    nm = mw.inverted().transposed().to_3x3()
    used = set(i for p in me.polygons for i in p.vertices)
    raw = [(mw @ v.co, (nm @ v.normal).normalized()) for i, v in enumerate(me.vertices) if i in used]
    ev.to_mesh_clear()
    out = []
    for p, n in raw:
        if B.inside(bvh, p + n * 0.0015):
            n = -n
        out.append((p, n))
    return out


def lateral_face(ob, side):
    """Vertices whose outward normal points away from the midline."""
    s = sign_of(side)
    return [(p, n) for p, n in oriented_vertices(ob) if n.x * s > 0.0]


def first_hit_from_lateral(ob, p, side):
    """Whether p is the first surface of ob a ray from far lateral meets
    at its own height and depth - i.e. is on the outside of the bone."""
    bvh, _ = B.bvh_for(ob)
    s = sign_of(side)
    loc, _n, _i, _d = bvh.ray_cast(Vector((s * 0.5, p.y, p.z)), Vector((-s, 0.0, 0.0)), 2.0)
    return loc is not None and (loc - p).length < 0.0005


# ------------------------------------------------------------------ ribbon


def ribbon(a, b, lat, width, thickness):
    """A flat box from a to b: world-space vertices and triangles, wound
    outward (positive signed volume). The thickness axis is the lateral
    direction made perpendicular to the long axis, so the flat face looks
    outward; the width axis is perpendicular to both."""
    u = (b - a).normalized()
    t = (lat - lat.dot(u) * u).normalized()
    w = u.cross(t).normalized()
    if w.y < 0:
        w = -w          # posterior: the same corner order on both sides
    hw, ht = width / 2.0, thickness / 2.0
    corners = [p + w * hw * sw + t * ht * st
               for p in (a, b) for sw in (-1, 1) for st in (-1, 1)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    bm = bmesh.new()
    bv = [bm.verts.new(c) for c in corners]
    for q in quads:
        bm.faces.new([bv[i] for i in q])
    bm.normal_update()
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.verts.index_update()
    verts = [v.co.copy() for v in bm.verts]
    tris = [[v.index for v in f.verts] for f in bm.faces]
    vol = bm.calc_volume(signed=True)
    bm.free()
    assert vol > 0, vol
    return verts, tris, {"axis": u, "thicknessAxis": t, "widthAxis": w}


def overlap_count(verts, tris, ob):
    mine = BVHTree.FromPolygons(verts, tris, all_triangles=True)
    theirs, _ = B.bvh_for(ob)
    return len(mine.overlap(theirs))


def clearance(a, b, ob, n=21):
    """Minimum signed distance from the segment's centreline to the bone."""
    return min(B.signed_distance(ob, a.lerp(b, i / float(n - 1))) for i in range(n))


# --------------------------------------------------------------------- CFL


def build_cfl(side):
    name = "Calcaneofibular ligament." + side
    fib = B.get_object("Fibula." + side)
    tal = B.get_object("Talus." + side)
    cal = B.get_object("Calcaneus." + side)

    lm, tip, _ = landmark_point("lm-lateral-malleolus", side)
    a = lm + mirror(CFL_FIBULAR_OFFSET, side)

    target = lm + mirror(CFL_CALCANEAL_TARGET, side)
    face = lateral_face(cal, side)
    if not face:
        raise ValueError("%s: no lateral-face vertices on %s" % (name, cal.name))
    b, bn = min(face, key=lambda pn: (pn[0] - target).length)
    _bvh, CV = B.bvh_for(cal)
    nearest_vertex = min((q - b).length for q in CV)
    nearest_overall = min(CV, key=lambda q: (q - target).length)

    problems = []
    if nearest_vertex > CFL_ACCEPT_VERTEX:
        problems.append("%.1f mm from the nearest calcaneus vertex" % (nearest_vertex * 1000))
    if not (CFL_ACCEPT_Z[0] <= b.z <= CFL_ACCEPT_Z[1]):
        problems.append("z=%.4f outside %s" % (b.z, CFL_ACCEPT_Z))
    if not b.y > a.y:
        problems.append("not posterior to the fibular end (y %.4f vs %.4f)" % (b.y, a.y))
    if not first_hit_from_lateral(cal, b, side):
        problems.append("not the first calcaneal surface a lateral ray meets")
    if problems:
        raise ValueError(
            "%s: the calcaneal rule is wrong, not the box. Resolved (%.4f, %.4f, %.4f) "
            "for target (%.4f, %.4f, %.4f): %s"
            % (name, b.x, b.y, b.z, target.x, target.y, target.z, "; ".join(problems)))

    verts, tris, axes = ribbon(a, b, lateral(side), CFL_WIDTH, CFL_THICKNESS)
    talus_overlap = overlap_count(verts, tris, tal)
    if talus_overlap:
        raise ValueError("%s: the ribbon passes through %s (%d triangle pairs)" % (name, tal.name, talus_overlap))

    record = {
        "object": name,
        "source": "redrawn",
        "rule": "fibular end = lm-lateral-malleolus + (0, 2 mm anterior, 1 mm distal); calcaneal end = "
                "nearest lateral-face vertex of the calcaneus to lm-lateral-malleolus + "
                "(0, 10 mm posterior, 13 mm distal); flat ribbon between them",
        "fibularEnd": {
            "landmark": "lm-lateral-malleolus",
            "landmarkVertex": rnd(tip),
            "landmarkResolved": rnd(lm),
            "offset": rnd(mirror(CFL_FIBULAR_OFFSET, side)),
            "point": rnd(a),
            "surfaceDistance": {fib.name: round(B.signed_distance(fib, a), 5),
                                tal.name: round(B.signed_distance(tal, a), 5)},
        },
        "calcanealEnd": {
            "target": rnd(target),
            "targetSurfaceDistance": round(B.signed_distance(cal, target), 5),
            "point": rnd(b),
            "normal": rnd(bn, 4),
            "lateralFaceVertices": len(face),
            "nearestVertexDistance": round(nearest_vertex, 5),
            "nearestVertexOverall": rnd(nearest_overall),
            "sameAsNearestOverall": (nearest_overall - b).length < 1e-9,
            "offsetFromTarget": rnd(b - target),
            "acceptance": {"vertexWithin": CFL_ACCEPT_VERTEX, "z": list(CFL_ACCEPT_Z),
                           "posteriorToFibularEnd": True},
        },
        "length": round((b - a).length, 5),
        "width": CFL_WIDTH,
        "thickness": CFL_THICKNESS,
        "axis": rnd(axes["axis"], 4),
        "triangles": len(tris),
        "centrelineClearance": {tal.name: round(clearance(a, b, tal), 5),
                                fib.name: round(clearance(a, b, fib), 5),
                                cal.name: round(clearance(a, b, cal), 5)},
        "overlapTrianglePairs": {tal.name: talus_overlap,
                                 fib.name: overlap_count(verts, tris, fib),
                                 cal.name: overlap_count(verts, tris, cal)},
    }
    return verts, tris, record


BUILDERS = {
    "Calcaneofibular ligament.l": lambda: build_cfl("l"),
    "Calcaneofibular ligament.r": lambda: build_cfl("r"),
}
assert set(BUILDERS) == set(CORRECTED)


# ------------------------------------------------------------------ driver


def resolve_all(verbose=True):
    """{object name: (world vertices, triangles, record)} for every corrected
    object. Runs the rules on the live source objects, so it must be called
    while they still carry their own names."""
    out = {}
    for name in CORRECTED:
        verts, tris, rec = BUILDERS[name]()
        out[name] = (verts, tris, rec)
        if verbose:
            f, c = rec["fibularEnd"], rec["calcanealEnd"]
            print("  %-32s fibular (%.4f %.4f %.4f) surf(fib)=%+.1fmm  calcaneal (%.4f %.4f %.4f) "
                  "target-offset (%.1f %.1f %.1f)mm  length=%.1fmm  clearance talus=%+.1fmm  %d tris"
                  % (name, f["point"][0], f["point"][1], f["point"][2],
                     list(f["surfaceDistance"].values())[0] * 1000,
                     c["point"][0], c["point"][1], c["point"][2],
                     c["offsetFromTarget"][0] * 1000, c["offsetFromTarget"][1] * 1000, c["offsetFromTarget"][2] * 1000,
                     rec["length"] * 1000, list(rec["centrelineClearance"].values())[0] * 1000, rec["triangles"]))
    # Each side ran on its own bones. Report how far the two results are from
    # mirror images: the bones are mirror instances, so this should be ~0.
    for name in CORRECTED:
        if not name.endswith(".l"):
            continue
        twin = name[:-2] + ".r"
        if twin not in out:
            continue
        vl, _, recl = out[name]
        vr, _, recr = out[twin]
        worst = max(min((mirror(p, "r") - q).length for q in vr) for p in vl)
        recl["mirrorAsymmetry"] = recr["mirrorAsymmetry"] = round(worst, 6)
        if verbose:
            print("  %s / .r: sides resolved independently, worst mirror asymmetry %.3f mm" % (name[:-2], worst * 1000))
        if worst > 0.0005:
            raise ValueError("%s: the two sides differ by %.2f mm - the rule read something side-dependent" % (name, worst * 1000))
    return out


def local_mesh(name, ob, verts, tris):
    """A Blender mesh for the exporter: the corrected geometry in the source
    object's own frame, carrying the source mesh's materials, wound so that
    its signed volume is positive in that frame - which is what bake_mesh
    expects of every source mesh, mirrored or not."""
    inv = ob.matrix_world.inverted()
    me = bpy.data.meshes.new("corrected|" + name)
    me.from_pydata([inv @ v for v in verts], [], tris)
    for mat in ob.data.materials:
        me.materials.append(mat)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.to_mesh(me)
    bm.free()
    me.update()
    return me


def write_record(path, resolved):
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "version": 1,
            "note": ("Source meshes redrawn in the export by anchor rule (tools/corrections.py). "
                     "Each record is the rule's result on the build that wrote this file: both "
                     "attachment points, the acceptance measurements, and the ribbon's clearance "
                     "from the neighbouring bones. Both sides are resolved on their own bones."),
            "units": "metres",
            "up": "Z",
            "sideConvention": {"l": "+X", "r": "-X"},
            "objects": [resolved[n][2] for n in CORRECTED],
        }, f, indent=1)
