"""Verify mannequin.glb and rig-manifest.json by reading the shipped file
back - in a fresh Blender, without MPFB, and mostly without Blender at all.

    blender-4.2 -b --factory-startup --python tools/verify_mannequin.py -- \
        [--glb mannequin.glb] [--manifest rig-manifest.json] \
        [--overview overview.glb] [--render verification/mannequin] [--no-render]

Three layers:

  1. The file, parsed directly: one mesh, one skin, four influences, no Draco,
     no required extensions; every bone the manifest names resolves to
     exactly one joint; the skinned rest mesh stands on the floor, faces +Z,
     has its left hand at +X, and is a T to within half a degree.

  2. The calibration, re-derived from the file with tools/mannequin_rig.py
     and compared with what the manifest holds - the same rules, run again,
     must give the same axes. Then the brief's calibration pose is applied
     through the manifest's own composition rule and MEASURED: the right
     thigh must point anterior and level, the shin straight down, the left
     forearm forward, the head turned 45 to the right, the right hand bent
     45 away from the palm. This is the render's claim checked in numbers.

  3. Blender's importer: the file imports as one armature and one mesh, and
     is rendered beside overview.glb (the Z-Anatomy whole body, if the path
     exists) so scale, facing and stance can be compared by eye.

Prints VERIFY_MANNEQUIN_OK or VERIFY_MANNEQUIN_FAIL and exits non-zero on any
failure.
"""

import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import mannequin_rig as mr  # noqa: E402

results = []


def check(name, ok, detail):
    results.append((name, bool(ok), detail))
    print("  %-4s %-40s %s" % ("PASS" if ok else "FAIL", name, detail))
    sys.stdout.flush()


