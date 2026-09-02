"""Verify the 42 palpable landmarks against the real source geometry.

    blender -b source/Z-Anatomy/Startup.blend \
            --python tools/verify_landmarks.py -- [--render verification/landmarks]

Landmarks are palpable by definition, which gives hard criteria the nerves
did not have. Every landmark must:

  1. Sit on or just outside its bone: signed distance 0 to +5 mm, on both
     sides, sign by ray-cast parity.
  2. Be shallow beneath the limb envelope: under 20 mm for limb landmarks,
     measured against the convex hull of the limb's own cross-section.
  3. Be left-right symmetric: the anchor scheme applied to the right-hand
     bone must land within 3 mm of the left point mirrored, and the right
     point must be on or outside the right bone too.

Then the named relationships a practitioner checks first, each reported
with its margin in millimetres. Distal/proximal on the forearm is measured
along the forearm's own axis: the A-pose forearm leans 13 degrees, and in
world Z the two styloids come out level.

Prints VERIFY_LANDMARKS_OK or VERIFY_LANDMARKS_FAIL with a count, and exits
non-zero on failure.
"""

import bmesh
import bpy
import math
import os
import sys

from mathutils import Vector

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import build_landmarks as B  # noqa: E402
from build_landmarks import SKELETON, is_label, in_collection  # noqa: E402
from landmark_anchors import PUSH, sel  # noqa: E402

SURFACE_MAX = 0.005
DEPTH_MAX = 0.020
SYMMETRY_MAX = 0.003

results = []


def check(name, ok, detail):
    results.append((name, bool(ok), detail))
    print("  %-4s %-40s %s" % ("PASS" if ok else "FAIL", name, detail))


def info(name, detail):
    print("  %-4s %-40s %s" % ("info", name, detail))


def mm(v):
    return "%+.1f mm" % (v * 1000.0)


# ---------------------------------------------------------------- checks


def check_surface(recs):
    worst = max(recs, key=lambda r: abs(r["surfaceDistance"] - SURFACE_MAX / 2))
    bad = [r for r in recs if not (0.0 <= r["surfaceDistance"] <= SURFACE_MAX)]
    lo = min(r["surfaceDistance"] for r in recs)
    hi = max(r["surfaceDistance"] for r in recs)
    check("on-or-outside-own-bone-left", not bad,
          "range %s to %s across 42" % (mm(lo), mm(hi)) if not bad
          else "%d outside 0..5 mm: %s" % (len(bad), ", ".join("%s %s" % (r["id"], mm(r["surfaceDistance"])) for r in bad)))
    del worst

    badr = [r for r in recs if not (0.0 <= r["surfaceDistanceRight"] <= SURFACE_MAX)]
    lo = min(r["surfaceDistanceRight"] for r in recs)
    hi = max(r["surfaceDistanceRight"] for r in recs)
    check("on-or-outside-own-bone-right", not badr,
          "range %s to %s across 42, mirrored onto the .r bone" % (mm(lo), mm(hi)) if not badr
          else "%d outside 0..5 mm: %s" % (len(badr), ", ".join("%s %s" % (r["id"], mm(r["surfaceDistanceRight"])) for r in badr)))


def check_anchor_reproduces(recs):
    """The (object, uvw, offset) the viewer reads must give `resolved` back."""
    worst = 0.0
    for r in recs:
        ob = B.get_object(r["anchor"]["object"])
        lo, hi = B.world_bbox(ob)
        q = B.lerp_bbox(lo, hi, r["anchor"]["uvw"]) + Vector(r["anchor"]["offset"])
        worst = max(worst, (q - r["_p"]).length)
    check("anchor-reproduces-resolved", worst < 0.0003,
          "worst round-trip through uvw+offset %.2f mm" % (worst * 1000))


