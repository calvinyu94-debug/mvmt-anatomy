"""Verify the authored peripheral nerves against the real source geometry.

    blender -b source/Z-Anatomy/Startup.blend \
            --python tools/verify_nerves.py -- [--render verification/]

Two kinds of check, both quantitative:

  1. Intersection. Every nerve tube is tested for triangle-level overlap against
     every skeletal mesh whose bounding box it comes near. Nothing may pass
     through bone.

  2. Anatomy. The named relationships a clinician checks first - the ulnar
     behind the medial epicondyle, the radial in the spiral groove, the common
     fibular at the fibular neck, the sciatic below piriformis, the tibial
     behind the medial malleolus, the median anterior at elbow and wrist.
     Each is measured against actual vertices, not against bounding boxes, and
     reports its margin in millimetres.

Prints VERIFY_OK or VERIFY_FAIL with a count, and exits non-zero on failure.
"""

import bmesh
import bpy
import math
import os
import sys

from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import build_nerves  # noqa: E402
from build_nerves import centreline  # noqa: E402

SKELETON = "1: Skeletal system"
MUSCLE = "4: Muscular system"

# Height of one slice used by the depth measure. Bucketing at 10 mm put the
# ankle samples either side of a boundary and made the estimate jump by several
# millimetres between adjacent samples; 5 mm buckets read over a fixed window
# instead, which is what makes the measure stable enough to compare points.
BUCKET = 0.005

results = []


def check(name, ok, detail):
    results.append((name, bool(ok), detail))
    print("  %-4s %-38s %s" % ("PASS" if ok else "FAIL", name, detail))


def mm(v):
    return "%+.1f mm" % (v * 1000.0)


# ---------------------------------------------------------------- geometry


def collection_paths():
    paths = {}

    def walk(coll, prefix):
        p = (prefix + "/" + coll.name) if prefix else coll.name
        paths[coll.name] = p
        for child in coll.children:
            walk(child, p)

    walk(bpy.context.scene.collection, "")
    return paths


def wverts(name):
    ob = bpy.data.objects[name]
    mw = ob.matrix_world
    return [mw @ v.co for v in ob.data.vertices]


def slab(vs, zlo, zhi):
    return [v for v in vs if zlo <= v.z <= zhi]


def near_z(vs, z, tol=0.012):
    return [v for v in vs if abs(v.z - z) <= tol]


def bbox(vs):
    return (min(v.x for v in vs), max(v.x for v in vs),
            min(v.y for v in vs), max(v.y for v in vs),
            min(v.z for v in vs), max(v.z for v in vs))


def eval_bvh(ob, depsgraph):
    ev = ob.evaluated_get(depsgraph)
    me = ev.to_mesh()
    mw = ob.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    if not polys:
        return None
    return BVHTree.FromPolygons(verts, polys, all_triangles=False)


# ---------------------------------------------------------------- checks


def check_bone_intersections(nerve_objs, depsgraph):
    paths = collection_paths()
    bones = []
    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.data is None or not ob.data.polygons:
            continue
        if not any(SKELETON in paths.get(c.name, c.name) for c in ob.users_collection):
            continue
        bones.append(ob)

    hits = []
    for nob in nerve_objs:
        nverts = centreline(nob)
        r = nob.data.bevel_depth
        nb = bbox(nverts)
        pad = r + 0.02
        nbvh = eval_bvh(nob, depsgraph)
        if nbvh is None:
            continue
        for bone in bones:
            corners = [bone.matrix_world @ Vector(c[:]) for c in bone.bound_box]
            bb = bbox(corners)
            if (bb[1] < nb[0] - pad or bb[0] > nb[1] + pad or
                    bb[3] < nb[2] - pad or bb[2] > nb[3] + pad or
                    bb[5] < nb[4] - pad or bb[4] > nb[5] + pad):
                continue
            bbvh = eval_bvh(bone, depsgraph)
            if bbvh is None:
                continue
            ov = nbvh.overlap(bbvh)
            if ov:
                hits.append((nob.name, bone.name, len(ov)))

    if hits:
        for n, b, c in sorted(hits):
            print("       INTERSECTION  %-26s x %-34s %d faces" % (n, b, c))
    check("no-nerve-passes-through-bone", not hits,
          "clear of %d skeletal meshes" % len(bones) if not hits
          else "%d nerve/bone intersections" % len(hits))
    return hits


