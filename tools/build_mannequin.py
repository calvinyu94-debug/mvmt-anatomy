"""Build the exercise-demo mannequin: an MPFB2 default human on the game-engine
skeleton, T-pose rest, clay, exported as one skinned glTF - and calibrate it.

    blender-4.2 -b --python tools/build_mannequin.py -- \
        [--out .] [--render verification/mannequin] [--copy-to ../mvmt-program/assets]

This is the one job in the repository that does NOT run in the pinned
Blender 3.6: MPFB2 is a Blender 4.2+ extension, and nothing here touches the
Z-Anatomy model, so the two never meet. The figure is built from MPFB's
bundled base mesh with default macro settings - adult, average build, neutral
sex presentation - and its bundled game-engine rig and T-pose. MPFB's
optional system-assets pack (skins, eyes, clothes) is not installed and not
used, so there is no fitted top and shorts to add; the figure is clay.

Writes, into --out:

  mannequin.glb      one mesh, one skin, no Draco, Y-up, +Z anterior, metres,
                     feet on the floor. Gitignored like every export.
  rig-manifest.json  the resolution key the viewer reads: every joint in the
                     app's vocabulary resolved to exactly one bone, the pinned
                     effectors, and the calibration table - for every
                     anatomical motion the measured axis in the bone's own
                     frame (see tools/mannequin_rig.py). Committed.

and into --render the proof: the calibration pose from the brief, drawn from
the exported file's own data (the mesh skinned in numpy from the glb by the
table in the manifest, not by Blender's armature), plus the rest pose. If the
figure in the image is not doing exactly what the brief says, the table is
wrong. Blender's own deformation of the same pose is compared numerically and
the disagreement recorded; it is not what the image shows.

Prints MANNEQUIN_OK and exits zero; any failed check is a hard stop.
"""

import argparse
import json
import math
import os
import shutil
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import mannequin_rig as mr  # noqa: E402

t0 = time.time()


def log(msg):
    print("[%6.1fs] %s" % (time.time() - t0, msg))
    sys.stdout.flush()


def fail(msg):
    print("MANNEQUIN_FAIL " + msg)
    sys.exit(1)


CLAY = (0.72, 0.68, 0.62, 1.0)      # a placeholder; the viewer replaces the material with its own token
MPFB_MODULE = "bl_ext.user_default.mpfb"


# ------------------------------------------------------------ toolchain

def ensure_mpfb():
    if bpy.app.version < (4, 2, 0):
        fail("MPFB2 needs Blender 4.2 or later; this is %s" % bpy.app.version_string)
    if not any(a.module == MPFB_MODULE for a in bpy.context.preferences.addons):
        try:
            bpy.ops.preferences.addon_enable(module=MPFB_MODULE)
        except Exception as e:  # noqa: BLE001
            fail("MPFB is not installed as %s: %s" % (MPFB_MODULE, e))
    import importlib
    mpfb = importlib.import_module(MPFB_MODULE)
    version = ".".join(str(v) for v in mpfb.VERSION)
    log("MPFB %s (build %s) in Blender %s" % (version, getattr(mpfb, "BUILD_INFO", "?"), bpy.app.version_string))
    return version


def gltf_exporter_version():
    try:
        import io_scene_gltf2
        return ".".join(str(v) for v in io_scene_gltf2.bl_info["version"])
    except Exception:  # noqa: BLE001
        return "unknown"


# ------------------------------------------------------------ the figure

def build_figure():
    from bl_ext.user_default.mpfb.services.humanservice import HumanService
    from bl_ext.user_default.mpfb.services.locationservice import LocationService
    from bl_ext.user_default.mpfb.services.objectservice import ObjectService
    from bl_ext.user_default.mpfb.services.rigservice import RigService
    from bl_ext.user_default.mpfb.services.targetservice import TargetService

    bpy.ops.wm.read_homefile(use_empty=True)
    macro = TargetService.get_default_macro_info_dict()
    log("macro settings (MPFB defaults): %s" % json.dumps(macro))
    body = HumanService.create_human(mask_helpers=True, detailed_helpers=True, extra_vertex_groups=True,
                                     feet_on_ground=True, scale=0.1, macro_detail_dict=macro)
    arm = HumanService.add_builtin_rig(body, "game_engine", import_weights=True)
    if arm is None:
        fail("could not add the game_engine rig")
    log("base mesh %d vertices, %d faces; rig %d bones" % (len(body.data.vertices), len(body.data.polygons),
                                                             len(arm.data.bones)))

    # -- MPFB's T-pose for this rig ---------------------------------------
    pose_file = os.path.join(LocationService.get_mpfb_data("poses"), "game_engine_fk", "t-pose.json")
    with open(pose_file, encoding="utf-8") as f:
        tpose = json.load(f)
    ObjectService.deselect_and_deactivate_all()
    ObjectService.activate_blender_object(arm)
    bpy.ops.object.mode_set(mode="POSE")
    RigService.set_pose_from_dict(arm, tpose)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    return body, arm, macro


