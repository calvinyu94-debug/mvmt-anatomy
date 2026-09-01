import bpy, csv, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = argv[0] if argv else "inventory.csv"

# Full collection paths, e.g. "Scene Collection/Muscles/Upper limb"
paths = {}
def walk(coll, prefix):
    p = (prefix + "/" + coll.name) if prefix else coll.name
    paths[coll.name] = p
    for child in coll.children:
        walk(child, p)
walk(bpy.context.scene.collection, "")

rows = []
for obj in bpy.data.objects:
    colls = [paths.get(c.name, c.name) for c in obj.users_collection]

    tris = verts = 0
    if obj.type == "MESH" and obj.data is not None:
        me = obj.data
        verts = len(me.vertices)
        # Cheaper than calc_loop_triangles() across thousands of objects
        tris = sum(max(len(p.vertices) - 2, 0) for p in me.polygons)

    corners = [obj.matrix_world @ Vector(c[:]) for c in obj.bound_box]
    xs = [c.x for c in corners]; ys = [c.y for c in corners]; zs = [c.z for c in corners]
    cx = sum(xs) / 8.0; cy = sum(ys) / 8.0; cz = sum(zs) / 8.0

    rows.append({
        "object_name":     obj.name,
        "object_type":     obj.type,
        "collection_path": colls[0] if colls else "",
        "all_collections": " | ".join(colls),
        "parent":          obj.parent.name if obj.parent else "",
        "triangles":       tris,
        "vertices":        verts,
        "material":        obj.material_slots[0].name if obj.material_slots else "",
        "hide_viewport":   int(obj.hide_viewport),
        "bbox_min_x": round(min(xs), 4), "bbox_min_y": round(min(ys), 4), "bbox_min_z": round(min(zs), 4),
        "bbox_max_x": round(max(xs), 4), "bbox_max_y": round(max(ys), 4), "bbox_max_z": round(max(zs), 4),
        "centroid_x": round(cx, 4), "centroid_y": round(cy, 4), "centroid_z": round(cz, 4),
    })

rows.sort(key=lambda r: (r["collection_path"], r["object_name"]))

with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

meshes = [r for r in rows if r["object_type"] == "MESH"]
total_tris = sum(r["triangles"] for r in meshes)
print("INVENTORY_OK objects=%d meshes=%d triangles=%d out=%s"
      % (len(rows), len(meshes), total_tris, out_path))
