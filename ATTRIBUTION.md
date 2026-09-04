# Attribution

Anatomical model data in this project derives from:

**Z-Anatomy** — https://github.com/Z-Anatomy
Licensed CC BY-SA 4.0. Created by Gauthier Kervyn and contributors.

Z-Anatomy is itself derived from:

**BodyParts3D** — Database Center for Life Science (DBCLS), Japan
Licensed CC BY-SA 2.1 Japan.

Structure naming follows Terminologia Anatomica (TA2, 2019).

## Licensing of derivatives distributed from this repository

The Z-Anatomy model is **predominantly** CC BY-SA 4.0, but it is not uniformly
so. Its own `License.txt` declares third-party components adapted into the
model under terms that are **not** compatible with CC BY-SA 4.0 share-alike:

- **"Anatomy of the Inner Ear"** — University of Dundee School of Medicine —
  CC BY-NC-SA 4.0 *(non-commercial)*
- **"Kidney"** — Lissie Cowley — CC BY-NC 4.0 *(non-commercial)*
- **"Brainder"** and **"White matter"** — University of Washington —
  *no licence stated upstream*

**These components are excluded from every derivative distributed from this
repository.** See [EXCLUSIONS.md](EXCLUSIONS.md), which is the authoritative
list and is enforced programmatically in the export pipeline.

Everything that remains is CC BY-SA 4.0, and **any derivative of it distributed
from this repository is licensed CC BY-SA 4.0** in accordance with the
share-alike terms.

## Original work in this repository: the authored peripheral nerves

**The peripheral nerves in this repository are not derived from BodyParts3D,
from Z-Anatomy, or from any other source model. They are original schematic
additions, and they are not imaging-derived anatomy.**

Z-Anatomy has no peripheral nervous system. Its "Nervous system & Sense organs"
collection is brain, cranial nerve nuclei, spinal ganglia and sense organs; it
contains no brachial plexus, no median, ulnar or radial nerve, no sciatic,
femoral, tibial or common fibular nerve. Ten structures in the MVMT map — the
ten the nerve glides depend on — therefore had no geometry at all.

Those ten are authored here as bezier curves converted to tubes, anchored to
landmark geometry that does exist in the model. They were written from a
specification and a practitioner's reading of the anatomy, then checked
against the real bones. See `tools/nerve_paths.py` for the paths,
`tools/verify_nerves.py` for the checks, `nerves.json` for the resolved
coordinates, and `verification/` for the renders.

### What that means for anyone using them

Rendered beside the muscles and bones they will look equally authoritative.
**They are not.** The rest of the model comes from cadaveric and imaging data
via BodyParts3D. These are approximations of where a nerve runs, accurate
enough to show a path and a relationship, and not accurate enough to be
measured against.

The distinction is carried in the assets themselves, not only in this file:

- every authored object carries `authored = True` and `source = "schematic"`,
  exported into the glTF as node `extras` — **done**
- they export to **`nerves.glb`**, separately from every model-derived export,
  and are never merged into one — **done**
