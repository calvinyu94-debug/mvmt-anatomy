# Exclusions

Objects that must never enter an exported asset, and why.

**This file is the authoritative list.** It is derived from `inventory.csv`,
not hand-maintained, and the export pipeline is expected to enforce it
programmatically and assert the resulting counts — not to rely on anyone
remembering.

Every exclusion here is a **licence** exclusion. Payload trimming (labels,
reference planes, curves) is a separate concern and is described at the end.

See [ATTRIBUTION.md](ATTRIBUTION.md) for the full licence breakdown.

## Summary

| Set | Objects | With geometry | Triangles | Reason |
|---|---:|---:|---:|---|
| `brain_cns` | 96 | 61 | 413,041 | no licence stated upstream |
| `inner_middle_ear` | 61 | 17 | 30,574 | CC BY-NC-SA 4.0 |
| `kidney_renal` | 15 | 4 | 8,016 | CC BY-NC 4.0 |
| **Total** | **172** | **82** | **451,631** | **11.02% of all triangles** |

Nothing in the MVMT structure map references any excluded object. This was
checked mechanically: no excluded object name contains any keyword from the
116-structure map. Removing all of them costs the map nothing.

## Verification

The export pipeline must assert these counts against a fresh inventory. If a
count moves, either the upstream model changed or a pattern has drifted — both
are reasons to stop, not to proceed.

```python
EXPECTED = {
    "brain_cns": {"objects": 96, "with_geometry": 61, "triangles": 413041},
    "inner_middle_ear": {"objects": 61, "with_geometry": 17, "triangles": 30574},
    "kidney_renal": {"objects": 15, "with_geometry": 4, "triangles": 8016},
}
```

## Brain and intracranial CNS

**Source:** "Brainder" / "White matter" (University of Washington) — **no licence stated upstream**

Absent a licence grant the default is all rights reserved. Z-Anatomy does not say which brain geometry came from the University of Washington assets and which came from BodyParts3D, so the whole intracranial CNS block is excluded rather than guessed at.

**Matched:** 96 objects, 61 carrying geometry, 413,041 triangles.

<details>
<summary>Match pattern (case-insensitive, on <code>object_name</code>)</summary>

```regex
telencephalon|diencephalon|mesencephalon|metencephalon|myelencephalon|cerebrum|cerebral|cerebell|\bpons\b|medulla oblongata|brainstem|brain stem|thalam|hypothalam|epithalam|subthalam|hippocamp|amygdal|corpus callosum|basal (nuclei|ganglia)|caudate|putamen|globus pallidus|claustrum|internal capsule|corona radiata|fornix of brain|septum pellucidum|commissural fibres|projection fibres|association fibres|arcuate fasciculus|olfactory (bulb|tract)|optic (chiasm|radiation)|pituitary|hypophysis|pineal|choroid plexus|ventricle of brain|lateral ventricle|third ventricle|fourth ventricle|cerebrospinal|arachnoid|pia mater of brain|dura mater of brain|cranial dura|falx|tentorium|red nucleus|substantia nigra|locus (coeruleus|ceruleus)|superior colliculus|inferior colliculus|corpus striatum|insula\b|white matter of telencephalon|grey matter of telencephalon
```

</details>