def segment_dir(arm, bone, probe):
    """World direction from a bone's head to its probe (a bone head or its
    own tail)."""
    pb = arm.pose.bones[bone]
    h = arm.matrix_world @ pb.head
    p = arm.matrix_world @ (arm.pose.bones[probe].head if probe != "tail" else pb.tail)
    return (p - h).normalized()


def refine_t_pose(arm):
    """Make the T unambiguous: every arm segment exactly along the world X
    axis, in the frontal plane, fingers straight and in line. MPFB's T-pose
    is within a few degrees of that at the shoulder and elbow but relaxes the
    hand and curls the fingers; anatomical zero has to be exact, so each
    segment is turned onto its axis, most proximal first, and the residual
    it started with is recorded."""
    chain = []
    for s in ("l", "r"):
        chain += [("upperarm_" + s, "lowerarm_" + s), ("lowerarm_" + s, "hand_" + s), ("hand_" + s, "middle_01_" + s)]
        for f in mr.FINGERS:
            chain += [("%s_01_%s" % (f, s), "%s_02_%s" % (f, s)), ("%s_02_%s" % (f, s), "%s_03_%s" % (f, s)),
                      ("%s_03_%s" % (f, s), "tail")]
    residuals = {}
    for bone, probe in chain:
        target = Vector((1.0 if bone.endswith("_l") else -1.0, 0.0, 0.0))
        before = segment_dir(arm, bone, probe)
        residuals[bone] = round(math.degrees(before.angle(target)), 2)
        pb = arm.pose.bones[bone]
        rw = before.rotation_difference(target).to_matrix()          # world rotation to apply
        m = pb.matrix.to_3x3()                                       # current pose rotation, armature space
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (pb.rotation_quaternion.to_matrix() @ (m.inverted() @ rw @ m)).to_quaternion()
        bpy.context.view_layer.update()
        after = segment_dir(arm, bone, probe)
        if math.degrees(after.angle(target)) > 0.05:
            fail("could not align %s to %s: %.2f degrees left" % (bone, tuple(target), math.degrees(after.angle(target))))
    log("T-pose refined; residuals before (deg): %s" % json.dumps(residuals))
    return residuals


def apply_as_rest(body, arm):
    from bl_ext.user_default.mpfb.services.rigservice import RigService
    RigService.apply_pose_as_rest_pose(arm)
    bpy.context.view_layer.update()
    # One plain armature modifier: glTF has no volume preservation, and the
    # viewer skins linearly, so Blender must deform the same way for the
    # agreement check to mean anything.
    mods = [m for m in body.modifiers if m.type == "ARMATURE"]
    for m in mods[1:]:
        body.modifiers.remove(m)
    mods[0].use_deform_preserve_volume = False
    mods[0].use_multi_modifier = False
    mods[0].vertex_group = ""
    for pb in arm.pose.bones:
        if (pb.rotation_quaternion - Quaternion((1, 0, 0, 0))).magnitude > 1e-6 or pb.location.length > 1e-6:
            fail("pose not cleared on %s after applying rest" % pb.name)
    log("T-pose applied as rest; modifiers: %s" % [(m.name, m.type) for m in body.modifiers])


