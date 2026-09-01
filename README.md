# mvmt-anatomy

Anatomical model tooling for the MVMT structure map — an inventory of the
Z-Anatomy atlas, and eventually a two-tier web viewer built from it.

**No model-derived asset has been produced.** Nothing from Z-Anatomy has been
decimated or exported. What this repo holds is an inventory, the licence
analysis that has to precede any export — and one set of original geometry that
is not derived from the model at all: the ten peripheral nerves the atlas does
not contain, authored here from scratch.

Those nerves are **schematic approximations, not imaging-derived anatomy**, and
they are kept separate from model-derived geometry at every stage. See
[`ATTRIBUTION.md`](ATTRIBUTION.md#original-work-in-this-repository-the-authored-peripheral-nerves).

## What is here

| File | What it is |
|---|---|
| [`inventory.csv`](inventory.csv) | 7,184 objects from `Z-Anatomy/Startup.blend` — name, type, collection path, parent, triangle and vertex counts, material, visibility, world-space bounding box and centroid |
| [`inventory-summary.md`](inventory-summary.md) | The inventory read back: totals, breakdown by collection, heaviest objects, unit scale, and the structural oddities that matter downstream |
| [`EXCLUSIONS.md`](EXCLUSIONS.md) | Every object that must never enter an export, with the licence reason. Derived from the CSV, meant to be enforced programmatically |
| [`ATTRIBUTION.md`](ATTRIBUTION.md) | The licence chain, including the third-party components that are **not** CC BY-SA |
| [`tools/inventory.py`](tools/inventory.py) | The Blender script that produces `inventory.csv` |
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

## What has not been done

- No decimation.
- No export of model-derived geometry — no glTF, no GLB, no meshes from
  Z-Anatomy. `nerves.glb` is original work and contains nothing from the atlas.
- **No join between the 116-entry MVMT structure map and these 7,184 objects.**
  That join is clinical judgement, not automation: "Rotator Cuff" is four
  objects, "Scalenes" is three, and most of the file is never referenced at all.
  It is the next job, and it is written against this inventory rather than
  against guesses.
- No viewer.

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