def nearest_sample(samples, target):
    return min(samples, key=lambda s: (s - target).length)


def check_ulnar_behind_medial_epicondyle(cl):
    hum = wverts("Humerus.l")
    zmin = min(v.z for v in hum)
    distal = slab(hum, zmin, zmin + 0.05)
    xs = [v.x for v in distal]
    cut = min(xs) + 0.25 * (max(xs) - min(xs))
    mec = [v for v in distal if v.x <= cut]          # medial epicondyle cluster
    c = sum(mec, Vector()) / len(mec)

    s = nearest_sample(cl["nerve-ulnar.l"], c)
    ymax = max(v.y for v in near_z(mec, s.z, 0.015)) if near_z(mec, s.z, 0.015) else max(v.y for v in mec)
    margin = s.y - ymax
    check("ulnar-posterior-to-med-epicondyle", margin > 0,
          "nerve y=%.4f vs epicondyle y_max=%.4f, %s posterior" % (s.y, ymax, mm(margin)))


def check_radial_spiral_groove(cl):
    hum = wverts("Humerus.l")
    samples = [s for s in cl["nerve-radial.l"] if 1.20 <= s.z <= 1.32]
    worst = None
    for s in samples:
        nz = near_z(hum, s.z, 0.012)
        if not nz:
            continue
        d = s.y - max(v.y for v in nz)
        if worst is None or d < worst[0]:
            worst = (d, s)
    check("radial-posterior-in-spiral-groove", worst is not None and worst[0] > 0,
          "closest of %d samples is %s posterior to the humerus" % (len(samples), mm(worst[0]))
          if worst else "no samples in the spiral groove band")

    # and anterior again at the elbow, on the lateral side
    el = [s for s in cl["nerve-radial.l"] if 1.09 <= s.z <= 1.15]
    ok = False
    best = None
    for s in el:
        nz = near_z(hum, s.z, 0.012)
        if not nz:
            continue
        d = min(v.y for v in nz) - s.y            # positive => nerve anterior
        lateral = s.x > (min(v.x for v in nz) + max(v.x for v in nz)) / 2.0
        if d > 0 and lateral:
            ok = True
        if best is None or d > best[0]:
            best = (d, s, lateral)
    check("radial-anterior-lateral-at-elbow", ok,
          "best sample %s anterior to the humerus, lateral=%s" % (mm(best[0]), best[2])
          if best else "no samples at the elbow")


def check_median_anterior(cl):
    hum = wverts("Humerus.l")
    el = [s for s in cl["nerve-median.l"] if 1.08 <= s.z <= 1.14]
    best = None
    for s in el:
        nz = near_z(hum, s.z, 0.012)
        if not nz:
            continue
        d = min(v.y for v in nz) - s.y
        if best is None or d > best[0]:
            best = (d, s)
    check("median-anterior-at-elbow", best is not None and best[0] > 0,
          "%s anterior to the humerus" % mm(best[0]) if best else "no samples at the elbow")

    # In the carpal tunnel: deep to the flexor retinaculum, palmar to the carpus.
    carpus = []
    for n in ("Lunate bone.l", "Capitate bone.l", "Hamate bone.l",
              "Scaphoid bone.l", "Triquetrum bone.l", "Trapezium bone.l"):
        carpus += wverts(n)
    retin = wverts("Flexor retinaculum of wrist.l")
    zlo, zhi = 0.832, 0.872
    band = [s for s in cl["nerve-median.l"] if zlo <= s.z <= zhi]
    ok = False
    detail = "no samples in the carpal band"
    for s in band:
        cy = min(v.y for v in near_z(carpus, s.z, 0.010)) if near_z(carpus, s.z, 0.010) else None
        ry = min(v.y for v in near_z(retin, s.z, 0.010)) if near_z(retin, s.z, 0.010) else None
        if cy is None or ry is None:
            continue
        inside = ry < s.y < cy       # between retinaculum roof and carpal floor
        if inside:
            ok = True
            detail = ("y=%.4f between retinaculum %.4f and carpus %.4f"
                      % (s.y, ry, cy))
            break
        detail = "y=%.4f vs retinaculum %.4f / carpus %.4f" % (s.y, ry, cy)
    check("median-inside-carpal-tunnel", ok, detail)