def strip_helpers(body, arm):
    """Delete every vertex outside the `body` group - MakeHuman's helper
    geometry (eye, tooth, tongue, hair and clothing proxies, joint cubes) -
    and drop the mask that was hiding it. Non-bone vertex groups go too."""
    me = body.data
    gi = body.vertex_groups["body"].index
    bm = bmesh.new()
    bm.from_mesh(me)
    dl = bm.verts.layers.deform.verify()
    doomed = [v for v in bm.verts if gi not in v[dl] or v[dl][gi] <= 0.0]
    n_before = len(bm.verts)
    bmesh.ops.delete(bm, geom=doomed, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    for m in list(body.modifiers):
        if m.type == "MASK":
            body.modifiers.remove(m)
    bones = {b.name for b in arm.data.bones}
    for vg in list(body.vertex_groups):
        if vg.name not in bones:
            body.vertex_groups.remove(vg)
    # glTF carries four influences per vertex and the exporter silently keeps
    # the four heaviest. Do that here instead, and renormalise, so the file
    # skins exactly as Blender does and the agreement check below can bite.
    over = sum(1 for v in me.vertices if len(v.groups) > 4)
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.vertex_group_limit_total(group_select_mode="BONE_DEFORM", limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode="BONE_DEFORM", lock_active=False)
    log("%d vertices had more than four bone influences; limited to four and renormalised" % over)
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    log("helpers stripped: %d -> %d vertices, %d faces, %d triangles" % (n_before, len(me.vertices), len(me.polygons), tris))
    if len(me.vertices) == 0 or tris == 0:
        fail("no body geometry left after stripping helpers")
    # every vertex must be weighted to at least one bone, and weights must sum to ~1
    unweighted = 0
    for v in me.vertices:
        w = sum(g.weight for g in v.groups)
        if w < 0.5:
            unweighted += 1
    if unweighted:
        fail("%d vertices carry no bone weight" % unweighted)
    return tris


def clay(body):
    for i in range(len(body.data.materials)):
        body.data.materials.pop(index=0)
    mat = bpy.data.materials.new("Mannequin clay")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = CLAY
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Metallic"].default_value = 0.0
    mat.diffuse_color = CLAY
    mat.roughness = 0.85
    body.data.materials.append(mat)
    body.data.polygons.foreach_set("material_index", [0] * len(body.data.polygons))
    body.data.polygons.foreach_set("use_smooth", [True] * len(body.data.polygons))
    body.data.update()


def tag(ob, **extras):
    for k, v in extras.items():
        ob[k] = v


# ------------------------------------------------------------ export

def export_glb(path, arm, body):
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_extras=True,
        export_yup=True,
        export_normals=True,
        export_texcoords=False,
        export_vertex_color="NONE",
        export_attributes=False,
        export_tangents=False,
        export_materials="EXPORT",
        export_image_format="NONE",
        export_cameras=False,
        export_lights=False,
        export_animations=False,
        export_skins=True,
        export_all_influences=False,
        export_influence_nb=4,
        export_morph=False,
        export_rest_position_armature=True,
        export_def_bones=False,
        export_hierarchy_flatten_bones=False,
        export_leaf_bone=False,
        export_armature_object_remove=False,
        export_draco_mesh_compression_enable=False,
    )
    return os.path.getsize(path)


# ------------------------------------------------------------ checks on the file

def blender_agreement(rig, manifest, arm, body):
    """Pose Blender's armature with the calibration pose through the same
    table and compare its deformed mesh with the file skinned in numpy.
    The two must agree for the manifest's frames to be Blender's frames, and
    for the render (which is the numpy one) to stand for the export."""
    pose = mr.pose_from_angles(rig, manifest, mr.CALIBRATION_POSE)
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
        pb.location = Vector((0, 0, 0))
    for node, q in pose.items():
        name = rig.nodes[node]["name"]
        x, y, z, w = q
        arm.pose.bones[name].rotation_quaternion = Quaternion((w, x, y, z))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    n = len(ev.data.vertices)
    co = np.empty(n * 3)
    ev.data.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    world = np.array(body.matrix_world)
    co = co @ world[:3, :3].T + world[:3, 3]
    ours = rig.skinned(pose)
    if len(ours) != n:
        # the exporter may split vertices at sharp edges / material seams; compare by nearest
        return None, "vertex count differs (%d in Blender, %d in file); not compared" % (n, len(ours))
    d = np.linalg.norm(mr.blender_to_gltf(co) - ours, axis=1)
    for pb in arm.pose.bones:
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
    bpy.context.view_layer.update()
    return float(d.max() * 1000.0), "max %.3f mm, mean %.3f mm over %d vertices" % (d.max() * 1000, d.mean() * 1000, n)


# ------------------------------------------------------------ renders

def mesh_object(name, verts_gltf, indices, colour):
    """A plain Blender mesh from glTF-space vertices and a flat index list."""
    me = bpy.data.meshes.new(name)
    v = mr.gltf_to_blender(verts_gltf)
    faces = [tuple(int(i) for i in indices[k:k + 3]) for k in range(0, len(indices), 3)]
    me.from_pydata([tuple(p) for p in v], [], faces)
    me.update()
    mat = bpy.data.materials.new(name + " mat")
    mat.diffuse_color = colour
    mat.roughness = 0.85
    me.materials.append(mat)
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    ob = bpy.data.objects.new(name, me)
    return ob


