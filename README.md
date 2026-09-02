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
| [`verification/decimation/`](verification/decimation/) | Twelve representative meshes at source / 50% / 12.5% / overview, side by side |
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

## What has been done

- Z-Anatomy's full third-party licence position audited. Nothing is
  NoDerivatives, so decimation is permitted; three component sets are
  incompatible or unlicensed and are excluded — see `EXCLUSIONS.md`.
- The reference model fetched and opened in the pinned Blender version.
- A complete object inventory produced, sanity-checked and committed.
- The ten missing peripheral nerves authored as schematic tubes, verified
  against the real bones — 11 checks, no nerve passing through bone — and
  exported to `nerves.glb`, separately from anything model-derived.
- The musculoskeletal scope — 2,054 meshes after the licence filter — assigned
  to the app's nine regions, decimated on two tiers and exported as
  Draco-compressed glTF: a 212k-triangle whole-body overview, one file per
  region at 50% with its neighbours dimmed as context at 12.5%, and a
  full-resolution insertion layer per region. Every node carries the exact
  Z-Anatomy `sourceName`, verified by reading the files back. See
  [`verification/export-report.md`](verification/export-report.md).

## What has not been done

- **No join between the MVMT structure map and the exported objects.** That
  join is clinical judgement, not automation: "Rotator Cuff" is four objects,
  "Scalenes" is three. It is authored separately, against the `objects` array
  in `manifest.json`, which is complete and exact by construction.
- No viewer — and with it, **the schematic treatment for the authored nerves is
  still owed**: a distinct material, and a visible "Schematic — indicative path
  only" label whenever a nerve is selected or the nerve layer is on. The
  exported `authored`/`source` flags are what that keys off, not a substitute
  for it. See [CLAUDE.md](CLAUDE.md#open-debts).

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

## Building the region exports

All from the worktree root, against the same pinned Blender:

```bash
blender --background source/Z-Anatomy/Startup.blend --python tools/export_regions.py -- --out .
```

Prints `EXPORT_OK meshes=2054 regions=9 files=19 …` and writes the nineteen
`.glb` files (gitignored), `samples.glb` (gitignored), `manifest.json` and
`region-assignment.csv`. It asserts the scope figures and the `EXPECTED`
exclusion counts first and stops on any drift. Then:

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
index accessors, the bytes on disk, region membership, and winding by signed
volume on the Draco-decoded geometry. It prints `VERIFY_EXPORT_OK checks=…`
and exits non-zero on any failure.

The region assignment can be reviewed without Blender:

```bash
python tools/regions.py
```

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
