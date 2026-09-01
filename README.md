# mvmt-anatomy

Anatomical model tooling for the MVMT structure map — an inventory of the
Z-Anatomy atlas, and eventually a two-tier web viewer built from it.

**There are no processed 3D assets in this repository, and none have been
produced.** This repo currently contains an inventory and the licence analysis
that has to precede any export. Nothing has been decimated or exported.

## What is here

| File | What it is |
|---|---|
| [`inventory.csv`](inventory.csv) | 7,184 objects from `Z-Anatomy/Startup.blend` — name, type, collection path, parent, triangle and vertex counts, material, visibility, world-space bounding box and centroid |
| [`inventory-summary.md`](inventory-summary.md) | The inventory read back: totals, breakdown by collection, heaviest objects, unit scale, and the structural oddities that matter downstream |
| [`EXCLUSIONS.md`](EXCLUSIONS.md) | Every object that must never enter an export, with the licence reason. Derived from the CSV, meant to be enforced programmatically |
| [`ATTRIBUTION.md`](ATTRIBUTION.md) | The licence chain, including the third-party components that are **not** CC BY-SA |
| [`tools/inventory.py`](tools/inventory.py) | The Blender script that produces `inventory.csv` |

## What has been done

- Z-Anatomy's full third-party licence position audited. Nothing is
  NoDerivatives, so decimation is permitted; three component sets are
  incompatible or unlicensed and are excluded — see `EXCLUSIONS.md`.
- The reference model fetched and opened in the pinned Blender version.
- A complete object inventory produced, sanity-checked and committed.

## What has not been done

- No decimation.
- No export of any kind — no glTF, no GLB, no meshes.
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
