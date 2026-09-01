# Inventory summary

Generated from `inventory.csv` by `tools/inventory.py`.

| | |
|---|---|
| Source | `Z-Anatomy/Startup.blend`, 306,838,281 bytes, `BLENDER-v305` |
| Obtained from | `Z-Anatomy.zip` (86,734,957 bytes) in `Z-Anatomy/Models-of-human-anatomy@master` |
| Blender | 3.6.23 (hash `e467db79ca8c`, built 2025-06-17) |
| Run | `INVENTORY_OK objects=7184 meshes=4569 triangles=4099477 out=inventory.csv` |

## Totals

| Metric | Count |
|---|---|
| Objects | **7,184** |
| Meshes | **4,569** |
| Triangles | **4,099,477** |
| Vertices | 2,094,701 |

**Not all of that is anatomy.** Excluding label infrastructure and reference
geometry, the real anatomical payload is **2,905 meshes / 4,090,144 triangles**
— 99.8% of the triangles in 64% of the meshes. See *Label infrastructure*.

### Object types

| Type | Count |
|---|---|
| MESH | 4,569 |
| FONT | 1,660 |
| CURVE | 951 |
| LIGHT | 3 |
| CAMERA | 1 |

## By top-level collection

Counted by membership in `all_collections`, so an object cross-listed into
several collections is counted in each. This is why the rows sum to more than
7,184 — see *Cross-listing* below.

| Collection | Objects | Meshes | Triangles |
|---|---:|---:|---:|
| Bonus collection *(deep hierarchy — see below)* | 5,559 | 3,373 | 3,991,563 |
| 4: Muscular system | 894 | 789 | 2,138,247 |
| 7: Nervous system & Sense organs | 842 | 460 | 788,098 |
| 1: Skeletal system | 2,218 | 1,244 | 598,979 |
| 3: Joints | 593 | 480 | 160,201 |
| 6: Lymphoid organs | 276 | 220 | 127,009 |
| 8: Visceral systems | 479 | 254 | 83,918 |
| 5: Cardiovascular system | 757 | 60 | 67,840 |
| 9: Regions of human body | 343 | 299 | 66,881 |
| 2: Muscular insertions | 705 | 705 | 63,843 |
| Reference lines, reference planes, movements | 54 | 52 | 3,936 |
| Scene Collection (root) | 15 | 2 | 357 |
| (no collection) | 1 | 1 | 168 |
| Cross section planes | 3 | 3 | 0 |

The muscular system alone is **52% of all triangles**.

## The 25 heaviest objects

| # | Object | Triangles | Vertices | Collection |
|---:|---|---:|---:|---|
| 1 | White matter of telencephalon.l | 135,288 | 67,646 | 7: Nervous system |
| 2 | White matter of telencephalon.r | 135,288 | 67,646 | 7: Nervous system |
| 3 | Iliotibial tract.l | 48,612 | 24,298 | 4: Muscular system |
| 4 | Iliotibial tract.r | 48,612 | 24,298 | 4: Muscular system |
| 5 | External intercostal muscles.l | 41,410 | 20,663 | 4: Muscular system |
| 6 | External intercostal muscles.r | 41,410 | 20,663 | 4: Muscular system |
| 7 | Internal intercostal muscles.l | 40,184 | 20,049 | 4: Muscular system |
| 8 | Internal intercostal muscles.r | 40,184 | 20,049 | 4: Muscular system |
| 9 | Innermost intercostal muscles.l | 38,254 | 19,091 | 4: Muscular system |
| 10 | Innermost intercostal muscles.r | 38,254 | 19,091 | 4: Muscular system |
| 11 | Spinal dura | 35,002 | 18,104 | 7: Nervous system |
| 12 | Transversus abdominis muscle.l | 34,328 | 17,164 | 4: Muscular system |
| 13 | Transversus abdominis muscle.r | 34,328 | 17,164 | 4: Muscular system |
| 14 | External abdominal oblique muscle.l | 29,622 | 14,811 | 4: Muscular system |
| 15 | External abdominal oblique muscle.r | 29,622 | 14,811 | 4: Muscular system |
| 16 | Internal abdominal oblique muscle.l | 28,869 | 14,411 | 4: Muscular system |
| 17 | Internal abdominal oblique muscle.r | 28,869 | 14,411 | 4: Muscular system |
| 18 | Scapula.l | 25,326 | 12,690 | 1: Skeletal system |
| 19 | Scapula.r | 25,326 | 12,690 | 1: Skeletal system |
| 20 | Serratus anterior muscle.l | 25,240 | 12,618 | 4: Muscular system |
| 21 | Serratus anterior muscle.r | 25,240 | 12,618 | 4: Muscular system |
| 22 | Latissimus dorsi muscle.l | 21,580 | 10,796 | 4: Muscular system |
| 23 | Latissimus dorsi muscle.r | 21,580 | 10,796 | 4: Muscular system |
| 24 | Rectus abdominis muscle.l | 20,604 | 10,304 | 4: Muscular system |
| 25 | Rectus abdominis muscle.r | 20,604 | 10,304 | 4: Muscular system |

The two heaviest objects in the entire file are **brain white matter**, and
together they are 6.6% of all triangles. They are licence-excluded
(see [EXCLUSIONS.md](EXCLUSIONS.md)) and referenced by nothing in the structure
map, so the decimation budget gets that back for free.

Everything else in the top 25 is `.l`/`.r` paired and clinically relevant —
iliotibial tract, intercostals, abdominal wall, scapula, serratus, lats. These
are the objects the regional models will actually be spending their budget on.

## Bounding box and unit scale