| Object | Triangles |
|---|---:|
| `White matter of telencephalon.l` | 135,288 |
| `White matter of telencephalon.r` | 135,288 |
| `Hippocampal commissure` | 10,213 |
| `Pons.l` | 10,171 |
| `Pons.r` | 10,171 |
| `Superior cerebellar peduncle.l` | 8,474 |
| `Superior cerebellar peduncle.r` | 8,474 |
| `Medulla oblongata.l` | 6,080 |
| `Medulla oblongata.r` | 6,080 |
| `Fourth ventricle` | 5,798 |
| `Globus pallidus.l` | 5,276 |
| `Globus pallidus.r` | 5,276 |
| `Third ventricle` | 4,315 |
| `Hypothalamus` | 4,258 |
| `Corpus callosum` | 3,996 |
| `Tonsil of cerebellum.l` | 3,638 |
| `Tonsil of cerebellum.r` | 3,638 |
| `Lateral ventricle.l` | 2,898 |
| `Lateral ventricle.r` | 2,898 |
| `Choroid plexus.l` | 2,647 |
| `Choroid plexus.r` | 2,647 |
| `Caudate nucleus.l` | 2,570 |
| `Caudate nucleus.r` | 2,570 |
| `Septum pellucidum` | 2,388 |
| `Tentorium cerebelli.l` | 2,108 |
| `Tentorium cerebelli.r` | 2,108 |
| `Falx cerebri` | 1,675 |
| `Putamen.l` | 1,150 |
| `Putamen.r` | 1,150 |
| `Lingula of cerebellum` | 1,028 |
| `Hippocampus.l` | 1,020 |
| `Hippocampus.r` | 1,020 |
| `Pyramid of medulla oblongata.l` | 960 |
| `Pyramid of medulla oblongata.r` | 960 |
| `Optic chiasm.l` | 890 |
| `Optic chiasm.r` | 890 |
| `Medial occipitotemporal gyrus (Parahippocampal*).l` | 858 |
| `Medial occipitotemporal gyrus (Parahippocampal*).r` | 858 |
| `Stria medullaris thalami.l` | 842 |
| `Stria medullaris thalami.r` | 842 |
| `Circular sulcus of insula.l` | 798 |
| `Circular sulcus of insula.r` | 798 |
| `Thalamus.l` | 758 |
| `Thalamus.r` | 758 |
| `Insula (Subcentral gyrus and ant. and post. sulci*).l` | 740 |
| `Insula (Subcentral gyrus and ant. and post. sulci*).r` | 740 |
| `Adenohypophysis` | 680 |
| `Pineal gland` | 634 |
| `Neurohypophysis` | 592 |
| `Inferior colliculus.l` | 464 |
| `Inferior colliculus.r` | 464 |
| `Superior colliculus.l` | 458 |
| `Superior colliculus.r` | 458 |
| `Amygdaloid body.l` | 384 |
| `Amygdaloid body.r` | 384 |
| `Red nucleus.l` | 160 |
| `Red nucleus.r` | 160 |
| `Anterior spinocerebellar tract` | 58 |
| `Posterior spinocerebellar tract` | 58 |
| `Lateral spinothalamic tract` | 44 |
| `Anterior spinothalamic tract` | 40 |
| `Anterior median fissure of medulla oblongata.j` | — *(label anchor)* |
| `Anterolateral sulcus of medulla oblongata.j` | — *(label anchor)* |
| `Basilar part of pons.j` | — *(label anchor)* |
| `Brainstem.j` | — *(label anchor)* |
| `Caudate lobe.j` | — *(label anchor)* |
| `Cerebellar fossa.j` | — *(label anchor)* |
| `Cerebellar peduncles.j` | — *(label anchor)* |
| `Cerebellum.j` | — *(label anchor)* |
| `Cerebral arterial circle.j` | — *(label anchor)* |
| `Cerebral fossa.j` | — *(label anchor)* |
| `Cerebral hemisphere.j` | — *(label anchor)* |
| `Cerebral peduncle.j` | — *(label anchor)* |
| `Cerebral surface of greater wing.j` | — *(label anchor)* |
| `Cerebrum.j` | — *(label anchor)* |
| `Commissural fibres of telencephalon.j` | — *(label anchor)* |
| `Corpus striatum.j` | — *(label anchor)* |
| `Diencephalon.j` | — *(label anchor)* |
| `Grey matter of medulla oblongata.j` | — *(label anchor)* |
| `Hypophysis.j` | — *(label anchor)* |
| `Inferior medulla oblongata.j` | — *(label anchor)* |
| `Insula.j` | — *(label anchor)* |
| `Lateral funiculus of medulla oblongata.j` | — *(label anchor)* |
| `Pars distalis of hypophysis.j` | — *(label anchor)* |
| `Pars intermedia of hypophysis.j` | — *(label anchor)* |
| `Pars nervosa of hypophysis.j` | — *(label anchor)* |
| `Pars tubelaris of hypophysis.j` | — *(label anchor)* |
| `Posterior median sulcus of medulla oblongata.j` | — *(label anchor)* |
| `Posterolateral sulcus of medulla oblongata.j` | — *(label anchor)* |
| `Projection fibres of telencephalon.j` | — *(label anchor)* |
| `Pyramid of medulla oblongata.j` | — *(label anchor)* |
| `Superior medulla oblongata.j` | — *(label anchor)* |
| `Tegmentum of pons.j` | — *(label anchor)* |
| `Telencephalon.j` | — *(label anchor)* |
| `Walls of lateral ventricle.j` | — *(label anchor)* |
| `White matter of diencephalon.j` | — *(label anchor)* |

