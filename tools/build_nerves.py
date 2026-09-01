"""Build the authored peripheral nerves as bezier tubes anchored to landmarks.

Run headless against the source model:

    blender -b source/Z-Anatomy/Startup.blend \
            --python tools/build_nerves.py -- nerves.glb nerves.json

Prints NERVES_OK built=20 and exits zero on success. A landmark that does not
resolve is a hard error, never a silent skip.

The geometry this produces is SCHEMATIC and is exported separately from any
model-derived geometry. It is never merged into them. See ATTRIBUTION.md.
"""

import bpy
import json
import os
import sys

from mathutils import Vector, geometry

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from nerve_paths import DEVIATIONS, NERVES  # noqa: E402

COLLECTION = "Peripheral nerves (authored)"

# Every authored object carries these. The viewer keys its "Schematic -
# indicative path only" treatment off them, so they are not decoration.
AUTHORED_PROPS = {"authored": True, "source": "schematic"}

# Samples per bezier segment when the centreline is written to nerves.json and
# when verification measures the path. Matches the curve resolution_u below.
RESOLUTION_U = 12


def anchor(name, uvw, off):
    """Resolve a waypoint to a world-space point.

    Normalised position within the landmark world bounding box, then a metric
    offset. Raises if the landmark is missing - a wrong or renamed landmark
    must stop the build rather than quietly shift a nerve.
    """
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise KeyError("Landmark not found: %s" % name)
    corners = [obj.matrix_world @ Vector(c[:]) for c in obj.bound_box]
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    p = Vector((lo.x + (hi.x - lo.x) * uvw[0],
                lo.y + (hi.y - lo.y) * uvw[1],
                lo.z + (hi.z - lo.z) * uvw[2]))
    return p + Vector(off)


def make_curve(nid, radius, pts):
    """A beveled bezier through pts, as a curve object named nid."""
    cu = bpy.data.curves.new(nid, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = RESOLUTION_U
    cu.bevel_depth = radius
    cu.bevel_resolution = 6
    cu.use_fill_caps = True

    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"

    ob = bpy.data.objects.new(nid, cu)
    for k, v in AUTHORED_PROPS.items():
        ob[k] = v
    return ob


def centreline(ob):
    """Sample the curve centreline in world space.

    Read back from the resolved AUTO handles rather than from the control
    points, so the samples are the path the tube actually follows.
    """
    sp = ob.data.splines[0]
    bps = list(sp.bezier_points)
    out = []
    for a, b in zip(bps, bps[1:]):
        seg = geometry.interpolate_bezier(
            a.co, a.handle_right, b.handle_left, b.co, RESOLUTION_U + 1)
        out.extend(seg[:-1])
    out.append(bps[-1].co)
    return [ob.matrix_world @ p for p in out]


def build(collection):
    """Build both sides of every nerve. Returns {nid: {...}} for nerves.json."""
    built = []
    record = {}

    for nid, spec in NERVES.items():
        pts = [anchor(*w) for w in spec["waypoints"]]

        left = make_curve(nid + ".l", spec["radius"], pts)
        # Mirror by negating X on the resolved points rather than by setting a
        # negative object scale: a negative scale inverts the winding order and
        # exports inside-out through glTF.
        right = make_curve(nid + ".r", spec["radius"],
                           [Vector((-p.x, p.y, p.z)) for p in pts])

        for ob in (left, right):
            collection.objects.link(ob)
            built.append(ob)

        record[nid] = {
            "radius": spec["radius"],
            "authored": AUTHORED_PROPS["authored"],
            "source": AUTHORED_PROPS["source"],
            "objects": [left.name, right.name],
            "waypoints": [
                {
                    "landmark": w[0],
                    "uvw": list(w[1]),
                    "offset": list(w[2]),
                    "resolved": [round(c, 5) for c in pts[i]],
                }
                for i, w in enumerate(spec["waypoints"])
            ],
        }

    # Handles are only resolved once the dependency graph has evaluated the
    # new curves, so the centrelines are read after this update.
    bpy.context.view_layer.update()
    for nid in record:
        left = bpy.data.objects[nid + ".l"]
        record[nid]["centreline"] = [[round(c, 5) for c in p] for p in centreline(left)]

    return built, record


def triangles(ob, depsgraph):
    """Triangle count of the evaluated (beveled) curve."""
    ev = ob.evaluated_get(depsgraph)
    me = ev.to_mesh()
    n = sum(max(len(p.vertices) - 2, 0) for p in me.polygons)
    ev.to_mesh_clear()
    return n


def isolate(collection):
    """Unlink everything except the authored nerves, so the glTF export cannot
    pick up model-derived geometry even by accident."""
    scene = bpy.context.scene
    for child in list(scene.collection.children):
        if child is not collection:
            scene.collection.children.unlink(child)
    for ob in list(scene.collection.objects):
        scene.collection.objects.unlink(ob)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    glb_path = argv[0] if argv else "nerves.glb"
    json_path = argv[1] if len(argv) > 1 else "nerves.json"

    coll = bpy.data.collections.new(COLLECTION)
    bpy.context.scene.collection.children.link(coll)

    built, record = build(coll)

    depsgraph = bpy.context.evaluated_depsgraph_get()
    for nid in record:
        record[nid]["triangles"] = {
            name: triangles(bpy.data.objects[name], depsgraph)
            for name in record[nid]["objects"]
        }

    isolate(coll)

    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format="GLB",
        use_active_collection=True,
        export_apply=True,          # evaluate the curves to meshes
        export_extras=True,         # carries authored / source into glTF extras
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_yup=True,
    )

    total_tris = sum(sum(r["triangles"].values()) for r in record.values())
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "note": ("Schematic approximations. Authored from a written "
                     "specification, not derived from BodyParts3D, Z-Anatomy, "
                     "or any imaging or cadaveric data. Indicative paths only."),
            "deviations": [
                {"nerve": d[0], "kind": d[1], "what": d[2], "why": d[3]}
                for d in DEVIATIONS
            ],
            "units": "metres",
            "axes": "Z up (superior), +X left, -Y anterior",
            "objects": len(built),
            "triangles": total_tris,
            "nerves": record,
        }, f, indent=1)

    print("NERVES_OK built=%d triangles=%d glb=%s json=%s"
          % (len(built), total_tris, glb_path, json_path))


if __name__ == "__main__":
    main()