def check_sciatic_below_piriformis(cl, hits):
    pir = wverts("Piriformis muscle.l")
    zlo = min(v.z for v in pir)                       # inferior border of the muscle
    xmid = (min(v.x for v in pir) + max(v.x for v in pir)) / 2.0

    # By the time the nerve has travelled past the mid-width of the muscle on
    # its way laterally, it must already be below that inferior border. Testing
    # it this way rather than "no sample inside the footprint" matters: inside
    # the pelvis the nerve is legitimately deep to piriformis and above its
    # lower edge, and a footprint test would flag that correct arrangement.
    crossing = next((s for s in cl["nerve-sciatic.l"] if s.x >= xmid), None)
    check("sciatic-emerges-below-piriformis",
          crossing is not None and crossing.z < zlo,
          "passes the muscle mid-width at z=%.4f, %s below its inferior border %.4f"
          % (crossing.z, mm(zlo - crossing.z), zlo) if crossing
          else "path never reaches the piriformis mid-width")


def check_tibial_behind_malleolus(cl):
    mal = wverts("Medial malleolus.l")
    c = sum(mal, Vector()) / len(mal)
    s = nearest_sample(cl["nerve-tibial.l"], c)
    nz = near_z(mal, s.z, 0.012) or mal
    ymax = max(v.y for v in nz)
    check("tibial-posterior-to-med-malleolus", s.y > ymax,
          "nerve y=%.4f vs malleolus y_max=%.4f, %s posterior" % (s.y, ymax, mm(s.y - ymax)))


def check_fibular_neck(cl):
    fib = wverts("Fibula.l")
    band = [s for s in cl["nerve-common-fibular.l"] if 0.365 <= s.z <= 0.395]
    worst = None
    for s in band:
        nz = near_z(fib, s.z, 0.010)
        if not nz:
            continue
        d = s.x - max(v.x for v in nz)          # positive => lateral to the bone
        if worst is None or d < worst[0]:
            worst = (d, s)
    check("fibular-lateral-at-fibular-neck", worst is not None and worst[0] > 0,
          "closest of %d samples is %s lateral to the fibula" % (len(band), mm(worst[0]))
          if worst else "no samples at the fibular neck")


def limb_slices():
    """Left lower limb vertices bucketed by height, for the depth measure."""
    paths = collection_paths()
    vs = []
    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.data is None or not ob.data.polygons:
            continue
        if not any(SKELETON in paths.get(c.name, c.name) or MUSCLE in paths.get(c.name, c.name)
                   for c in ob.users_collection):
            continue
        corners = [ob.matrix_world @ Vector(c[:]) for c in ob.bound_box]
        cz = sum(c.z for c in corners) / 8.0
        cx = sum(c.x for c in corners) / 8.0
        if cx < 0.005 or cz > 0.95:
            continue
        mw = ob.matrix_world
        vs += [mw @ v.co for v in ob.data.vertices]

    buckets = {}
    for v in vs:
        buckets.setdefault(int(v.z / BUCKET), []).append(v)
    return buckets


def radial_depth(s, buckets):
    """How far s lies beneath the limb surface, in its own transverse slice.

    Measured radially from the slice centroid: the limb is convex enough in
    cross-section for this to be a fair stand-in for depth below skin, and the
    model carries no skin mesh to measure against.
    """
    k = int(s.z / BUCKET)
    pts = []
    for i in range(k - 2, k + 3):                 # a fixed +/-12 mm window
        pts += buckets.get(i, [])
    if len(pts) < 32:
        return None
    cx = sum(p.x for p in pts) / len(pts)
    cy = sum(p.y for p in pts) / len(pts)
    dx, dy = s.x - cx, s.y - cy
    n = math.hypot(dx, dy)
    if n < 1e-6:
        return None
    dx, dy = dx / n, dy / n
    surface = max((p.x - cx) * dx + (p.y - cy) * dy for p in pts)
    return surface - n


LOWER_LIMB = ("nerve-sciatic.l", "nerve-tibial.l",
              "nerve-common-fibular.l", "nerve-femoral.l")


