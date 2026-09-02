# CLAUDE.md

Standing notes for work in this repository. [`README.md`](README.md) says what
is here; this file says what has bitten us and what is still owed.

## The model

Z-Anatomy `Startup.blend`, Blender **3.6.x** specifically — the file is
documented as incompatible with 4.5, and opening it in 4.x may appear to work
while silently dropping data. Metres, **Z up**, **+X left**, **−Y anterior**.
`.l` objects sit at +X, `.r` at −X. Full figures in
[`inventory-summary.md`](inventory-summary.md).

## Bounding-box axes are not anatomical axes

**Do not treat a normalised bounding-box coordinate as an anatomical direction.**
The model stands in an A-pose and most long bones are oblique in it, so a
bounding box is not aligned with the bone. Normalising against it conflates
*medial* with *proximal*:

- `Humerus.l` runs X=0.145 at the head to X=0.249 at the elbow. `u=0.55` at
  elbow height is **4 cm medial of the cubital fossa**, not in it.
- `Ulna.l` has the same problem in reverse — its box reaches X=0.203 only at the
  olecranon, while the shaft sits at X=0.228 or beyond.
- `Femur.l`, `Tibia.l` and `Fibula.l` are all oblique to a lesser degree.

Anchoring to landmark geometry is still the right pattern — it means paths
follow if the source model is ever updated — but **every waypoint must be
retargeted against the real cross-section of the surrounding bones at its own
height**, not placed by reading the bounding box. In practice that means
slicing the landmark's vertices near the target Z and looking at the actual X/Y
extent there, then measuring signed distance to the nearest bone surface.

Two things that cost time and are worth reusing:

- `BVHTree.find_nearest` returns an **unsigned** distance, so a point inside a
  bone reports a comfortable clearance. Determine inside/outside by **ray-cast
  parity**, not by the dot product with the surface normal — these meshes are
  not consistently wound, and the normal test silently reported everything as
  inside.
- Verify with exact triangle-level `BVHTree.overlap`, and treat proximity
  probes only as a search aid. See
  [`tools/verify_nerves.py`](tools/verify_nerves.py).

This was a defect in the job brief for the authored nerves rather than in the
geometry; the first pass was wrong in eleven places and most of them traced back
to it. All eleven are recorded in [`tools/nerve_paths.py`](tools/nerve_paths.py)
and carried into `nerves.json`.

## The model mirrors by negative scale and shares mesh data

**971 of the 2,054 kept musculoskeletal objects are the `.l` side of a pair
that shares one mesh datablock with its `.r` twin under a reflecting world
matrix (determinant −1).** Blender draws that correctly; a glTF export does
not. Either the exporter writes one mesh with two nodes, one of them under a
negative-scale transform that most viewers render inside-out, or a naive bake
carries the reflected winding into the file. `tools/export_regions.py` bakes
every object to world space and reverses the polygon winding wherever the
determinant is negative, so every node has an identity transform and both
sides wind outward. Verify winding in the exported file by **signed volume**
(bmesh `calc_volume(signed=True)` on the decoded mesh) — a mirrored pair
exported inside-out cannot have equal signed volumes — never by the viewport,
which does not cull backfaces, and never by dotting normals, per above.

Two related facts worth keeping:

- A mirror transform followed by a winding flip leaves the signed volume equal
  to the local-space one. Do not negate it again for mirrored objects — that
  double-flip silently "corrected" 199 meshes that were already right.
- A handful of closed meshes are wound inside-out in the atlas itself, on both
  sides (the acetabular labrum). The export flips those and names them in
  `manifest.json` under `geometry.windingCorrected`.

## The base meshes are cages

**1,201 kept objects carry Subdivision and Solidify modifiers, and the
inventory counted base meshes.** For most ligaments the base mesh is a cage of
a few triangles that only becomes a ligament once the modifiers run — the
anterior talofibular ligament is two triangles before them. Skeletal,
muscular and articular objects are therefore exported from the
viewport-evaluated mesh, and `sourceTriangles` in the manifest is that count;
`inventoryTriangles` is the base count the brief's budgets were written
against. Insertion patches are the exception and stay as flat base meshes:
their 0.5 mm Solidify skin would take 63,843 triangles to 931,484.

## Blender process notes

- **Cycles crashes (`ccl::create_mesh` access violation) rendering meshes
  baked in the export process.** Renders are made afterwards by
  `tools/render_export.py` in a factory-startup Blender that imports the
  exported `.glb` files — which is the better review anyway, since it shows
  what shipped.
- **The glTF exporter drops a few degenerate triangles.** Manifest counts are
  read back from each file's index accessors, not from the meshes handed to
  the exporter.
- The upstream `Regions of human body` division tags are wrong as well as
  incomplete on the left (left tarsal bones are filed under `Right foot`).
  `tools/regions.py` strips the side word from every division tag and takes
  the side from the name suffix only.

## Open debts

### The schematic honesty requirement is half done

The authored peripheral nerves are **schematic approximations, not
imaging-derived anatomy**, and rendered beside the model-derived muscles and
bones they look equally authoritative. Four things were required to keep that
distinction visible. Two exist; two do not.

**Done:**

- every authored object carries `authored = True` and `source = "schematic"`,
  exported into the glTF as node `extras` — verified on all 20 nodes
- they export to `nerves.glb` alone, never merged with model-derived geometry,
  and [`ATTRIBUTION.md`](ATTRIBUTION.md) records them as original work

**Owed — viewer work, does not exist yet:**

- a **distinct material** for authored geometry, so it does not read as
  equivalent to the model-derived meshes
- a visible label reading **"Schematic — indicative path only"** whenever a
  nerve is selected or the nerve layer is on

This was called non-negotiable when the nerves were commissioned, and it is
exactly the kind of requirement that gets quietly dropped for visual tidiness.
It is **owed, not done.** Do not close it out on the strength of the exported
flags alone — the flags are what the viewer keys off, not a substitute for the
treatment.

## Conventions

- Exports are **built locally, never committed** — `.blend`, archives and
  `*.glb` are gitignored. Records of what was built (`nerves.json`,
  `verification/*.png`, `inventory.csv`) are committed.
- Every headless script prints a machine-checkable line and exits non-zero on
  failure: `INVENTORY_OK`, `NERVES_OK`, `VERIFY_OK`. A missing landmark is a
  hard error, never a silent skip — a path must never quietly drift onto the
  wrong geometry.
- [`EXCLUSIONS.md`](EXCLUSIONS.md) is authoritative for licence exclusions and
  is meant to be enforced programmatically, not remembered.