## Inner and middle ear

**Source:** "Anatomy of the Inner Ear" (University of Dundee School of Medicine) — **CC BY-NC-SA 4.0**

NC is incompatible with CC BY-SA 4.0 share-alike. The auditory ossicles are filed under `1: Skeletal system` and may well be BodyParts3D rather than Dundee, but upstream does not distinguish them, so they are excluded conservatively.

**Matched:** 61 objects, 17 carrying geometry, 30,574 triangles.

<details>
<summary>Match pattern (case-insensitive, on <code>object_name</code>)</summary>

```regex
cochlea|cochlear (duct|nerve|canal)|semicircular|bony labyrinth|membranous labyrinth|\bincus\b|\bmalleus\b|\bstapes\b|tympanic (membrane|cavity)|auditory ossicle|utricle|saccule|spiral organ|organ of corti|endolymph|perilymph|oval window|round window|vestibular (aqueduct|duct|nerve|ganglion)|internal acoustic|auditory tube|middle ear|inner ear|internal ear
```

</details>

| Object | Triangles |
|---|---:|
| `Stapes.l` | 4,342 |
| `Stapes.r` | 4,342 |
| `Malleus.l` | 3,982 |
| `Malleus.r` | 3,982 |
| `Incus.l` | 2,532 |
| `Incus.r` | 2,532 |
| `Cochlear nerve` | 1,758 |
| `Tympanic membrane.l` | 1,572 |
| `Tympanic membrane.r` | 1,572 |
| `Cochlea.l` | 1,540 |
| `Cochlea.r` | 1,540 |
| `Posterior cochlear nucleus.l` | 224 |
| `Posterior cochlear nucleus.r` | 224 |
| `Auditory tube.l` | 168 |
| `Auditory tube.r` | 168 |
| `Anterior cochlear nucleus.l` | 48 |
| `Anterior cochlear nucleus.r` | 48 |
| `Anterior limb of stapes.i` | — *(label anchor)* |
| `Anterior limb of stapes.j` | — *(label anchor)* |
| `Anterior process of malleus.i` | — *(label anchor)* |
| `Anterior process of malleus.j` | — *(label anchor)* |
| `Anterior semicircular canal.j` | — *(label anchor)* |
| `Articular facet for malleus.i` | — *(label anchor)* |
| `Articular facet for malleus.j` | — *(label anchor)* |
| `Articular facet for stapes.i` | — *(label anchor)* |
| `Articular facet for stapes.j` | — *(label anchor)* |
| `Articular facet of head of malleus.i` | — *(label anchor)* |
| `Articular facet of head of malleus.j` | — *(label anchor)* |
| `Articular facet of head of stapes.i` | — *(label anchor)* |
| `Articular facet of head of stapes.j` | — *(label anchor)* |
| `Auditory ossicles.j` | — *(label anchor)* |
| `Base of cochlea.j` | — *(label anchor)* |
| `Base of stapes.i` | — *(label anchor)* |
| `Base of stapes.j` | — *(label anchor)* |
| `Body of incus.i` | — *(label anchor)* |
| `Body of incus.j` | — *(label anchor)* |
| `Cochlear cupula.j` | — *(label anchor)* |
| `Handle of malleus.i` | — *(label anchor)* |
| `Handle of malleus.j` | — *(label anchor)* |
| `Head of malleus.i` | — *(label anchor)* |
| `Head of malleus.j` | — *(label anchor)* |
| `Internal ear.j` | — *(label anchor)* |
| `Joints of auditory ossicles.j` | — *(label anchor)* |
| `Lateral process of malleus.i` | — *(label anchor)* |
| `Lateral process of malleus.j` | — *(label anchor)* |
| `Lateral semicircular canal.j` | — *(label anchor)* |
| `Lenticular process of incus.i` | — *(label anchor)* |
| `Lenticular process of incus.j` | — *(label anchor)* |
| `Long limb of incus.i` | — *(label anchor)* |
| `Long limb of incus.j` | — *(label anchor)* |
| `Middle ear.j` | — *(label anchor)* |
| `Muscles of auditory ossicles.j` | — *(label anchor)* |
| `Neck of malleus.i` | — *(label anchor)* |
| `Neck of malleus.j` | — *(label anchor)* |
| `Posterior limb of stapes.i` | — *(label anchor)* |
| `Posterior limb of stapes.j` | — *(label anchor)* |
| `Posterior semicircular canal.j` | — *(label anchor)* |
| `Spiral canal of cochlea.j` | — *(label anchor)* |
| `Stapes.i` | — *(label anchor)* |
| `Stapes.j` | — *(label anchor)* |
| `Sulcus of auditory tube.j` | — *(label anchor)* |