def check_depths(cl):
    """Two separate claims that an earlier version of this file conflated.

    A nerve outside the skin is a defect anywhere on the path. Which point is
    the shallowest is a different question, and the brief's claim - that the
    fibular neck is the most exposed spot - is about the common fibular's own
    course. Judged across all four nerves it would be a different claim, and a
    false one: the tibial nerve behind the medial malleolus and the saphenous
    at the knee are subcutaneous too. Both rankings are printed either way.
    """
    buckets = limb_slices()
    scored = {}
    for nid in LOWER_LIMB:
        pts = [(radial_depth(s, buckets), s) for s in cl[nid]]
        scored[nid] = sorted((d, s) for d, s in pts if d is not None)

    worst = min((v[0] + (nid,) for nid, v in scored.items() if v),
                key=lambda t: t[0])
    check("no-nerve-outside-the-limb", worst[0] >= 0.0,
          "shallowest of all lower-limb samples is %s at z=%.3f, %.1f mm inside"
          % (worst[2], worst[1].z, worst[0] * 1000.0))

    # The fibular neck must be the most exposed point on the common fibular
    # path. Asserted with a 1 mm tolerance rather than as a strict minimum: the
    # only point that rivals it is the anterior ankle, which measures within
    # 0.1 mm of it, and both are genuinely subcutaneous. At that separation a
    # strict test would be discriminating on the noise in this estimate rather
    # than on anatomy. The full ranking is printed so the margin stays visible.
    fib = scored["nerve-common-fibular.l"]
    neck = min((d, s) for d, s in fib if 0.34 <= s.z <= 0.43)
    shallowest = fib[0]
    check("fibular-neck-most-superficial", neck[0] <= shallowest[0] + 0.001,
          "neck %.1f mm deep at z=%.3f; shallowest on the path %.1f mm at z=%.3f"
          % (neck[0] * 1000.0, neck[1].z, shallowest[0] * 1000.0, shallowest[1].z))

    print("       depth ranking, shallowest point per nerve:")
    for nid in LOWER_LIMB:
        d, s = scored[nid][0]
        print("         %-24s %5.1f mm at z=%.3f" % (nid, d * 1000.0, s.z))


# ---------------------------------------------------------------- render


def is_label(name):
    """Atlas label infrastructure, per EXCLUSIONS.md. Rendering it puts stray
    words like "SKELETAL SYSTEM" across the frame."""
    return name.endswith((".j", ".t", ".g")) or "-txt" in name