- the viewer renders them visually distinct from model-derived geometry —
  unlit and flat, an overlay rather than a part of the model — and shows
  **"Schematic — indicative path only"** whenever a nerve is selected or the
  nerve layer is on, with no close control — **done**, in
  [mvmt-program](https://github.com/calvinyu94-debug/mvmt-program) by
  [#26](https://github.com/calvinyu94-debug/mvmt-program/pull/26) and
  [#27](https://github.com/calvinyu94-debug/mvmt-program/pull/27). The two
  flags above are what it keys off; they were never a substitute for the
  treatment. Recorded in [CLAUDE.md](CLAUDE.md#open-debts).

### Licensing

As original work they are not encumbered by the upstream chain. They are
released under the same **CC BY-SA 4.0** as the rest of this repository, so
that a consumer of the combined work has one licence to satisfy rather than
two. Attribution for them belongs to this project, not to Z-Anatomy or DBCLS,
and neither upstream should be cited as their source.

## The exercise-demo mannequin: MPFB2, CC0

**`mannequin.glb` is not derived from Z-Anatomy, from BodyParts3D, or from
anything else in the chain above.** It is a character built from the assets
bundled with **MPFB2**, the MakeHuman extension for Blender, in an official,
unmodified build:

- MPFB **2.0.17** (build 20260722), installed from the Blender extensions
  platform as `add-on-mpfb-v2.0.17.zip`,
  sha256 `4f0a879d64a39bf646fbf5f53601ac678855da329d650617dca5737548239a87`
- Blender **4.2.9 LTS** (hash `a10f621e649a`), glTF exporter 4.2.83
- MPFB's bundled base mesh at its default macro settings, its `game_engine`
  skeleton and weights, and its `t-pose.json` for that skeleton. No skin, eye
  or clothing asset is used: the optional system-assets pack is not
  installed, and the eyes, teeth, tongue, eyebrows, eyelashes and every other
  helper mesh are deleted before export.

**The mannequin is licensed CC0 1.0.** The assets MPFB2 bundles are CC0, and
characters exported from an official, unmodified MPFB build are CC0 per the
MakeHuman community's licensing statement
(https://static.makehumancommunity.org/mpfb.html). MPFB's own code is
GPL-3.0-or-later; that licence attaches to the add-on, not to the characters
it produces, and none of its code is redistributed here. This is a separate
licence line from the Z-Anatomy one: nothing about the CC BY-SA chain applies
to the mannequin, and nothing about the mannequin's CC0 status extends to the
anatomical exports.

`tools/build_mannequin.py` records the MPFB and Blender versions it ran
under into `rig-manifest.json`; the table above is what the current build
used. Mixamo is not used for anything.

## Full third-party breakdown

Every component named in Z-Anatomy's `License.txt`:

| Component | Licence | Compatible with CC BY-SA 4.0? | Status here |
|---|---|---|---|
| **BodyParts3D** (DBCLS) — the bulk of the model | CC BY-SA 2.1 Japan | Yes — share-alike, upgradeable | **Included** |
| **Z-Anatomy** additions (Kervyn et al.) | CC BY-SA 4.0 | Yes — same licence | **Included** |
| **Cranial Nerves and Foramina** — Univ. of Dundee, CAHID | CC BY 4.0 | Yes — BY is one-way compatible into BY-SA | Included; unreferenced by the map |
| **Anatomy of the Inner Ear** — Univ. of Dundee School of Medicine | CC BY-**NC**-SA 4.0 | **No** — NC | **Excluded** |
| **Kidney** — Lissie Cowley | CC BY-**NC** 4.0 | **No** — NC | **Excluded** |
| **"Brainder"** and **"White matter"** — Univ. of Washington | **None stated** | **Unknown** | **Excluded** |
| Structure **definitions** | Wikipedia, CC BY-SA 3.0 | Yes — upgradeable to 4.0 | Not exported |
| Blender add-on / app code (Zielinski; Vinent) | GPL-3.0 per source header | N/A — code, not model | Not redistributed |

### Nothing is ND

**No component in the chain carries a NoDerivatives clause.** This was checked
specifically, because ND would be disqualifying in a way NC is not: NC only
restricts commercial use, whereas ND forbids distributing modified versions at
all — and decimation *is* modification. An ND component would be unusable here
even in a tool that is never distributed commercially.

Since nothing is ND, the two-tier decimation the viewer needs is permitted for
every component that survives the exclusions below.

### The unstated licence is the sharper problem

The NC components are a known, bounded quantity. **"Brainder" and "White
matter" carry no licence statement at all**, which is worse: absent a grant the
default is all rights reserved, and it cannot be assumed CC BY-SA merely
because the surrounding work is. Both are brain/CNS assets referenced by
nothing in the MVMT structure map, so excluding them costs nothing — which is
why they are excluded rather than researched.

### On BodyParts3D's version upgrade

CC BY-SA 2.1 Japan permits distributing adaptations under a later version of
the same licence, which is the basis for treating the BodyParts3D-derived
geometry as redistributable under CC BY-SA 4.0. This is the standard reading
and the one Z-Anatomy itself relies on. Recorded here as a stated assumption
rather than a certainty. It is not legal advice.

## Authors

Kousaku Okubo (original BodyParts3D model) · Gauthier Kervyn (design, 3D,
anatomy) · Marcin Zielinski (Blender add-on) · Lluis Vinent (Unity
development) · Ana Teresa Bigio, Carlos Torres Villar, Paola Perin, Daniele
Cossellu, Elisa Vivado, Jadwiga Palosz, Shariar Ahmadpour (translations of the
anatomical structures).