## Kidney and renal collecting system

**Source:** "Kidney" (Lissie Cowley) — **CC BY-NC 4.0**

NC is incompatible with CC BY-SA 4.0 share-alike. Suprarenal (adrenal) glands are anatomically distinct and are NOT excluded; they sit outside Cowley's stated scope.

**Matched:** 15 objects, 4 carrying geometry, 8,016 triangles.

<details>
<summary>Match pattern (case-insensitive, on <code>object_name</code>)</summary>

```regex
\bkidney|\brenal\b|nephron|\bureter|renal (pelvis|calix|calyx)|minor calix|major calix
```

</details>

| Object | Triangles |
|---|---:|
| `Kidney.l` | 2,982 |
| `Kidney.r` | 2,322 |
| `Renal pelvis.l` | 1,450 |
| `Renal pelvis.r` | 1,262 |
| `Anterior surface of kidney.j` | — *(label anchor)* |
| `Hilum of kidney.j` | — *(label anchor)* |
| `Inferior pole of kidney.j` | — *(label anchor)* |
| `Lateral border of kidney.j` | — *(label anchor)* |
| `Medial border of kidney.j` | — *(label anchor)* |
| `Posterior surface of kidney.j` | — *(label anchor)* |
| `Renal impression of liver.j` | — *(label anchor)* |
| `Renal impression of spleen.j` | — *(label anchor)* |
| `Renal sinus.j` | — *(label anchor)* |
| `Renal surface of suprarenal gland.j` | — *(label anchor)* |
| `Superior pole of kidney.j` | — *(label anchor)* |

## Not excluded, but worth recording

**Cranial Nerves and Foramina** (University of Dundee, CAHID) is **CC BY 4.0**,
which is one-way compatible into a CC BY-SA 4.0 work. It needs attribution, not
exclusion. The structure map references no cranial nerve, so it will most likely
be dropped from exports anyway — as payload, not on licence grounds.

**Structure definitions** carried in the .blend derive from Wikipedia
(CC BY-SA 3.0). They are compatible, but the viewer uses the MVMT map's own
`action` and `clinical` copy, so definitions should simply not be exported.

**The Blender add-on code** (`__init__.py`, `Anatomy-shortcuts.py`) is GPL-3.0
per its own header. It is a tool, not model data. Do not vendor it into this
repository — a GPL file in a CC BY-SA repo creates a licence conflict that does
not otherwise exist.

## Payload exclusions — not licence-driven

Recorded here so the export filter has one place to look, but these are dropped
because they are useless to the viewer, not because of any licence.

| What | Match | Objects | Triangles |
|---|---|---:|---:|
| Label text | `object_type == "FONT"` | 1,660 | 0 |
| Label leaders / anchors | name ends `.j`, `.t`, `.g`, or contains `-txt` | 2,546 | 7,191 |
| Curves | `object_type == "CURVE"` | 951 | 0 |
| Reference planes and lines | collection contains `Reference lines` | 54 | 3,936 |
| Cross-section planes | collection `Cross section planes` | 3 | 0 |
| Lights and camera | `object_type in ("LIGHT", "CAMERA")` | 4 | 0 |

The viewer draws its own labels from the structure map, so none of the atlas's
label infrastructure is needed.
