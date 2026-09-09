# mvmt-anatomy

Anatomical model tooling for the MVMT structure map — an inventory of the
Z-Anatomy atlas, a musculoskeletal glTF export pipeline built on it, and
eventually a two-tier web viewer.

What this repo holds is the inventory, the licence analysis that precedes any
export, the pipeline that produces the region assets and the records of what
it produced (`manifest.json`, `region-assignment.csv`, renders) — and one set
of original geometry that is not derived from the model at all: the ten
peripheral nerves the atlas does not contain, authored here from scratch.
**The exported `.glb` files themselves are built locally and never committed.**

Those nerves are **schematic approximations, not imaging-derived anatomy**, and
they are kept separate from model-derived geometry at every stage. See
[`ATTRIBUTION.md`](ATTRIBUTION.md#original-work-in-this-repository-the-authored-peripheral-nerves).

## What is here

| File | What it is |
|---|---|
| [`inventory.csv`](inventory.csv) | 7,184 objects from `Z-Anatomy/Startup.blend` — name, type, collection path, parent, triangle and vertex counts, material, visibility, world-space bounding box and centroid |
| [`inventory-summary.md`](inventory-summary.md) | The inventory read back: totals, breakdown by collection, heaviest objects, unit scale, and the structural oddities that matter downstream |
| [`EXCLUSIONS.md`](EXCLUSIONS.md) | Every object that must never enter an export, with the licence reason. Derived from the CSV, meant to be enforced programmatically |
| [`ATTRIBUTION.md`](ATTRIBUTION.md) | The licence chain, including the third-party components that are **not** CC BY-SA, and the original-work status of the authored nerves |
| [`CLAUDE.md`](CLAUDE.md) | Standing notes for working in this repo: what has bitten us, and what is still owed |
| [`manifest.json`](manifest.json) | What the viewer and the structure map read: every exported file with its triangle and byte counts, and the full join table of all 2,054 exported meshes by `sourceName` |
| [`region-assignment.csv`](region-assignment.csv) | Every kept mesh, its region, system, side, which signal decided it and why, and its triangle count |
| [`verification/export-report.md`](verification/export-report.md) | The export read back: kept counts against the brief, the region table with the centroid-only set called out, actual against target triangles, decimation deviation per tier, bytes, and what the model did that the inventory did not predict |
| [`verification/regions/`](verification/regions/) | One 1600 px render per region at target detail with its context dimmed |
| [`tools/inventory.py`](tools/inventory.py) | The Blender script that produces `inventory.csv` |
| [`tools/scope.py`](tools/scope.py) | The scope filter (collections 1–4) and the licence filter from `EXCLUSIONS.md`, with the `EXPECTED` counts asserted |
| [`tools/regions.py`](tools/regions.py) | Region assignment: a clinical override table, the collection hierarchy, insertion-to-muscle parentage, side pairing, centroid fallback — reviewable against the CSV without Blender |
| [`tools/export_regions.py`](tools/export_regions.py) | The Blender script that bakes, decimates and exports the region files, the overview, the insertion layers and the manifest |
| [`tools/render_export.py`](tools/render_export.py) | Renders the review images from the exported files, in a separate Blender |
| [`tools/verify_export.py`](tools/verify_export.py) | Reads every exported file back and checks names, extras, counts, bytes, membership and winding against the manifest, the CSV and the inventory |
| [`tools/export_report.py`](tools/export_report.py) | Writes `verification/export-report.md` from the committed records |
| [`tools/nerve_paths.py`](tools/nerve_paths.py) | Waypoints for the ten authored nerves, anchored to landmark objects, with the departures from the original specification and why |
| [`tools/build_nerves.py`](tools/build_nerves.py) | Builds the nerves and exports `nerves.glb` and `nerves.json` |
| [`tools/verify_nerves.py`](tools/verify_nerves.py) | Checks them against the real geometry — bone intersection and the named anatomical relationships — and renders `verification/` |
| [`nerves.json`](nerves.json) | Resolved waypoint coordinates, centrelines, radii, triangle counts and the `authored`/`source` flags |
| [`verification/`](verification/) | Six orthographic renders of the nerves against a semi-transparent skeleton |
| [`tools/landmark_anchors.py`](tools/landmark_anchors.py) | The 42 palpable landmarks, each as a geometric rule on its bone - the anatomical description made executable - with the brief's first-pass bounding-box estimates kept for comparison |
| [`tools/build_landmarks.py`](tools/build_landmarks.py) | Resolves the rules against the model, measures each point and writes `landmarks.json` |
| [`tools/verify_landmarks.py`](tools/verify_landmarks.py) | Checks every landmark for surface distance, depth and symmetry, asserts the named relationships with margins, and renders `verification/landmarks/` |
| [`landmarks.json`](landmarks.json) | Every landmark's anchor (object, uvw, offset), resolved coordinates for both sides, signed surface distance, depth, nearest skin region, and where the first pass had landed |
| [`tools/corrections.py`](tools/corrections.py) | Source meshes redrawn in the export by anchor rule - the calcaneofibular ligament - each as an anatomical description resolved on the bones' real vertices, with an asserted acceptance box |
| [`tools/render_corrections.py`](tools/render_corrections.py) | Renders the corrected geometry for review from the exported files, before and after |
| [`corrections.json`](corrections.json) | The result of every correction rule on the current build: both attachment points on both sides, acceptance measurements, clearance from the neighbouring bones |
| [`verification/corrections/`](verification/corrections/) | Right-ankle lateral and posterior renders of the redrawn calcaneofibular ligament, and the same views of the source placeholder it replaced |
| [`verification/landmarks/`](verification/landmarks/) | Four orthographic renders - anterior, posterior, both laterals - of the landmarks as labelled spheres on a semi-transparent skeleton |
| [`tools/bp3d_fit.py`](tools/bp3d_fit.py) | Fits the Z-Anatomy body onto BodyParts3D for MVMT Atlas: runs the 42 landmark rules on the BP3D bones read from the atlas chunks, global similarity then a blended residual per region, residuals per landmark. Blender's Python for mathutils; opens no .blend |
| [`bp3d-fit.json`](bp3d-fit.json) | The fit: both transforms, every landmark pair on both bodies with its residual, the six low-confidence landmarks |
| [`tools/bp3d_export.py`](tools/bp3d_export.py) | Carries fascia, ligaments, insertions, nerves and landmarks onto the BP3D body in Human Atlas's chunk format, one chunk per region; projects insertions onto their own BP3D bone; authors the schematic spinal cord through the BP3D canal; the seam check; the review renders |
| [`tools/mvmt_structures.mjs`](tools/mvmt_structures.mjs) | Pulls the MVMT structure table out of mvmt-program's index.html for the export |
| [`bp3d-export.json`](bp3d-export.json) | What the export wrote: parts and triangles per system and region, the projection counts, the seam table, the canal centres, the side mismatches |
| [`verification/bp3d-fit-report.md`](verification/bp3d-fit-report.md) | The fit and the export read back: residuals, projection, seams, chunks, names |
| [`verification/bp3d/`](verification/bp3d/) | Knee, hip and shoulder from the front and the side with our ligaments and insertions on BP3D bone; the whole body with fascia and nerves; the landmarks |
| [`tools/build_mannequin.py`](tools/build_mannequin.py) | Builds the exercise-demo mannequin - an MPFB2 default human on the game-engine skeleton, T-pose rest, clay, one skinned mesh - exports `mannequin.glb`, calibrates it and writes `rig-manifest.json`. **Blender 4.2 with MPFB2, not the pinned 3.6** |
| [`tools/mannequin_rig.py`](tools/mannequin_rig.py) | The rig as the exported file states it, pure Python: reads the GLB, skins the mesh as three.js does, resolves the app's joint vocabulary to bones and measures the anatomical axes in each bone's own frame |
| [`tools/verify_mannequin.py`](tools/verify_mannequin.py) | Reads `mannequin.glb` back in a fresh Blender, re-derives the calibration and compares it with the manifest, measures the brief's calibration pose in numbers, and renders the figure beside `overview.glb` |
| [`tools/mannequin_preview.html`](tools/mannequin_preview.html) | The same check in the consumer: loads the file in three.js, poses it through `rig-manifest.json` and prints what the pose did |
| [`rig-manifest.json`](rig-manifest.json) | The resolution key the viewer reads: every joint resolved to exactly one bone, the pinned effectors, the neutral offsets, and for every anatomical motion the measured axis in the bone's frame with how far it is from the nearest labelled axis |
| [`verification/mannequin/`](verification/mannequin/) | The rest pose, the calibration pose from three views - skinned from the exported file, not by Blender's armature - the figure beside the Z-Anatomy overview, and the three.js capture |

## What has been done

- Z-Anatomy's full third-party licence position audited. Nothing is
  NoDerivatives, so decimation is permitted; three component sets are
  incompatible or unlicensed and are excluded — see `EXCLUSIONS.md`.
- The reference model fetched and opened in the pinned Blender version.
- A complete object inventory produced, sanity-checked and committed.
- The ten missing peripheral nerves authored as schematic tubes, verified
  against the real bones — 11 checks, no nerve passing through bone — and
  exported to `nerves.glb`, separately from anything model-derived.
- The 42 palpable landmarks resolved as points on the model's bones - none
  of them is a mesh in the atlas - each from a rule that encodes its
  anatomical description on the bone's real vertices, verified on or just
  outside the bone (1.0 to 2.0 mm), symmetric, shallow where a hand reaches
  them, and holding the six named relationships. See
  [`landmarks.json`](landmarks.json) and
  [`verification/landmarks/`](verification/landmarks/).
- The musculoskeletal scope — 2,054 meshes after the licence filter — assigned
  to the app's nine regions, decimated on two tiers and exported as
  Draco-compressed glTF: a 212k-triangle whole-body overview, one file per
  region at 50% with its neighbours dimmed as context at 12.5%, and a
  full-resolution insertion layer per region. Every node carries the exact
  Z-Anatomy `sourceName`, verified by reading the files back. See
  [`verification/export-report.md`](verification/export-report.md).
- The calcaneofibular ligament, a placeholder quad in the atlas, redrawn in
  the export by anchor rule between the lateral malleolus and the lateral
  wall of the calcaneus, flagged `corrected` in its extras and recorded in
  [`corrections.json`](corrections.json) and
  [`verification/corrections/`](verification/corrections/).
- The exercise-demo mannequin: a neutral clay figure from MPFB2 (CC0, not
  derived from the atlas) on MPFB's game-engine skeleton, rest pose an exact
  T, one skinned mesh, no Draco, in the region exports' conventions - and its
  calibration table, measured on the exported file rather than read off the
  bones' axis labels, because those are rolled by up to 43 degrees from the
  anatomical axes. See [`rig-manifest.json`](rig-manifest.json) and
  [`verification/mannequin/`](verification/mannequin/). The pose engine that
  consumes it is a separate job in mvmt-program.

## What has not been done

- **No join between the MVMT structure map and the exported objects.** That
  join is clinical judgement, not automation: "Rotator Cuff" is four objects,
  "Scalenes" is three. It is authored separately, against the `objects` array
  in `manifest.json`, which is complete and exact by construction.
- No viewer here. The viewer lives in
  [mvmt-program](https://github.com/calvinyu94-debug/mvmt-program), and the
  schematic treatment for the authored nerves — a distinct unlit material, and
  the non-dismissible "Schematic — indicative path only" label whenever a nerve
  is selected or the nerve layer is on — is paid there, by
  [#26](https://github.com/calvinyu94-debug/mvmt-program/pull/26) and
  [#27](https://github.com/calvinyu94-debug/mvmt-program/pull/27). The
  exported `authored`/`source` flags are what it keys off. See
  [CLAUDE.md](CLAUDE.md#open-debts).

## Reproducing the inventory

Blender **3.6.x** specifically. The reference `.blend` is documented as
compatible with 3.6 and incompatible with 4.5, and opening it in 4.x may appear
to work while silently dropping data.

```bash
blender --version   # must report 3.6.x
```

Fetch the model into `source/`, which is gitignored — model files must never
enter git history:

```bash
mkdir -p source && cd source
curl -LO https://raw.githubusercontent.com/Z-Anatomy/Models-of-human-anatomy/master/Z-Anatomy.zip
unzip Z-Anatomy.zip     # -> Z-Anatomy/Startup.blend, 306,838,281 bytes
```

Then:

```bash
blender --background source/Z-Anatomy/Startup.blend --python tools/inventory.py -- inventory.csv
```

It prints `INVENTORY_OK objects=… meshes=… triangles=…` and exits zero. A run
that hangs or exits non-zero has produced an untrustworthy CSV — do not use it.

## Building and verifying the nerves

```bash
blender --background source/Z-Anatomy/Startup.blend --python tools/build_nerves.py -- nerves.glb nerves.json
```

Prints `NERVES_OK built=20 triangles=45104` and exits zero. A landmark that does
not resolve is a hard error, never a silent skip, so a path can never quietly
drift onto the wrong geometry.

`nerves.glb` is a build output and is gitignored, like every other export here;
rebuild it rather than committing it. `nerves.json` and the renders are
committed, because they are the record of what was built.

To re-check the geometry, and optionally re-render:

```bash
blender --background source/Z-Anatomy/Startup.blend --python tools/verify_nerves.py -- --render verification
```

Prints `VERIFY_OK checks=11 failed=0` and exits zero; it exits non-zero on any
failure, so it can gate a build. The checks are intersection against all 278
skeletal meshes, and the named relationships a clinician looks for first — the
ulnar behind the medial epicondyle, the radial in the spiral groove, the common
fibular at the fibular neck, the sciatic below piriformis, the tibial behind the
medial malleolus, the median anterior at elbow and inside the carpal tunnel.
Each reports its margin in millimetres rather than a bare pass.

## Building and verifying the landmarks

```bash
blender --background source/Z-Anatomy/Startup.blend --python tools/build_landmarks.py -- landmarks.json
```

Prints `LANDMARKS_OK count=42` and exits zero. A missing anchor object, a rule
that selects nothing, or a point inside its bone is a hard error. No glTF is
written: these are points, and the viewer places a marker.

Each landmark is defined in `tools/landmark_anchors.py` as a rule on the
bone's evaluated mesh - "the femoral vertex with the greatest X", "the most
anterior vertex of the top 3 mm of the manubrium's midline" - resolved to a
vertex and stepped 2 mm outward. The `uvw` and `offset` written to
`landmarks.json` reproduce that point in the same anchor scheme the nerves
use, but they are outputs of the rule, not inputs: the brief's first-pass
`uvw` estimates were read off axis-aligned bounding boxes of oblique bones
and landed up to 78 mm from the bone. Each is kept in the file under
`firstPass` with how far it was off.

```bash
blender --background source/Z-Anatomy/Startup.blend --python tools/verify_landmarks.py -- --render verification/landmarks
```

Prints `VERIFY_LANDMARKS_OK checks=13 failed=0` and exits zero. The checks
are: on or outside the bone on both sides (0 to +5 mm, sign by ray-cast
parity), the anchor round-trips to the resolved point, the eighteen limb
landmarks under 20 mm beneath the limb's convex cross-section, paired
landmarks symmetric within 3 mm, and the six relationships - radial styloid
distal to ulnar along the forearm axis, lateral malleolus distal and
posterior to medial, PSIS behind ASIS and both above the ischial tuberosity,
greater trochanter the most lateral hip point, acromion above and lateral to
the coracoid, C7 behind and below C2 - each with its margin. It also reports
each landmark's distance to the nearest of the atlas's own skin-region
patches, and that patch's name, as an independent reading.

## Corrected geometry

One source mesh is not exported as Z-Anatomy drew it. The calcaneofibular
ligament is a two-triangle placeholder in the atlas, running medially under
the lateral malleolus onto the top of the calcaneus; the export redraws it as
a ribbon from the anterior-distal face of the malleolus down and back to the
lateral wall of the calcaneus. It is redrawn by **rule**, in
[`tools/corrections.py`](tools/corrections.py), resolved on the bones' real
vertices every build - never by editing the `.blend` - and the exported node
carries `corrected = True` and `source = "redrawn"` in its extras so a viewer
can say so. `corrections.json` records where each end landed;
[`CLAUDE.md`](CLAUDE.md#corrected-geometry) states the rule and lists every
corrected object. The export stops if a rule misses its acceptance box.

```bash
blender --background --factory-startup --python tools/render_corrections.py -- --glb ankle-foot.glb --before <previous ankle-foot.glb>
```

Prints `RENDER_CORRECTIONS_OK renders=…` and writes the review images to
`verification/corrections/`.

## Building the region exports

All from the worktree root, against the same pinned Blender:

```bash
blender --background source/Z-Anatomy/Startup.blend --python tools/export_regions.py -- --out .
```

Prints `EXPORT_OK meshes=2054 regions=9 files=19 …` and writes the nineteen
`.glb` files (gitignored), `samples.glb` (gitignored), `manifest.json`,
`region-assignment.csv` and `corrections.json`. It asserts the scope figures
and the `EXPECTED` exclusion counts first and stops on any drift, and
resolves the correction rules before it renames anything. Then:

```bash
blender --background --factory-startup --python tools/render_export.py -- --manifest manifest.json
```

```bash
blender --background --factory-startup --python tools/verify_export.py -- --manifest manifest.json
```

```bash
python tools/export_report.py
```

The renders and the verifier run in a fresh Blender and read the exported
files, not the export process's memory: the verifier checks every node's
`sourceName` and extras against `inventory.csv`, the triangle counts from the
index accessors, the bytes on disk, region membership, winding by signed
volume on the Draco-decoded geometry, and that exactly the corrected objects
carry the `corrected` / `source` extras. It prints `VERIFY_EXPORT_OK checks=…`
and exits non-zero on any failure.

The region assignment can be reviewed without Blender:

```bash
python tools/regions.py
```

## Building the mannequin

The mannequin is the one export that does **not** come from the Z-Anatomy
model and does **not** run in Blender 3.6. It is built with
[MPFB2](https://static.makehumancommunity.org/mpfb.html), the MakeHuman
extension for Blender 4.2 and later, from MPFB's bundled base mesh and rig -
the optional system-assets pack (skins, eyes, clothes) is not needed and not
used. Keep the two Blenders apart: never open `Startup.blend` in 4.x.

Install once: a portable Blender 4.2 LTS, then MPFB from the Blender
extensions platform into it (the `portable` directory next to the executable
is what makes a 4.2 install self-contained; the pre-4.2 `4.2/config` trick
does nothing in 4.2 and leaves the extension in `%APPDATA%`):

```bash
mkdir -p blender-4.2/portable
blender-4.2/blender -b --command extension install-file -r user_default -e add-on-mpfb-v2.0.17.zip
```

Then, from the worktree root:

```bash
blender-4.2 --background --python tools/build_mannequin.py -- --out . --render verification/mannequin
```

Prints `MANNEQUIN_OK triangles=… joints=… bytes=… height=…` and writes
`mannequin.glb` (gitignored, like every export), `rig-manifest.json` and the
renders. It stops if the figure does not face +Z with its left at +X, if the
rest pose is not a T to half a degree, if any joint in the app's vocabulary
fails to resolve to exactly one bone, or if Blender's own deformation of the
calibration pose disagrees with the file's skinning by more than a
millimetre. The calibration renders are the exported file skinned in numpy
through the manifest's own table, so they show what a glTF viewer will do,
not what Blender did.

```bash
blender-4.2 --background --factory-startup --python tools/verify_mannequin.py -- --overview overview.glb
```

Prints `VERIFY_MANNEQUIN_OK checks=…` and exits non-zero on any failure. It
runs without MPFB and reads only the shipped file: structure (one mesh, one
skin, four influences, no Draco), every manifest key resolving to one bone,
stance and facing, the T, the palms; then it re-derives the whole
calibration table from the file and compares it with the manifest, applies
the brief's calibration pose through the manifest's composition rule and
measures it - right thigh swept 90 from rest and level, knee bent 90 more
than at rest, left arm lateral with the forearm forward, face turned 45 to
the right, right hand bent 45 away from the palm; then it imports the file
through Blender's own importer and renders it beside `overview.glb` if that
has been built.

To see the same thing in the library the viewer uses, serve the worktree
root and open [`tools/mannequin_preview.html`](tools/mannequin_preview.html)
with `?pose=calibration&overview=1`; it prints the same measurements from
three.js's own bones.

`mannequin.glb` and `rig-manifest.json` land in `mvmt-program/assets/` the
way the region files do; `--copy-to ../mvmt-program/assets` on the build does
the copy.

## Provenance of the current mannequin

| | |
|---|---|
| Blender | 4.2.9 LTS, hash `a10f621e649a`, built 2025-04-15; glTF exporter 4.2.83 |
| MPFB | 2.0.17, build 20260722, `add-on-mpfb-v2.0.17.zip` from extensions.blender.org, sha256 `4f0a879d…239a87` |
| Figure | MPFB default macro settings (every slider at 0.5), `game_engine` rig, MPFB's `t-pose.json` for it, refined so every arm segment lies on the world X axis |
| Result | `MANNEQUIN_OK triangles=26756 vertices=13380 joints=53 bytes=767280 height=1.664 blenderAgreement_mm=0.001` |
| Verified | `VERIFY_MANNEQUIN_OK checks=27 failed=0` |

## Provenance of the current inventory

| | |
|---|---|
| Blender | 3.6.23, hash `e467db79ca8c`, built 2025-06-17 |
| Archive | `Z-Anatomy.zip`, 86,734,957 bytes, from `Z-Anatomy/Models-of-human-anatomy@master` |
| Model | `Z-Anatomy/Startup.blend`, 306,838,281 bytes, header `BLENDER-v305` |
| Result | `INVENTORY_OK objects=7184 meshes=4569 triangles=4099477 out=inventory.csv` |

## Licence

Derivative works distributed from this repository are **CC BY-SA 4.0**, with the
exclusions in [`EXCLUSIONS.md`](EXCLUSIONS.md) applied. Read
[`ATTRIBUTION.md`](ATTRIBUTION.md) before distributing anything built from this
model — it is not uniformly CC BY-SA upstream.

The mannequin is the exception: `mannequin.glb` derives from MPFB2's bundled
assets, not from Z-Anatomy, and is **CC0**. See
[`ATTRIBUTION.md`](ATTRIBUTION.md#the-exercise-demo-mannequin-mpfb2-cc0).
