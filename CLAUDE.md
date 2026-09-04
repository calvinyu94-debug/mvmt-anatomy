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

The landmark job hit the same trap harder, and answered it differently: the
42 landmarks in [`tools/landmark_anchors.py`](tools/landmark_anchors.py) are
**rules on the bone's real vertices** ("the most lateral femoral vertex",
"the most anterior vertex in the top 3 mm of the manubrium's midline"), and
`uvw` is computed from the rule's result, never authored. The brief's
first-pass `uvw` values landed a median 19 mm from the rule's point, 78 mm at
worst (the ASIS: the hip bone's box corner is nowhere near the bone), inside
the bone four times, and on the wrong structure three times - the centre of
the tibial plateau for the joint line, the medial epicondyle for the adductor
tubercle, the opisthocranion for the inion. Every one is kept in
`landmarks.json` under `firstPass`.

Those last three are a **different failure class from a wrong coordinate**,
and it is worth keeping the two apart. A wrong coordinate is a right
description read off the wrong axis: the fix is a different number, or a rule
that reads the geometry instead. A wrong structure is a wrong *description* -
"the plateau centre" is the intercondylar eminence, "the femur's medial
extreme" is the epicondyle, "the most posterior occipital point" is the
opisthocranion - and no amount of retargeting fixes it, because the number
faithfully found what was asked for. The fix is a different description,
which is what the rules for those three now encode. Keep this pattern for
anything similar: write the anatomical description as an executable rule on
the geometry, so the description is what gets reviewed and the landmarks
regenerate if the model changes.

## World axes are not anatomical axes either

The model is in an A-pose. The forearm leans ~16 degrees, so the radial
styloid sits **higher** than the ulnar in world Z while being correctly
distal along the forearm. Any proximal / distal, medial / lateral or
anterior / posterior assertion must be measured along the relevant anatomical
axis, not a world axis. A world-axis check can fail a correct result - and,
just as quietly, pass a wrong one. `verify_landmarks.forearm_axis` is the
pattern: derive the axis from the bone's own ends, then project.

## Things the landmark job learned about the bones

- **Five anchor bones carry loose vertices** that belong to no face: sacrum
  21, scapula 25, fibula 19, atlas 13, occipital 4, manubrium 3. A rule that
  picks one returns a point on no surface; the sacral base first came out
  7 mm off the bone that way. `build_landmarks.bvh_for` returns only
  face-referenced vertices.
- **`Atlas (C1)` and `Mandible` are single unsided objects.** The brief named
  `Atlas (C1).l` and `Mandible.l`, which do not exist. Left-side rules on them
  select `x > 0`; the right is still the mirror.
- **"Distal" is not "lower Z" on the forearm.** The A-pose forearm leans 16
  degrees; in world Z the radial styloid is 0.7 mm *higher* than the ulnar,
  along the forearm's own axis it is 8 mm more distal. Measure proximal /
  distal along the limb axis. The leg is within 1 degree of vertical.
- **In the A-pose the hand hangs at the height of the greater trochanter,**
  7 cm lateral of it. A lower-limb slice selected by centroid height alone
  picks up the fingers and reported the trochanter 47 mm deep inside the
  hull; the slice is now bounded at X < 0.21.
- **The occipital bone has no inion bump.** Its midline profile is smoothly
  convex, most posterior 3 cm above where the inion belongs. What it has is
  the kink where the nuchal plane (dy/dz ~0.8) meets the occipital plane
  (dy/dz ~0.2); the extreme vertex in a direction between those two normals
  sits on it.
- **The humerus does not resolve the bicipital groove** at 4,280 triangles:
  the anterior profile has one prominence (the lesser tubercle) and recedes
  laterally into the greater. The groove is placed on the anterior surface
  midway between the two tubercles' extremes.
- **Collection 9, `Regions of human body`, is a usable skin reference.** It
  holds 130 named surface patches (Solidify shells) from the frontal region
  to the sole. Distance to the nearest patch is how far a landmark is under
  the skin, and the patch's *name* is a check in itself - the lateral
  malleolus lands nearest `Lateral malleolus.l`, the coracoid nearest
  `Deltopectoral triangle.l`. Two cautions: the patches hug bony prominences
  (0.0 mm at the medial epicondyle) and they do not tile the body, so where
  the patch over a point is absent the reading is an overestimate - Gerdy's
  tubercle reads 22 mm to skin but 4 mm to the muscle hull. It is a
  measuring reference only; nothing from that collection is exported.
- **The deltoid is 24-26 mm thick over the greater tubercle and the bicipital
  groove** by both measures, so those two exceed the brief's 20 mm limb-depth
  limit as written. They are reported by `verify_landmarks.py` under
  `under-deltoid-…`, not asserted. This is a decision, not a waived check:
  the 20 mm limit was a proxy for "a hand can find this", and the proxy is
  wrong where thick muscle overlies bone. The greater tubercle is palpable
  *through* the deltoid - that is how supraspinatus is reached - so a depth
  of 24 mm there is the model's soft tissue and says nothing about whether
  the point is misplaced. The limit stays asserted for the 18 limb landmarks
  it fits. Decided by CYU on PR #4.

## Corrected geometry

A source mesh whose attachment is demonstrably wrong is **redrawn in the
export by anchor rule, never hand-edited in the `.blend`.** A correction that
lives only in a saved file is one nobody can rebuild. A rule in
[`tools/corrections.py`](tools/corrections.py) is reviewed as a description,
resolves against the bone's real vertices on every build, and follows the
model if it is ever updated. The mechanism is the landmarks': the attachment
written anatomically, resolved to a vertex on a named bone, every target
checked against a bone surface and never against a box corner (see
"Bounding-box axes are not anatomical axes" above).

What a correction keeps, and what it changes:

- **The object keeps its name, material, collection and parent.** Only the
  mesh data the export writes for it is replaced, so the object list in
  `manifest.json` and the structure-mesh join are untouched. The manifest's
  counts for that object move, and its modifiers are not applied - the
  redrawn mesh is finished geometry - so `modifiersApplied` drops them.
- **The exported node carries `corrected = True` and `source = "redrawn"`**
  in its extras, the way the authored nerves carry `authored = True`.
  `verify_export.py` demands both on exactly the objects
  `corrections.CORRECTED` names, in every file they appear in, and on no
  others. Saying so on screen is the viewer's job, as the schematic label
  is; the flags are what it keys off.
- **Every rule runs on each side's own bones.** The right is the rule
  mirrored, never the left geometry mirrored, and the build stops if the two
  results are not mirror images to 0.5 mm - an asymmetry would mean the rule
  read something side-dependent.
- **Every rule carries an acceptance box, asserted.** A result outside it
  stops the build and prints the point. Do not move the box to admit the
  point: a rule that misses its box is a wrong description, the failure class
  the landmark job separated from a wrong coordinate.
- `corrections.json` records the result of every build - both attachment
  points, the acceptance measurements, clearance from the neighbouring bones
  - and `verification/corrections/` holds the review renders, before and
  after.
- `ATTRIBUTION.md` does not change for a correction. The licence permits
  derivatives, and the object is still Z-Anatomy's, redrawn.

Corrected objects, each with its target rule - rules, not counts:

| Object | Rule |
|---|---|
| `Calcaneofibular ligament.l` / `.r` | Fibular end: `lm-lateral-malleolus` as resolved, offset 2 mm anterior and 1 mm distal. Calcaneal end: the vertex on the lateral face of `Calcaneus` - outward normal pointing away from the midline, oriented by ray parity, and the first surface a lateral ray meets - nearest to the landmark + (0 lateral, 10 mm posterior, 13 mm distal). A flat ribbon 7 mm wide and 1.5 mm thick between them, 12 triangles, its face turned laterally. Accept: the calcaneal point within 3 mm of a calcaneus vertex, z in [0.032, 0.046], posterior to the fibular end in y; the ribbon clear of the talus. |

What the CFL rule found, worth keeping:

- **The source object is a two-triangle cage**, 18 x 6 x 13 mm once its
  modifiers run, touching the fibula 1-10 mm above the malleolar tip and
  resting on the top of the calcaneus directly beneath it. It ran medially
  under the malleolus and never reached the lateral calcaneal wall. The
  anterior and posterior talofibular ligaments are the same kind of cage;
  both do span fibula to talus, and both were reported and left alone.
- **The calcaneal target sits 9.2 mm lateral of the bone.** The malleolus
  overhangs the calcaneal wall by about 8 mm, so "nearest vertex on the
  lateral face" resolves 7.9 mm medial, 3.3 mm anterior and 3.8 mm distal of
  the target, at z = 0.037. It happened also to be the nearest vertex
  overall; that is the shape of this calcaneus, not a property of the rule,
  which is why the face restriction stays.
- **The fibular end as specified sits 3.0 mm off the fibula.** The landmark
  is already stepped 2 mm out along (lateral, distal), and the malleolar tip
  is the bone's lowest vertex, so a point 1 mm further distal is off the
  bone by construction. Recorded and rendered as specified, not adjusted.
- **A cross-product axis flips under mirroring.** The ribbon's width axis is
  fixed to point posterior on both sides so the two builds order their
  corners the same way; the mirror check compares point sets regardless.

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

## Object names follow TA2 content, not TA2 word order

**Do not match clinical names against this model by substring.** Z-Anatomy's
names carry the TA2 terms but frequently invert the adjectives — it is
`Rectus posterior major capitis muscle`, not `Rectus capitis posterior major`
— and `colli` is used throughout where clinical English uses `cervicis`:
`Semispinalis colli muscle`, `Splenius colli muscle`, `Multifidus colli
muscle`, `Longissimus colli muscle`, `Iliocostalis colli muscle`. A substring
match on clinical names silently drops at least twelve structures, and they
read as absent from the model rather than as a matching failure — the
suboccipitals nearly went down as "not modelled" during the structure-map
join for exactly this reason.

Match on **normalised token sets**: content words only, dropping `muscle`,
`of`, `part` and the side suffix, with `colli ≡ cervicis`, and compare as
sets so word order cannot matter. `tools/regions.py` already treats `colli`,
`cervicis` and `capitis` as one class for region assignment; anything that
joins names to this model needs the same treatment.

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

### The schematic honesty requirement — paid, in the viewer

The authored peripheral nerves are **schematic approximations, not
imaging-derived anatomy**, and rendered beside the model-derived muscles and
bones they would look equally authoritative. Four things were required to keep
that distinction visible. All four now exist, two here and two in the viewer.

**Here:**

- every authored object carries `authored = True` and `source = "schematic"`,
  exported into the glTF as node `extras` — verified on all 20 nodes
- they export to `nerves.glb` alone, never merged with model-derived geometry,
  and [`ATTRIBUTION.md`](ATTRIBUTION.md) records them as original work

**In the viewer — mvmt-program, paid by
[#26](https://github.com/calvinyu94-debug/mvmt-program/pull/26) and reached
from the index by
[#27](https://github.com/calvinyu94-debug/mvmt-program/pull/27):**

- a **distinct material**: the nerves are drawn unlit and flat, no shading and
  no roughness, so they read as an overlay on the model rather than a part of it
- the label **"Schematic — indicative path only"**, over the model whenever
  the nerve layer is on or a nerve is selected, and again in the selection
  panel beside the nerve's name. No close control; not a tooltip.

Both are recorded in mvmt-program's `CLAUDE.md` as things that have to stay,
and that is where they are guarded now. The flags exported here are what the
viewer keys off; they were never a substitute for the treatment, and they are
not one now. If the viewer is ever rewritten, this section reopens.

## Conventions

- Exports are **built locally, never committed** — `.blend`, archives and
  `*.glb` are gitignored. Records of what was built (`nerves.json`,
  `verification/*.png`, `inventory.csv`) are committed.
- Every headless script prints a machine-checkable line and exits non-zero on
  failure: `INVENTORY_OK`, `NERVES_OK`, `VERIFY_OK`, `LANDMARKS_OK`,
  `VERIFY_LANDMARKS_OK`. A missing landmark is a hard error, never a silent
  skip — a path must never quietly drift onto the wrong geometry.
- [`EXCLUSIONS.md`](EXCLUSIONS.md) is authoritative for licence exclusions and
  is meant to be enforced programmatically, not remembered.