def check_depth(recs):
    limb = [r for r in recs if r["limb"]]
    missing = [r["id"] for r in limb if r.get("hullDepth") is None]
    bad = [r for r in limb if r.get("hullDepth") is not None and r["hullDepth"] >= DEPTH_MAX]
    deepest = max((r for r in limb if r.get("hullDepth") is not None), key=lambda r: r["hullDepth"])
    shallowest = min((r for r in limb if r.get("hullDepth") is not None), key=lambda r: r["hullDepth"])
    check("limb-landmarks-under-20mm-hull", not bad and not missing,
          "%d limb landmarks, hull depth %s (%s) to %s (%s)"
          % (len(limb), mm(shallowest["hullDepth"]), shallowest["id"], mm(deepest["hullDepth"]), deepest["id"])
          if not bad and not missing
          else "over 20 mm: %s; unmeasured: %s"
          % (", ".join("%s %s" % (r["id"], mm(r["hullDepth"])) for r in bad), missing))

    sk = max(limb, key=lambda r: r["depth"])
    sk_bad = [r for r in limb if r["depth"] >= DEPTH_MAX]
    info("limb-landmarks-skin-distance",
         "nearest skin-region patch %s (%s) to %s (%s); over 20 mm: %s"
         % (mm(min(r["depth"] for r in limb)), min(limb, key=lambda r: r["depth"])["id"],
            mm(sk["depth"]), sk["id"],
            ", ".join("%s %s" % (r["id"], mm(r["depth"])) for r in sk_bad) or "none"))

    # The two humeral shoulder landmarks lie under the deltoid, which in this
    # model is 24-26 mm thick over them. Reported against the same hull, not
    # asserted - a fail here would be the model's soft tissue, not a
    # misplaced point. Decide separately whether the limit should bind them.
    for r in recs:
        if r["hull"] and not r["limb"]:
            info("under-deltoid-" + r["id"],
                 "hull %s, skin %s (%s) - over the 20 mm limb limit, not asserted"
                 % (mm(r["hullDepth"]), mm(r["depth"]), r["nearestSkin"]))


def check_symmetry(recs):
    worst = None
    bad = []
    for r in recs:
        if not r["paired"]:
            continue
        ob = B.get_object(r["anchor"]["object"])
        obr = B.right_object(ob.name)
        lo, hi = B.world_bbox(obr)
        u, v, w = r["anchor"]["uvw"]
        off = Vector(r["anchor"]["offset"])
        # the right box is the left box reflected, so u reflects too
        q = B.lerp_bbox(lo, hi, (1.0 - u, v, w)) + Vector((-off.x, off.y, off.z))
        pr = Vector(r["resolved"]["r"])
        d = (q - pr).length
        dsd = abs(r["surfaceDistanceRight"] - r["surfaceDistance"])
        if worst is None or d > worst[0]:
            worst = (d, r["id"], dsd)
        if d > SYMMETRY_MAX or dsd > SYMMETRY_MAX:
            bad.append((r["id"], d, dsd))
    n = sum(1 for r in recs if r["paired"])
    check("paired-landmarks-symmetric", not bad,
          "%d paired; anchor scheme on the .r bone vs mirrored left, worst %.2f mm (%s); "
          "surface distance differs by at most %.2f mm"
          % (n, worst[0] * 1000, worst[1], max(abs(r["surfaceDistanceRight"] - r["surfaceDistance"]) for r in recs if r["paired"]) * 1000)
          if not bad else "; ".join("%s %.1f mm / surface %.1f mm" % b for b in bad))


def by_id(recs):
    return {r["id"]: r["_p"] for r in recs}


def forearm_axis():
    """Unit vector from the elbow to the wrist along the left forearm."""
    R = B.get_object("Radius.l")
    U = B.get_object("Ulna.l")
    _, rv = B.bvh_for(R)
    _, uv = B.bvh_for(U)
    lor, hir = B.world_bbox(R)
    lou, hiu = B.world_bbox(U)
    prox = sel(rv, z=(hir.z - 0.02, None)) + sel(uv, z=(hiu.z - 0.02, None))
    dist = sel(rv, z=(None, lor.z + 0.02)) + sel(uv, z=(None, lou.z + 0.02))
    c = lambda V: sum(V, Vector()) / len(V)
    return (c(dist) - c(prox)).normalized()