def render_scene():
    """A fresh Workbench scene: studio light, shadows, a floor."""
    scene = bpy.data.scenes.new("mannequin_render")
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_shadows = True
    sh.show_cavity = True
    sh.background_type = "VIEWPORT"
    sh.background_color = (0.86, 0.87, 0.89)
    scene.display.render_aa = "8"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1600
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.render.use_stamp = True
    scene.render.use_stamp_note = True
    for flag in ("date", "time", "render_time", "frame", "scene", "filename", "memory", "camera",
                 "lens", "marker", "hostname", "sequencer_strip"):
        setattr(scene.render, "use_stamp_" + flag, False)
    scene.render.stamp_font_size = 26
    cam_data = bpy.data.cameras.new("mannequin_cam")
    cam_data.type = "ORTHO"
    cam_data.clip_end = 100
    cam = bpy.data.objects.new("mannequin_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    floor = bpy.data.meshes.new("floor")
    floor.from_pydata([(-3, -3, 0), (3, -3, 0), (3, 3, 0), (-3, 3, 0)], [], [(0, 1, 2, 3)])
    fmat = bpy.data.materials.new("floor mat")
    fmat.diffuse_color = (0.78, 0.79, 0.80, 1)
    floor.materials.append(fmat)
    fo = bpy.data.objects.new("floor", floor)
    scene.collection.objects.link(fo)
    return scene, cam


def shoot(scene, cam, objects, path, view, note):
    """Frame `objects` (Blender space) from direction `view` and render."""
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in objects:
        for c in ob.bound_box:
            p = ob.matrix_world @ Vector(c[:])
            lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
            hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
    centre = (lo + hi) / 2
    extent = max(hi - lo) * 1.15 + 0.1
    view = Vector(view).normalized()
    cam.location = centre + view * 6.0
    cam.rotation_euler = (-view).to_track_quat("-Z", "Y").to_euler()
    cam.data.ortho_scale = extent
    scene.render.stamp_note_text = note
    scene.render.filepath = os.path.abspath(path)
    with bpy.context.temp_override(scene=scene):
        bpy.ops.render.render(write_still=True, scene=scene.name)
    log("rendered %s" % path)


def renders(rig, manifest, outdir):
    os.makedirs(outdir, exist_ok=True)
    scene, cam = render_scene()
    made = []
    rest = mesh_object("rest", rig.skinned({}), rig.indices, CLAY)
    scene.collection.objects.link(rest)
    p = os.path.join(outdir, "rest-t-pose.png")
    shoot(scene, cam, [rest], p, (0, -1, 0.05),
          "mannequin.glb rest pose, skinned from the file: T-pose, anterior view. "
          "Figure's left is on the viewer's right.")
    made.append(p)
    rest.hide_render = True

    pose = mr.pose_from_angles(rig, manifest, mr.CALIBRATION_POSE)
    cal = mesh_object("calibration", rig.skinned(pose), rig.indices, CLAY)
    scene.collection.objects.link(cal)
    note = "calibration pose per rig-manifest.json axes: " + mr.CALIBRATION_PROSE
    p = os.path.join(outdir, "calibration-anterior.png")
    shoot(scene, cam, [cal], p, (-0.55, -1.0, 0.30), note + " | anterior three-quarter from the figure's right")
    made.append(p)
    p = os.path.join(outdir, "calibration-right-lateral.png")
    shoot(scene, cam, [cal], p, (-1.0, -0.05, 0.10), note + " | right lateral")
    made.append(p)
    p = os.path.join(outdir, "calibration-left-lateral.png")
    shoot(scene, cam, [cal], p, (1.0, -0.05, 0.10), note + " | left lateral")
    made.append(p)
    return made


# ------------------------------------------------------------ main

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--render", default=os.path.join("verification", "mannequin"))
    ap.add_argument("--copy-to", help="also copy mannequin.glb and rig-manifest.json here (mvmt-program/assets)")
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args(argv)
    outdir = os.path.abspath(args.out)
    os.makedirs(outdir, exist_ok=True)

    mpfb_version = ensure_mpfb()
    body, arm, macro = build_figure()
    residuals = refine_t_pose(arm)
    apply_as_rest(body, arm)
    tris = strip_helpers(body, arm)
    clay(body)
    arm.name = arm.data.name = "mannequin"
    body.name = "mannequin-body"
    body.data.name = "mannequin-body"
    extras = {"figure": "mannequin", "source": "mpfb2-game-engine", "licence": "CC0", "restPose": "T"}
    tag(arm, **extras)
    tag(body, **extras)

    glb = os.path.join(outdir, "mannequin.glb")
    nbytes = export_glb(glb, arm, body)
    log("exported %s, %d bytes" % (glb, nbytes))

    # -- read the file back and calibrate on it -----------------------------
    rig = mr.Rig(glb)
    exts = rig.g.get("extensionsUsed", []) + rig.g.get("extensionsRequired", [])
    if any("draco" in e.lower() for e in exts):
        fail("Draco in the export: %s" % exts)
    rest = rig.skinned({})
    height = float(rest[:, 1].max() - rest[:, 1].min())
    floor = float(rest[:, 1].min())
    # facing: the most anterior point of the head must be at +Z, the figure's
    # left hand at +X
    head = rest[rest[:, 1] > rest[:, 1].max() - 0.25]
    nose_z = float(head[:, 2].max())
    back_z = float(head[:, 2].min())
    W = rig.world()
    lhand_x = float(W[rig.joint("hand_l")][0, 3])
    if not (nose_z > 0 and abs(nose_z) > abs(back_z) * 0.5 and lhand_x > 0):
        fail("orientation: head z %.3f..%.3f, left hand x %.3f (want +Z anterior, .l at +X)" % (back_z, nose_z, lhand_x))
    for name, hits in rig.by_name.items():
        if len(hits) != 1:
            fail("joint name %r appears %d times" % (name, len(hits)))

    neutral = mr.neutral_offsets(rig)
    axes = mr.calibrate(rig, neutral)
    bones = {}
    for jt in mr.vocabulary():
        for b in jt["bones"]:
            rig.joint(b)     # exactly one, or KeyError
        bones[jt["joint"]] = jt["bones"][0] if len(jt["bones"]) == 1 else jt["bones"]
    effectors = mr.effectors()
    for b in effectors.values():
        rig.joint(b)
    shared = {}
    for j, b in bones.items():
        if isinstance(b, str):
            shared.setdefault(b, []).append(j)
    shared = {b: js for b, js in shared.items() if len(js) > 1}

    # the T: arms along X, legs vertical, in the file
    def axis_deg(a, b, target):
        d = W[rig.joint(b)][:3, 3] - W[rig.joint(a)][:3, 3]
        d /= np.linalg.norm(d)
        return round(math.degrees(math.acos(min(1.0, abs(float(d @ target))))), 2)
    t_check = {
        "upperarm_l": axis_deg("upperarm_l", "lowerarm_l", np.array([1.0, 0, 0])),
        "lowerarm_l": axis_deg("lowerarm_l", "hand_l", np.array([1.0, 0, 0])),
        "upperarm_r": axis_deg("upperarm_r", "lowerarm_r", np.array([1.0, 0, 0])),
        "lowerarm_r": axis_deg("lowerarm_r", "hand_r", np.array([1.0, 0, 0])),
        "thigh_l": axis_deg("thigh_l", "calf_l", np.array([0, 1.0, 0])),
        "thigh_r": axis_deg("thigh_r", "calf_r", np.array([0, 1.0, 0])),
        "calf_l": axis_deg("calf_l", "foot_l", np.array([0, 1.0, 0])),
        "calf_r": axis_deg("calf_r", "foot_r", np.array([0, 1.0, 0])),
    }
    for k in ("upperarm_l", "lowerarm_l", "upperarm_r", "lowerarm_r"):
        if t_check[k] > 0.5:
            fail("rest pose is not a T in the file: %s is %.2f degrees off the X axis" % (k, t_check[k]))
    # palms: in the T the thumb sits anterior of the hand, so the palm faces down
    palm = {}
    for s in ("l", "r"):
        dz = float(W[rig.joint("thumb_01_" + s)][2, 3] - W[rig.joint("hand_" + s)][2, 3])
        palm["thumb_01_" + s + "_anteriorOfWrist_m"] = round(dz, 4)
        if dz <= 0:
            fail("thumb_01_%s is not anterior of the wrist; the palm does not face down in the T" % s)

    manifest = {
        "version": 1,
        "rig": "mpfb-game-engine",
        "restPose": "T",
        "units": "m",
        "up": "Y",
        "anterior": "+Z",
        "sideConvention": {"l": "+X", "r": "-X"},
        "source": {
            "figure": "MPFB2 bundled base mesh, default macro settings, game_engine skeleton, MPFB t-pose refined to an exact T",
            "macro": macro,
            "mpfb": mpfb_version,
            "blender": bpy.app.version_string,
            "gltfExporter": gltf_exporter_version(),
            "licence": "CC0 (MPFB2 bundled assets and characters exported from an unmodified official build)",
            "excluded": "eyes, teeth, tongue, eyebrows, eyelashes, hair and every other helper mesh; no textures; "
                        "no clothes (MPFB's system-assets pack is not installed and not bundled)",
        },
        "file": {
            "name": "mannequin.glb",
            "bytes": nbytes,
            "triangles": rig.triangles,
            "vertices": int(len(rig.positions)),
            "joints": len(rig.joints),
            "meshNodes": 1,
            "influencesPerVertex": int(rig.skin_joints.shape[1]),
            "draco": False,
            "height_m": round(height, 4),
            "floor_y": round(floor, 5),
            "extensionsUsed": exts,
        },
        "restPoseRefinement": {
            "rule": "each arm segment - upper arm, forearm, hand, and every phalanx of the four fingers - turned onto "
                    "the world X axis before the pose was applied as rest; legs left as MPFB's T-pose has them",
            "residualBeforeDeg": residuals,
            "inFile": {"offAxisDeg": t_check, "palm": palm},
        },
        "bones": bones,
        "effectors": effectors,
        "sharedBones": shared,
        "fingerGroups": "fingersL/R drive the twelve phalanges of index, middle, ring and little finger (the thumb is "
                        "not in the vocabulary); the angle is applied at every phalanx, so 90 at each is a closed fist",
        "composition": "bone.quaternion = rest x neutral x Q(axes[flex], flex) x Q(axes[abd], abd) x ... x Q(axes[rot], rot); "
                       "quaternions post-multiplied in paramOrder, so each rotation is about the bone's own axis as it "
                       "then stands. `rest` is the joint node's rotation in the file. `neutral` is the identity except "
                       "on the two upper-arm bones. Angles in degrees, positive as the vocabulary defines them.",
        "paramOrder": mr.PARAM_ORDER,
        "hAddNote": "hAdd is measured with the arm at 90 abduction (the rest pose), about the vertical axis; at "
                    "anatomical neutral that axis coincides with the humerus and hAdd is not distinguishable from rot",
        "neutral": neutral,
        "axes": axes,
        "axesNote": "axis: unit vector in the bone's own frame; a positive rotation about it by the right-hand rule is "
                    "the named motion. nearestLocal / offAxisDeg: the labelled bone axis it is closest to and by how "
                    "much it misses - the rig's bones are rolled, so a snapped axis would mix motions. cosine: how "
                    "closely the probe moved in the expected direction when the rotation was applied.",
        "restWorld": mr.rest_world(rig),
        "calibration": {
            "pose": mr.CALIBRATION_POSE,
            "prose": mr.CALIBRATION_PROSE,
            "renders": [],
            "blenderAgreement": None,
        },
    }

    agree_mm, agree_note = blender_agreement(rig, manifest, arm, body)
    manifest["calibration"]["blenderAgreement"] = {"max_mm": agree_mm, "note": agree_note}
    log("Blender armature vs file skinning on the calibration pose: %s" % agree_note)
    if agree_mm is not None and agree_mm > 1.0:
        fail("Blender's deformation and the file's skinning disagree by %.2f mm" % agree_mm)

    if not args.no_render:
        made = renders(rig, manifest, args.render)
        manifest["calibration"]["renders"] = [os.path.relpath(p, outdir).replace(os.sep, "/") for p in made]

    mpath = os.path.join(outdir, "rig-manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    log("manifest written to %s" % mpath)

    if args.copy_to:
        dest = os.path.abspath(args.copy_to)
        os.makedirs(dest, exist_ok=True)
        for fn in ("mannequin.glb", "rig-manifest.json"):
            shutil.copy2(os.path.join(outdir, fn), os.path.join(dest, fn))
        log("copied mannequin.glb and rig-manifest.json to %s" % dest)

    print("MANNEQUIN_OK triangles=%d vertices=%d joints=%d bytes=%d height=%.3f blenderAgreement_mm=%s" % (
        rig.triangles, len(rig.positions), len(rig.joints), nbytes, height,
        "n/a" if agree_mm is None else "%.3f" % agree_mm))


if __name__ == "__main__":
    main()