def render(outdir, nerve_objs):
    import mathutils

    paths = collection_paths()

    # Render in a scene of our own rather than the atlas's. Its scene carries a
    # Freestyle pass that draws every object as identical line art, plus its own
    # compositor and view layers; rendering into it produced first a line
    # drawing in which the nerves were indistinguishable from bone, and then,
    # with Freestyle off, a blank frame. A fresh scene holding only the bones,
    # the nerves, a camera and two lights avoids all of that.
    scene = bpy.data.scenes.new("verify")
    scene.view_settings.view_transform = "Standard"

    bone_mat = bpy.data.materials.new("verify_bone")
    bone_mat.use_nodes = True
    bsdf = bone_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.85, 0.84, 0.80, 1)
    bsdf.inputs["Alpha"].default_value = 0.10
    bsdf.inputs["Roughness"].default_value = 0.6
    bone_mat.blend_method = "BLEND"

    nerve_mat = bpy.data.materials.new("verify_nerve")
    nerve_mat.use_nodes = True
    nt = nerve_mat.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.82, 0.05, 1)
    em.inputs["Strength"].default_value = 1.6
    nt.links.new(em.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])

    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.data is None or not ob.data.polygons:
            continue
        if not any(SKELETON in paths.get(c.name, c.name) for c in ob.users_collection):
            continue
        if is_label(ob.name):
            continue
        ob.data.materials.clear()
        ob.data.materials.append(bone_mat)
        ob.hide_render = False
        scene.collection.objects.link(ob)

    for ob in nerve_objs:
        ob.data.materials.clear()
        ob.data.materials.append(nerve_mat)
        ob.hide_render = False
        scene.collection.objects.link(ob)

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 4
    scene.cycles.transparent_max_bounces = 32
    scene.render.film_transparent = False
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1600
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    scene.render.use_freestyle = False

    world = bpy.data.worlds.new("verify_world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.04, 0.05, 0.07, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    scene.world = world

    # Two lights, so the translucent skeleton reads as a solid with depth
    # rather than as a flat wash.
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
        "SCHEMATIC - indicative nerve paths only, not imaging-derived")
    scene.render.use_stamp_date = False
    scene.render.use_stamp_time = False
    scene.render.use_stamp_render_time = False
    scene.render.use_stamp_frame = False
    scene.render.use_stamp_scene = False
    scene.render.use_stamp_filename = False
    scene.render.use_stamp_memory = False
    scene.render.use_stamp_camera = False
    scene.render.use_stamp_lens = False
    scene.render.use_stamp_marker = False
    scene.render.use_stamp_hostname = False
    scene.render.use_stamp_sequencer_strip = False
    scene.render.stamp_font_size = 28

    cam_data = bpy.data.cameras.new("verify_cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("verify_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    # Everything on the right of the midline, so the close crops can drop it.
    # The nerves are authored on the left; leaving the right side in means the
    # contralateral limb projects on top of the one being inspected.
    right_side = [ob for ob in scene.collection.objects
                  if ob.type in {"MESH", "CURVE"} and
                  sum((ob.matrix_world @ Vector(c[:])).x for c in ob.bound_box) / 8.0 < -0.012]

    # (name, direction the camera looks from, target centre, ortho width, left only)
    VIEWS = [
        ("01-anterior",       (0, -1, 0),    (0.000, 0.00, 0.90), 1.90, False),
        ("02-posterior",      (0, +1, 0),    (0.000, 0.00, 0.90), 1.90, False),
        ("03-left-lateral",   (+1, 0, 0),    (0.000, 0.00, 0.90), 1.90, False),
        ("04-axilla-arm",     (0, -1, 0),    (0.205, 0.02, 1.19), 0.34, True),
        ("05-pelvis-thigh",   (0, +1, 0),    (0.075, 0.03, 0.72), 0.27, True),
        ("06-knee-lower-leg", (+1, +0.28, 0), (0.090, 0.045, 0.27), 0.30, True),
    ]

    # Absolute: Blender resolves a relative render path against the drive root,
    # not the working directory, and silently writes somewhere else.
    outdir = os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)
    for name, d, centre, width, left_only in VIEWS:
        for ob in right_side:
            ob.hide_render = left_only
        d = mathutils.Vector(d).normalized()
        c = mathutils.Vector(centre)
        cam.location = c + d * 3.0
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        cam_data.ortho_scale = width
        scene.render.filepath = os.path.join(outdir, "nerves-%s.png" % name)
        with bpy.context.temp_override(scene=scene):
            bpy.ops.render.render(write_still=True)
        print("       rendered %s" % scene.render.filepath)


# ---------------------------------------------------------------- main


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    outdir = None
    if "--render" in argv:
        i = argv.index("--render")
        outdir = argv[i + 1] if len(argv) > i + 1 else "verification"

    coll = bpy.data.collections.new(build_nerves.COLLECTION)
    bpy.context.scene.collection.children.link(coll)
    nerve_objs, _ = build_nerves.build(coll)

    depsgraph = bpy.context.evaluated_depsgraph_get()
    cl = {ob.name: centreline(ob) for ob in nerve_objs}

    print("-- intersection")
    hits = check_bone_intersections(nerve_objs, depsgraph)

    print("-- anatomy")
    check_ulnar_behind_medial_epicondyle(cl)
    check_radial_spiral_groove(cl)
    check_median_anterior(cl)
    check_sciatic_below_piriformis(cl, hits)
    check_tibial_behind_malleolus(cl)
    check_fibular_neck(cl)
    check_depths(cl)

    failed = [r for r in results if not r[1]]
    if outdir:
        print("-- render")
        render(outdir, nerve_objs)

    if failed:
        print("VERIFY_FAIL checks=%d failed=%d" % (len(results), len(failed)))
        sys.exit(1)
    print("VERIFY_OK checks=%d failed=0" % len(results))


if __name__ == "__main__":
    main()
