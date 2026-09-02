"""Render the review images from the exported files.

    blender -b --factory-startup --python tools/render_export.py -- \
        [--manifest manifest.json] [--regions verification/regions] \
        [--samples verification/decimation] [--only knee,hip]

One 1600 px render per region, showing the region's own meshes at target
detail with its context dimmed, and one tile per decimation sample laid out
source / 50% / 12.5% / overview left to right. Everything is imported from
the .glb files, so what is reviewed is what was shipped - Draco decoding,
winding and extras included. Runs in a factory-startup Blender on purpose:
Cycles crashes syncing the baked meshes inside the export process.

Prints RENDER_OK with a count and exits non-zero if any render is missing.
"""

import argparse
import json
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import regions  # noqa: E402

t0 = time.time()


def log(msg):
    print("[%6.1fs] %s" % (time.time() - t0, msg))
    sys.stdout.flush()


SYSTEM_COLOUR = {
    "skeletal": (0.88, 0.86, 0.78, 1),
    "muscular": (0.62, 0.20, 0.16, 1),
    "articular": (0.55, 0.70, 0.85, 1),
    "insertion": (0.95, 0.75, 0.20, 1),
}
VIEW = Vector((0.55, -1.0, 0.30)).normalized()      # left-anterolateral, slightly above


def make_material(name, colour, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = colour
    bsdf.inputs["Roughness"].default_value = 0.65
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.blend_method = "BLEND"
        mat.show_transparent_back = False
    return mat


def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.view_settings.view_transform = "Standard"
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = 32
    s.cycles.use_denoising = False
    s.cycles.max_bounces = 4
    s.cycles.transparent_max_bounces = 32
    s.render.resolution_x = 1600
    s.render.resolution_y = 1600
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = "PNG"
    s.render.use_freestyle = False
    world = bpy.data.worlds.new("render_world")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.05, 0.06, 0.08, 1)
    bg.inputs["Strength"].default_value = 1.0
    s.world = world
    for nm, loc, energy in (("key", (2.0, -3.0, 3.0), 5.0),
                            ("fill", (-3.0, -1.5, 1.5), 2.5),
                            ("rim", (0.5, 3.0, 2.0), 2.0)):
        ld = bpy.data.lights.new("render_" + nm, "SUN")
        ld.energy = energy
        lo = bpy.data.objects.new("render_" + nm, ld)
        lo.location = loc
        lo.rotation_euler = (-Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        s.collection.objects.link(lo)
    cam_data = bpy.data.cameras.new("render_cam")
    cam_data.type = "ORTHO"
    cam_data.clip_end = 100
    cam = bpy.data.objects.new("render_cam", cam_data)
    s.collection.objects.link(cam)
    s.camera = cam
    s.render.use_stamp = True
    s.render.use_stamp_note = True
    for flag in ("date", "time", "render_time", "frame", "scene", "filename",
                 "memory", "camera", "lens", "marker", "hostname", "sequencer_strip"):
        setattr(s.render, "use_stamp_" + flag, False)
    s.render.stamp_font_size = 26
    mats = {k: make_material("render_" + k, c) for k, c in SYSTEM_COLOUR.items()}
    mats["context"] = make_material("render_context", (0.55, 0.58, 0.62, 1), alpha=0.14)
    return s, cam, mats


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [ob for ob in bpy.data.objects if ob not in before and ob.type == "MESH"]


def style(ob, mat):
    me = ob.data
    me.materials.clear()
    me.materials.append(mat)
    me.polygons.foreach_set("material_index", [0] * len(me.polygons))
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.update()


def bounds(objects):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in objects:
        mw = ob.matrix_world
        for c in ob.bound_box:
            p = mw @ Vector(c[:])
            lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
            hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
    return lo, hi


def shoot(scene, cam, path, centre, extent, note):
    cam.location = Vector(centre) + VIEW * 5.0
    cam.rotation_euler = (-VIEW).to_track_quat("-Z", "Y").to_euler()
    cam.data.ortho_scale = extent
    scene.render.stamp_note_text = note
    scene.render.filepath = os.path.abspath(path)
    bpy.ops.render.render(write_still=True)
    log("rendered %s" % path)


def remove(objects):
    for ob in objects:
        me = ob.data
        bpy.data.objects.remove(ob)
        if me.users == 0:
            bpy.data.meshes.remove(me)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="manifest.json")
    ap.add_argument("--regions", default=os.path.join("verification", "regions"))
    ap.add_argument("--samples", default=os.path.join("verification", "decimation"))
    ap.add_argument("--only", help="comma-separated region subset")
    ap.add_argument("--no-samples", action="store_true")
    args = ap.parse_args(argv)
    base = os.path.dirname(os.path.abspath(args.manifest))
    manifest = json.load(open(args.manifest, encoding="utf-8"))
    only = set(args.only.split(",")) if args.only else None

    scene, cam, mats = setup_scene()
    made = []

    os.makedirs(args.regions, exist_ok=True)
    for r in manifest["regions"]:
        if only and r["id"] not in only:
            continue
        obs = import_glb(os.path.join(base, r["file"]))
        own = []
        for ob in obs:
            if ob.get("context"):
                style(ob, mats["context"])
            else:
                style(ob, mats[ob.get("system", "muscular")])
                own.append(ob)
        lo, hi = bounds(own)
        extent = max(hi - lo) * 1.25 + 0.05
        out = os.path.join(args.regions, "%s.png" % r["id"])
        shoot(scene, cam, out, (lo + hi) / 2, extent,
              "%s: %d meshes, %d tris (50%% of %d); context dimmed, %d meshes %d tris" % (
                  r["id"], r["meshCount"], r["ownTriangles"], r["sourceTriangles"],
                  r["contextMeshCount"], r["contextTriangles"]))
        made.append(out)
        remove(obs)

    spath = os.path.join(base, "samples.glb")
    if not args.no_samples and os.path.exists(spath):
        os.makedirs(args.samples, exist_ok=True)
        # four tiers side by side: a wide frame, so each copy is large enough to judge
        scene.render.resolution_x = 2400
        scene.render.resolution_y = 800
        obs = import_glb(spath)
        groups = {}
        for ob in obs:
            groups.setdefault(ob["sourceName"], []).append(ob)
        right = VIEW.cross(Vector((0, 0, 1))).normalized()
        for name, group in groups.items():
            group.sort(key=lambda o: o["tier"])
            for ob in obs:
                ob.hide_render = ob["sourceName"] != name
            lo, hi = bounds([group[0]])
            step = max(hi - lo) * 1.15
            for ob in group:
                style(ob, mats[ob.get("system", "muscular")])
                ob.matrix_world = Matrix.Translation(right * (step * (ob["tier"] - 1.5)))
            labels = ", ".join("%s=%d" % (o["label"], o["triangles"]) for o in group)
            fn = name.replace(" ", "-").replace(".", "-").lower() + ".png"
            out = os.path.join(args.samples, fn)
            shoot(scene, cam, out, (lo + hi) / 2, step * 4.4,
                  "%s  |  left to right: %s" % (name, labels))
            made.append(out)
        remove(obs)

    missing = [p for p in made if not os.path.exists(p)]
    if missing:
        print("RENDER_FAIL missing=%d" % len(missing))
        sys.exit(1)
    print("RENDER_OK renders=%d" % len(made))


if __name__ == "__main__":
    main()
