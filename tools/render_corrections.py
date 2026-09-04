"""Render the corrected geometry for review, from the exported files.

    blender -b --factory-startup --python tools/render_corrections.py -- \
        [--glb ankle-foot.glb] [--corrections corrections.json] \
        [--before <previously shipped ankle-foot.glb>] [--out verification/corrections]

Right ankle, lateral and posterior orthographic views: fibula, talus and
calcaneus in bone, the anterior and posterior talofibular ligaments in the
articular colour for context, and the calcaneofibular ligament lit in orange.
Everything is imported from the exported .glb, so what is reviewed is what
shipped; the fibula is the knee region's context copy, at context detail,
because that is what the ankle-foot file carries. With --before the same
views are rendered from an earlier export for comparison.

Prints RENDER_CORRECTIONS_OK with a count and exits non-zero if any render
is missing.
"""

import argparse
import json
import os
import sys

import bpy
from mathutils import Vector

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import render_export as R  # noqa: E402

KEEP = ["Fibula.r", "Talus.r", "Calcaneus.r",
        "Calcaneofibular ligament.r", "Anterior talofibular ligament.r", "Posterior talofibular ligament.r"]
FRAME_ON = ["Talus.r", "Calcaneus.r", "Calcaneofibular ligament.r",
            "Anterior talofibular ligament.r", "Posterior talofibular ligament.r"]
LIT = "Calcaneofibular ligament.r"

# direction from the subject toward the camera
VIEWS = [("lateral", Vector((-1.0, 0.0, 0.0))),
         ("posterior", Vector((0.0, 1.0, 0.0)))]
UP = Vector((0.0, 0.0, 1.0))


def aim_lights(scene, d):
    """Re-point the three suns for a view: key over the camera's shoulder,
    fill from the other side, rim from behind the subject."""
    side = d.cross(UP).normalized()
    for nm, v in (("key", d + UP * 0.6 + side * 0.5),
                  ("fill", d - side * 0.8 + UP * 0.1),
                  ("rim", -d + UP * 0.8)):
        lo = bpy.data.objects["render_" + nm]
        lo.rotation_euler = (-v.normalized()).to_track_quat("-Z", "Y").to_euler()


def shoot(scene, cam, path, centre, extent, d, note):
    aim_lights(scene, d)
    cam.location = Vector(centre) + d * 5.0
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam.data.ortho_scale = extent
    scene.render.stamp_note_text = note
    scene.render.filepath = os.path.abspath(path)
    bpy.ops.render.render(write_still=True)
    R.log("rendered %s" % path)


def render_file(scene, cam, mats, glb, outdir, suffix, note):
    obs = R.import_glb(glb)
    keep = {}
    for ob in obs:
        if ob.name in KEEP:
            keep[ob.name] = ob
    missing = [n for n in KEEP if n not in keep]
    if missing:
        raise SystemExit("%s: missing %s" % (glb, missing))
    R.remove([ob for ob in obs if ob.name not in keep])
    for n, ob in keep.items():
        if n == LIT:
            R.style(ob, mats["lit"])
        else:
            R.style(ob, mats[ob.get("system", "articular")])
    lo, hi = R.bounds([keep[n] for n in FRAME_ON])
    extent = max(hi - lo) * 1.5 + 0.01
    made = []
    for label, d in VIEWS:
        out = os.path.join(outdir, "cfl-right-%s%s.png" % (label, suffix))
        shoot(scene, cam, out, (lo + hi) / 2, extent, d,
              "%s | right ankle, %s | %s" % (os.path.basename(glb), label, note))
        made.append(out)
    R.remove(list(keep.values()))
    return made


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", default="ankle-foot.glb")
    ap.add_argument("--corrections", default="corrections.json")
    ap.add_argument("--before")
    ap.add_argument("--out", default=os.path.join("verification", "corrections"))
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    note = "calcaneofibular ligament redrawn by rule"
    if os.path.exists(args.corrections):
        rec = next(o for o in json.load(open(args.corrections, encoding="utf-8"))["objects"]
                   if o["object"] == LIT)
        f, c = rec["fibularEnd"]["point"], rec["calcanealEnd"]["point"]
        note = ("CFL redrawn: fibular end (%.4f %.4f %.4f), calcaneal end (%.4f %.4f %.4f), %.1f mm"
                % (f[0], f[1], f[2], c[0], c[1], c[2], rec["length"] * 1000))

    scene, cam, mats = R.setup_scene()
    mats["lit"] = R.make_material("render_lit", (0.93, 0.45, 0.12, 1))
    made = render_file(scene, cam, mats, args.glb, args.out, "", note)
    if args.before:
        made += render_file(scene, cam, mats, args.before, args.out, "-before", "before: source placeholder quad")

    missing = [p for p in made if not os.path.exists(p)]
    if missing:
        print("RENDER_CORRECTIONS_FAIL missing=%d" % len(missing))
        sys.exit(1)
    print("RENDER_CORRECTIONS_OK renders=%d" % len(made))


if __name__ == "__main__":
    main()