Real anatomy meshes only — label and reference geometry excluded:

| Axis | Min | Max | Span |
|---|---:|---:|---:|
| X (left–right) | −0.3401 | +0.3401 | **0.6802** |
| Y (front–back) | −0.1544 | +0.1659 | **0.3203** |
| Z (up) | −0.0509 | +1.7433 | **1.7942** |

**One Blender unit = one metre.** The model is a life-size adult of about
**1.79 m**, 0.68 m across with the arms at the sides and 0.32 m deep. Z-up,
which is Blender's native convention — a glTF export will need the usual Y-up
conversion.

**`.l` is +X and `.r` is −X.** Confirmed on paired objects (`Nail plate.l` at
+0.340, `Nail plate.r` at −0.340). Laterality can therefore be recovered from
the centroid sign as well as the name suffix, which is a useful cross-check.

Including reference geometry the box is wider — X and Y both reach ±0.3418 —
because the median, paramedian and coronal reference planes are quads sized to
span the model. They are 2–10 triangles each and are not anatomy.

## Cross-listing: the important structural fact

**5,555 of 7,184 objects belong to more than one collection.** Every anatomical
object is filed once under a flat top-level system (`1: Skeletal system`,
`4: Muscular system`, …) and again inside `Bonus collection`, which holds a
genuine anatomical hierarchy up to **11 levels deep** — 62 distinct
second-level branches.

That hierarchy is far more useful for regional assignment than the flat
systems, and it already contains a regional partition:

`Bonus collection/Regions of human body/Main divisions/…`

| Division | Objects | Triangles |
|---|---:|---:|
| Head | 1,434 | 1,133,129 |
| Trunk | 1,183 | 1,737,397 |
| Right lower limb | 509 | 355,745 |
| Left lower limb | 448 | 355,961 |
| Right upper limb | 381 | 202,498 |
| Left upper limb | 322 | 201,627 |
| Right foot | 304 | 38,897 |
| Neck | 257 | 268,628 |
| Right hand | 96 | 23,838 |
| Left foot | 96 | 5,725 |
| Left hand | 42 | 2,070 |

> **These divisions are not left/right symmetric, and that is an upstream
> defect, not a property of the geometry.** Right foot carries 304 objects and
> 38,897 triangles against left foot's 96 and 5,725; right hand 96 against left
> hand 42. The meshes themselves *are* symmetric — 964 `.l` objects against 965
> `.r`. It is the regional tagging that is incomplete on the left side.
>
> Regional assignment must therefore **not** be driven by these collections
> alone. Pairing on the `.l`/`.r` suffix, or on centroid X sign, recovers what
> the tagging misses.

## Label infrastructure

**2,546 objects (1,239 MESH, 1,307 FONT) exist to draw the atlas's on-screen
labels, and carry 7,191 triangles between them** — 0.18% of the file.

The Z-Anatomy add-on names them by suffix (`__init__.py`:
`label_elements = {"-txt", ".t", ".j"}`):

| Suffix | Meaning | Count |
|---|---|---:|
| `.j` | label leader/joint anchor | 1,227 zero-poly meshes |
| `.g` | group label | 532 objects, mostly FONT |
| `.t` / `-txt` | label text | FONT objects |

This is why **1,605 of 4,569 meshes have zero polygons** — they are label
anchors, not broken geometry. It looked alarming in the raw sanity check and is
not.

All 1,660 FONT and 951 CURVE objects should be dropped at export. So should the
`.j`/`.t`/`.g`/`-txt` meshes. The viewer will draw its own labels from the
structure map.

## Muscle attachment sites

`2: Muscular insertions` holds 705 meshes / 63,843 triangles — painted origin
and insertion footprints on bone, suffixed `.ol` `.or` (origin left/right) and
`.el` `.er` (insertion left/right):

`(Abdominal part of pectoralis major muscle).ol`, `Abductor hallucis.el`, …

Not needed for the first viewer, but worth knowing they exist: they are exactly
what an "where does this attach" overlay would need, and they are cheap.

## Other oddities

| Observation | Count | Assessment |
|---|---:|---|
| Duplicate object names | **0** | Names are unique — safe as join keys |
| Objects outside any collection | 1 | `Lymph node`, MESH, 168 tris — orphaned, unreferenced |
| Meshes with zero polygons | 1,605 | Label anchors, explained above |
| Hidden in viewport | 697 (344 meshes) | **0 triangles between them** — all label infrastructure |
| Meshes with no material | 1,599 | Tracks the zero-poly label meshes |
| Objects in >1 collection | 5,555 | By design — see *Cross-listing* |
| Default-style names (`Cube.001`) | **0** | All TA2 anatomical terminology |

Blender also reported one **upstream dependency cycle** on load —
`Oesophagus-profile` ↔ `Oesophagus` via a Curve Follow Parent and a Solidify
modifier. It is benign for inventory purposes (no geometry is evaluated) but
would need attention if the oesophagus were ever exported. It is not referenced
by the structure map.

## What this means for the decimation budget

- The whole-body navigation model has to come down from **4.09 M triangles**.
- **~479 K triangles (11.7%) leave on licence grounds** before any decimation —
  brain/CNS, inner and middle ear, kidney. None is referenced by the structure
  map.
- A further **~7 K** goes with the label infrastructure, and 951 CURVE and
  1,660 FONT objects disappear entirely.
- That leaves roughly **3.6 M triangles** of referenced-or-plausible anatomy as
  the real starting point for the two-tier split.
- The muscular system is 52% of it, and it is where the clinical value is, so
  it should get a disproportionate share of the regional budget rather than an
  even one.