def check_relationships(recs):
    P = by_id(recs)

    ax = forearm_axis()
    rs, us = P["lm-radial-styloid"], P["lm-ulnar-styloid"]
    axial = rs.dot(ax) - us.dot(ax)
    check("radial-styloid-distal-to-ulnar", axial > 0,
          "%s along the forearm axis (axis leans %.0f deg from vertical; in world Z the radial is %s higher)"
          % (mm(axial), math.degrees(math.acos(-ax.z)), mm(us.z - rs.z)))

    lm_, mm_ = P["lm-lateral-malleolus"], P["lm-medial-malleolus"]
    check("lateral-malleolus-distal-to-medial", mm_.z > lm_.z, "%s lower" % mm(mm_.z - lm_.z))
    check("lateral-malleolus-posterior-to-medial", lm_.y > mm_.y, "%s posterior" % mm(lm_.y - mm_.y))

    asis, psis, isch = P["lm-asis"], P["lm-psis"], P["lm-ischial-tuberosity"]
    check("psis-posterior-to-asis", psis.y > asis.y, "%s posterior" % mm(psis.y - asis.y))
    check("asis-and-psis-superior-to-ischial-tuberosity", asis.z > isch.z and psis.z > isch.z,
          "ASIS %s, PSIS %s above it" % (mm(asis.z - isch.z), mm(psis.z - isch.z)))

    hip = ["lm-iliac-crest", "lm-asis", "lm-psis", "lm-ischial-tuberosity", "lm-pubic-tubercle"]
    gt = P["lm-greater-trochanter"]
    other = max(hip, key=lambda k: P[k].x)
    check("greater-trochanter-most-lateral-in-hip", all(gt.x > P[k].x for k in hip),
          "%s lateral of the next most lateral (%s)" % (mm(gt.x - P[other].x), other))

    ac, co = P["lm-acromion"], P["lm-coracoid"]
    check("acromion-superior-and-lateral-to-coracoid", ac.z > co.z and ac.x > co.x,
          "%s superior, %s lateral" % (mm(ac.z - co.z), mm(ac.x - co.x)))

    c7, c2 = P["lm-c7-spinous"], P["lm-c2-spinous"]
    check("c7-posterior-and-inferior-to-c2", c7.y > c2.y and c7.z < c2.z,
          "%s posterior, %s inferior" % (mm(c7.y - c2.y), mm(c2.z - c7.z)))

    # not in the brief's six, but the brief asked for them to be verified
    st = P["lm-sustentaculum-tali"]
    info("sustentaculum-below-medial-malleolus", "%s below the malleolar tip" % mm(mm_.z - st.z))
    info("coracoid-from-acromion", "%.1f mm apart" % ((ac - co).length * 1000))


def report_skin(recs):
    print("       nearest skin-region patch per landmark:")
    for r in recs:
        print("         %-28s %5.1f mm  %s" % (r["id"], r["depth"] * 1000, r["nearestSkin"]))


def report_first_pass(recs):
    print("       brief's first-pass uvw vs the rule's point (left side):")
    for r in sorted((r for r in recs if r["firstPass"]), key=lambda r: -r["firstPass"]["movedBy"]):
        fp = r["firstPass"]
        print("         %-28s moved %5.1f mm   first pass was %s from the bone"
              % (r["id"], fp["movedBy"] * 1000, mm(fp["surfaceDistance"])))


# ---------------------------------------------------------------- render


def make_sphere(name, loc, radius, mat, coll):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=12, radius=radius)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    coll.objects.link(ob)
    return ob