def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def deg(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, float(unit(a) @ unit(b))))))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", default="mannequin.glb")
    ap.add_argument("--manifest", default="rig-manifest.json")
    ap.add_argument("--overview", default="overview.glb")
    ap.add_argument("--render", default=os.path.join("verification", "mannequin"))
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args(argv)

    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)

    # ---- 1. the file ------------------------------------------------------
    try:
        rig = mr.Rig(args.glb)
        check("file-structure", True, "one mesh node, one skin, one primitive, %d joints" % len(rig.joints))
    except Exception as e:  # noqa: BLE001
        check("file-structure", False, str(e))
        print("VERIFY_MANNEQUIN_FAIL checks=%d failed=1" % len(results))
        sys.exit(1)
    exts = rig.g.get("extensionsUsed", []) + rig.g.get("extensionsRequired", [])
    check("no-draco-no-required-extensions", not exts, "extensions: %s" % (exts or "none"))
    check("four-influences", rig.skin_joints.shape[1] == 4 and "JOINTS_1" not in rig.g["meshes"][0]["primitives"][0]["attributes"],
          "%d per vertex" % rig.skin_joints.shape[1])
    nbytes = os.path.getsize(args.glb)
    check("size-and-count-recorded", manifest["file"]["bytes"] == nbytes and manifest["file"]["triangles"] == rig.triangles,
          "%d bytes, %d triangles (manifest says %d, %d)" % (nbytes, rig.triangles, manifest["file"]["bytes"],
                                                           manifest["file"]["triangles"]))
    print("  note triangles %d: the brief's target was roughly 20-40k" % rig.triangles)

    dup = [n for n, hits in rig.by_name.items() if len(hits) != 1]
    check("joint-names-unique", not dup, "duplicates: %s" % (dup or "none"))
    bad = []
    for joint, names in manifest["bones"].items():
        for n in ([names] if isinstance(names, str) else names):
            if len(rig.by_name.get(n, [])) != 1:
                bad.append("%s->%s" % (joint, n))
    for eff, n in manifest["effectors"].items():
        if len(rig.by_name.get(n, [])) != 1:
            bad.append("%s->%s" % (eff, n))
    check("every-key-resolves-to-one-bone", not bad, "unresolved: %s" % (bad or "none"))
    vocab = {jt["joint"]: jt for jt in mr.vocabulary()}
    missing = [j for j in vocab if j not in manifest["bones"] or j not in manifest["axes"]]
    extra = [j for j in manifest["bones"] if j not in vocab]
    check("vocabulary-complete", not missing and not extra, "missing %s, extra %s" % (missing or "none", extra or "none"))
    bad = []
    for j, jt in vocab.items():
        for p in jt["params"]:
            if p not in manifest["axes"].get(j, {}):
                bad.append("%s.%s" % (j, p))
    check("every-parameter-calibrated", not bad, "missing: %s" % (bad or "none"))

    rest = rig.skinned({})
    W = rig.world()
    height = float(rest[:, 1].max() - rest[:, 1].min())
    floor = float(rest[:, 1].min())
    check("stands-on-floor", abs(floor) < 0.01 and 1.5 < height < 1.9,
          "lowest vertex y %.4f m, height %.3f m" % (floor, height))
    head = rest[rest[:, 1] > rest[:, 1].max() - 0.25]
    nose_z, back_z = float(head[:, 2].max()), float(head[:, 2].min())
    check("faces-+Z", nose_z > 0 and nose_z > -back_z, "head z from %.3f to %.3f" % (back_z, nose_z))
    lhx = float(W[rig.joint("hand_l")][0, 3])
    rhx = float(W[rig.joint("hand_r")][0, 3])
    check("left-at-+X", lhx > 0 > rhx, "hand_l x %.3f, hand_r x %.3f" % (lhx, rhx))

    def seg(a, b):
        return W[rig.joint(b)][:3, 3] - W[rig.joint(a)][:3, 3]
    worst = max(deg(seg("upperarm_l", "lowerarm_l"), [1, 0, 0]), deg(seg("lowerarm_l", "hand_l"), [1, 0, 0]),
                deg(seg("upperarm_r", "lowerarm_r"), [-1, 0, 0]), deg(seg("lowerarm_r", "hand_r"), [-1, 0, 0]))
    check("rest-is-a-T", worst < 0.5, "arm segments within %.2f degrees of the X axis" % worst)
    thumb = min(float(W[rig.joint("thumb_01_" + s)][2, 3] - W[rig.joint("hand_" + s)][2, 3]) for s in ("l", "r"))
    check("palms-down-in-T", thumb > 0, "thumb_01 at least %.1f mm anterior of the wrist" % (thumb * 1000))

    # ---- 2. the calibration -----------------------------------------------
    neutral = mr.neutral_offsets(rig)
    same = all(deg(neutral[b]["axis"], manifest["neutral"][b]["axis"]) < 0.1 and neutral[b]["deg"] == manifest["neutral"][b]["deg"]
               for b in manifest["neutral"]) and set(neutral) == set(manifest["neutral"])
    check("neutral-reproduces", same, "%s" % sorted(neutral))
    try:
        axes = mr.calibrate(rig, manifest["neutral"])
        worst = 0.0
        n = 0
        for j, entry in axes.items():
            for p, v in entry.items():
                pairs = [(v, manifest["axes"][j][p])] if "axis" in v else [
                    (v["bones"][b], manifest["axes"][j][p]["bones"][b]) for b in v["bones"]]
                for a, m in pairs:
                    worst = max(worst, deg(a["axis"], m["axis"]))
                    n += 1
        check("axes-reproduce", worst < 0.1, "%d axes re-derived from the file, worst %.3f degrees from the manifest" % (n, worst))
    except Exception as e:  # noqa: BLE001
        check("axes-reproduce", False, str(e))
    rw = mr.rest_world(rig)
    worst = max(np.linalg.norm(np.array(rw[b]["position"]) - np.array(manifest["restWorld"][b]["position"]))
                for b in manifest["restWorld"])
    check("rest-world-reproduces", worst < 1e-4, "worst %.2f mm" % (worst * 1000))

    # the brief's pose, measured
    pose = mr.pose_from_angles(rig, manifest, mr.CALIBRATION_POSE)
    P = rig.world(pose)

    def pseg(a, b):
        return P[rig.joint(b)][:3, 3] - P[rig.joint(a)][:3, 3]
    # Angles are anatomical degrees FROM REST, and the rest leg is MPFB's
    # straight leg, whose bone chain is not a straight line: the thigh bone
    # leans a few degrees anterior and the calf a few posterior, so the knee
    # joint sits in front of the hip-ankle line. Flexion is therefore checked
    # as the change from rest, and the chain's own offsets are reported.
    thigh0, thigh = seg("thigh_r", "calf_r"), pseg("thigh_r", "calf_r")
    swept = deg(thigh0, thigh)
    check("cal-right-hip-flexed-90", abs(swept - 90) < 1.0 and float(unit(thigh)[2]) > 0.9 and abs(float(unit(thigh)[0])) < 0.15,
          "right thigh swept %.1f degrees from rest, now %.1f above anterior-horizontal (rest lean %.1f)" % (
              swept, math.degrees(math.asin(float(unit(thigh)[1]))), deg(thigh0, [0, -1, 0])))
    shin0, shin = seg("calf_r", "foot_r"), pseg("calf_r", "foot_r")
    bent0, bent = deg(thigh0, shin0), deg(thigh, shin)      # 0 = segments collinear
    check("cal-right-knee-flexed-90", abs((bent - bent0) - 90) < 1.0,
          "knee bent %.1f degrees more than at rest (rest chain bend %.1f, so the shin is %.1f from vertical)" % (
              bent - bent0, bent0, deg(shin, [0, -1, 0])))
    ua = pseg("upperarm_l", "lowerarm_l")
    check("cal-left-shoulder-abducted-90", deg(ua, [1, 0, 0]) < 1.0, "left upper arm %.1f degrees from lateral" % deg(ua, [1, 0, 0]))
    fa = pseg("lowerarm_l", "hand_l")
    check("cal-left-elbow-flexed-90", abs(deg(ua, fa) - 90) < 1.0 and deg(fa, [0, 0, 1]) < 3.0,
          "left forearm %.1f degrees from the upper arm, %.1f from anterior" % (deg(ua, fa), deg(fa, [0, 0, 1])))
    # head: the face direction is the head node's rest-anterior vector carried by the pose
    Rr = W[rig.joint("head")][:3, :3]
    Rp = P[rig.joint("head")][:3, :3]
    face = Rp @ (Rr.T @ np.array([0, 0, 1.0]))
    turn = math.degrees(math.atan2(-face[0], face[2]))         # positive = toward the figure's right (-X)
    check("cal-neck-rotated-45-right", abs(turn - 45) < 2.0, "face turned %.1f degrees toward the right" % turn)
    # right arm at the side, wrist extended: the hand bends away from the palm (laterally, -X for the right)
    fr = pseg("lowerarm_r", "hand_r")
    hand = pseg("hand_r", "middle_01_r")
    bend = deg(fr, hand)
    lateral = float(unit(hand)[0]) < -0.5
    check("cal-right-wrist-extended-45", abs(bend - 45) < 2.0 and lateral,
          "hand %.1f degrees off the forearm, %s" % (bend, "away from the palm (lateral)" if lateral else "toward the palm"))
    # everything else stayed put
    still = max(np.linalg.norm(P[rig.joint(b)][:3, 3] - W[rig.joint(b)][:3, 3] - (
        P[rig.joint("thigh_l")][:3, 3] - W[rig.joint("thigh_l")][:3, 3])) for b in ("thigh_l", "calf_l", "foot_l"))
    check("cal-left-leg-unmoved", still < 1e-6, "left leg joints moved %.3f mm" % (still * 1000))

    # ---- 3. Blender's importer ---------------------------------------------
    try:
        import bpy
        from mathutils import Vector
        import build_mannequin as bm
        bpy.ops.wm.read_factory_settings(use_empty=True)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=os.path.abspath(args.glb))
        new = [o for o in bpy.data.objects if o not in before]
        arms = [o for o in new if o.type == "ARMATURE"]
        # the importer also creates an unlinked "Icosphere" to display bones with; a
        # figure mesh is one that is skinned
        meshes = [o for o in new if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
        shapes = [o.name for o in new if o.type == "MESH" and o not in meshes]
        new = arms + meshes
        check("blender-imports", len(arms) == 1 and len(meshes) == 1,
              "%d armature(s), %d skinned mesh(es): %s; bone-shape helpers %s" % (
                  len(arms), len(meshes), [o.name for o in new], shapes or "none"))
        if meshes:
            bpy.context.view_layer.update()
            me = meshes[0]
            zs = [(me.matrix_world @ Vector(c[:])).z for c in me.bound_box]
            check("blender-height", abs((max(zs) - min(zs)) - height) < 0.01,
                  "imported figure %.3f m tall, lowest point z %.4f" % (max(zs) - min(zs), min(zs)))
            bad = [n for n in manifest["restWorld"] if n not in arms[0].data.bones] if arms else ["no armature"]
            check("blender-bones-named", not bad, "missing: %s" % (bad or "none"))
        if not args.no_render:
            os.makedirs(args.render, exist_ok=True)
            scene, cam = bm.render_scene()
            for o in new:
                scene.collection.objects.link(o)
            for o in meshes:
                for m in o.data.materials:
                    if m:
                        m.diffuse_color = bm.CLAY
            shown = list(meshes)
            note = "mannequin.glb through Blender's glTF importer"
            if os.path.exists(args.overview):
                before = set(bpy.data.objects)
                bpy.ops.import_scene.gltf(filepath=os.path.abspath(args.overview))
                ov = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
                mat = bpy.data.materials.new("overview mat")
                mat.diffuse_color = (0.86, 0.84, 0.76, 1)
                for o in ov:
                    scene.collection.objects.link(o)
                    o.data.materials.clear()
                    o.data.materials.append(mat)
                    o.data.polygons.foreach_set("material_index", [0] * len(o.data.polygons))
                    o.location.x -= 0.9
                zs = []
                for o in ov:
                    zs += [(o.matrix_world @ Vector(c[:])).z for c in o.bound_box]
                note += " beside overview.glb (Z-Anatomy, %d meshes, %.2f m tall, lowest point z %.3f)" % (
                    len(ov), max(zs) - min(zs), min(zs))
                shown += ov
                print("  note overview: %d meshes, z from %.3f to %.3f; mannequin height %.3f" % (
                    len(ov), min(zs), max(zs), height))
            else:
                note += " (overview.glb not found at %s, rendered alone)" % args.overview
            out = os.path.join(args.render, "beside-overview.png")
            bm.shoot(scene, cam, shown, out, (-0.55, -1.0, 0.25), note)
            check("render-beside-overview", os.path.exists(out), out)
    except Exception as e:  # noqa: BLE001
        check("blender-import", False, "%s: %s" % (type(e).__name__, e))

    failed = sum(1 for _, ok, _ in results if not ok)
    if failed:
        print("VERIFY_MANNEQUIN_FAIL checks=%d failed=%d" % (len(results), failed))
        sys.exit(1)
    print("VERIFY_MANNEQUIN_OK checks=%d failed=0" % len(results))


if __name__ == "__main__":
    main()