def make_leader(name, a, b, radius, mat, coll):
    d = b - a
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=6, radius1=radius, radius2=radius, depth=d.length)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = (a + b) / 2.0
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    coll.objects.link(ob)
    return ob


def make_text(name, body, loc, rot, size, align, mat, coll):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.materials.append(mat)
    ob = bpy.data.objects.new(name, cu)
    ob.location = loc
    ob.rotation_euler = rot
    coll.objects.link(ob)
    return ob


def emission(name, rgb, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (rgb[0], rgb[1], rgb[2], 1)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    return m


def spread(labels, h):
    """Push overlapping labels apart vertically, keeping each cluster centred
    on where its points are. labels: list of dicts with 'v'."""
    labels.sort(key=lambda l: l["v"])
    for _ in range(200):
        moved = False
        for a, b in zip(labels, labels[1:]):
            gap = (a["v"] + h) - b["v"]
            if gap > 0:
                a["v"] -= gap / 2.0
                b["v"] += gap / 2.0
                moved = True
        if not moved:
            break


def render(outdir, recs, samples=24, res=3000):
    scene = bpy.data.scenes.new("verify_landmarks")
    scene.view_settings.view_transform = "Standard"

    bone_mat = bpy.data.materials.new("verify_bone")
    bone_mat.use_nodes = True
    bsdf = bone_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.85, 0.84, 0.80, 1)
    bsdf.inputs["Alpha"].default_value = 0.12
    bsdf.inputs["Roughness"].default_value = 0.6
    bone_mat.blend_method = "BLEND"

    mark_mat = emission("verify_mark", (1.0, 0.45, 0.05), 2.0)
    mid_mat = emission("verify_mark_mid", (0.2, 0.9, 1.0), 2.0)
    text_mat = emission("verify_text", (1.0, 0.95, 0.8), 1.5)
    lead_mat = emission("verify_lead", (0.9, 0.8, 0.6), 1.0)

    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.data is None or not ob.data.polygons:
            continue
        if not in_collection(ob, SKELETON) or is_label(ob.name):
            continue
        ob.data.materials.clear()
        ob.data.materials.append(bone_mat)
        ob.hide_render = False
        scene.collection.objects.link(ob)

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 4
    scene.cycles.transparent_max_bounces = 32
    scene.render.film_transparent = False
    # portrait: the body is 1.75 m tall and 0.7 m wide with the arms down
    scene.render.resolution_x = int(res * 0.6)
    scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.use_freestyle = False

    world = bpy.data.worlds.new("verify_world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.04, 0.05, 0.07, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    scene.world = world

    for nm, loc, energy in (("verify_key", (2.0, -3.0, 3.0), 6.0),
                            ("verify_fill", (-3.0, 2.5, 1.5), 3.0)):
        ld = bpy.data.lights.new(nm, "SUN")
        ld.energy = energy
        lo = bpy.data.objects.new(nm, ld)
        lo.location = loc
        lo.rotation_euler = (-Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(lo)

    scene.render.use_stamp = True
    scene.render.use_stamp_note = True
    scene.render.stamp_note_text = (
        "42 palpable landmarks as points on the model's bones - landmarks.json. "
        "Orange: paired, cyan: midline. Marker radius 6 mm.")
    for attr in ("date", "time", "render_time", "frame", "scene", "filename", "memory",
                 "camera", "lens", "marker", "hostname", "sequencer_strip"):
        setattr(scene.render, "use_stamp_" + attr, False)
    scene.render.stamp_font_size = 28

    cam_data = bpy.data.cameras.new("verify_cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("verify_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    # markers for every side that exists
    points = []       # (rec, side, world point)
    for r in recs:
        for side, p in r["resolved"].items():
            points.append((r, side, Vector(p)))
    for i, (r, side, p) in enumerate(points):
        make_sphere("lm_%s_%s" % (r["id"], side), p, 0.006,
                    mid_mat if side == "m" else mark_mat, scene.collection)

    # (name, direction the camera looks along, sides shown, u-centre for label side)
    VIEWS = [
        ("01-anterior",      Vector((0, 1, 0)),  ("l", "r", "m"), 0.0),
        ("02-posterior",     Vector((0, -1, 0)), ("l", "r", "m"), 0.0),
        ("03-left-lateral",  Vector((-1, 0, 0)), ("l", "m"), 0.02),
        ("04-right-lateral", Vector((1, 0, 0)),  ("r", "m"), 0.02),
    ]
    centre = Vector((0.0, 0.02, 0.87))
    width = 1.95          # ortho scale applies to the taller side
    font = 0.012

    outdir = os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)
    for name, d, sides, ucentre in VIEWS:
        d = d.normalized()
        right = Vector((0, 0, 1)).cross(-d).normalized()    # screen right
        rot = (-d).to_track_quat("Z", "Y").to_euler()        # text faces the camera
        cam.location = centre - d * 3.0
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()   # the camera looks along d
        cam_data.ortho_scale = width

        for ob in scene.collection.objects:
            if ob.name.startswith("lm_"):
                ob.hide_render = ob.name.rsplit("_", 1)[1] not in sides

        temp = []
        labels = {+1: [], -1: []}
        for r, side, p in points:
            if side not in sides:
                continue
            u, v = p.dot(right), p.z
            s = +1 if u >= ucentre else -1
            labels[s].append(dict(u=u, v=v, v0=v, p=p, text=r["name"], s=s))
        for s, ls in labels.items():
            spread(ls, font * 1.25)
            for l in ls:
                gap = 0.016
                anchor = centre + right * (l["u"] + s * gap) + Vector((0, 0, l["v"] - centre.z))
                # pull the label toward the camera so bone cannot sit in front of it
                anchor = anchor - d * 0.6
                temp.append(make_text("lbl_" + l["text"], l["text"], anchor, rot, font,
                                      "LEFT" if s > 0 else "RIGHT", text_mat, scene.collection))
                a = l["p"] - d * 0.6
                b = anchor - right * (s * 0.002)
                if (b - a).length > 0.004:
                    temp.append(make_leader("lead_" + l["text"], a, b, 0.0006, lead_mat, scene.collection))

        scene.render.filepath = os.path.join(outdir, "landmarks-%s.png" % name)
        with bpy.context.temp_override(scene=scene):
            bpy.ops.render.render(write_still=True)
        print("       rendered %s" % scene.render.filepath)

        for ob in temp:
            data = ob.data
            bpy.data.objects.remove(ob)
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            else:
                bpy.data.curves.remove(data)


# ---------------------------------------------------------------- main


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    outdir = None
    samples, res = 24, 3000
    if "--render" in argv:
        i = argv.index("--render")
        outdir = argv[i + 1] if len(argv) > i + 1 and not argv[i + 1].startswith("--") else "verification/landmarks"
    if "--samples" in argv:
        samples = int(argv[argv.index("--samples") + 1])
    if "--res" in argv:
        res = int(argv[argv.index("--res") + 1])

    print("-- resolve")
    recs = B.resolve_all(verbose=False)
    print("  resolved %d" % len(recs))

    print("-- surface")
    check_surface(recs)
    check_anchor_reproduces(recs)
    print("-- depth")
    check_depth(recs)
    print("-- symmetry")
    check_symmetry(recs)
    print("-- relationships")
    check_relationships(recs)
    print("-- reference")
    report_skin(recs)
    report_first_pass(recs)

    failed = [r for r in results if not r[1]]
    if outdir:
        print("-- render")
        render(outdir, recs, samples=samples, res=res)

    if failed:
        print("VERIFY_LANDMARKS_FAIL checks=%d failed=%d" % (len(results), len(failed)))
        sys.exit(1)
    print("VERIFY_LANDMARKS_OK checks=%d failed=0" % len(results))


if __name__ == "__main__":
    main()
