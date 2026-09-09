# Our layers on the BodyParts3D body

What `tools/bp3d_fit.py` and `tools/bp3d_export.py` did on 2026-09-08, re-run on
2026-09-09 with one fit-confidence rule per system and the corrected canal, read
back from `bp3d-fit.json`, `bp3d-export.json` and the merged `atlas.json` in
mvmt-atlas. The renders are in [`bp3d/`](bp3d/).

## The fit

The 42 landmark rules of `tools/landmark_anchors.py` were run on the BodyParts3D
bones (right bones with the left rule mirrored) and matched to `landmarks.json`.
77 pairs resolved; the bicipital groove fails on the right humerus, whose 794
vertices leave the rule's 4 mm band empty, and is reported rather than patched.
Global similarity by Umeyama, then a residual similarity per MVMT region on that
region's landmarks, blended by a Gaussian of distance to the region's landmarks
(sigma 12 cm). Each part is blended from its home region and that region's
neighbours only, because the hand hangs beside the abdomen in the A-pose and the
wrist's residual otherwise reaches the abdominal fascia.

| Stage | RMS | Median | Max |
|---|---|---|---|
| Global similarity (scale 0.9995, rotation 0.75°) | 15.1 mm | 14.6 mm | 24.7 mm |
| Blended per-region | 7.7 mm | 6.1 mm | 20.6 mm |

Per region, RMS before → after the residual fit (points, scale): head-jaw
11.2 → 5.2 (12, 1.055), cervical 11.1 → 7.0 (10, 0.987), shoulder 13.2 → 5.4
(16, 0.966), thoracic 12.8 → 5.3 (11, 0.960), lumbar 18.3 → 8.4 (9, 0.993),
hip 20.9 → 6.1 (13, 1.006), knee 13.2 → 10.5 (12, 1.014), elbow-wrist
14.2 → 0.9 (14, 0.970), ankle-foot 16.6 → 8.1 (12, 1.042).

Three rules were under-specified for a second body and were tightened as
descriptions (scapular spine "in the upper half of the bone"; sustentaculum tali
"in the top 15 mm and the anterior half"; Gerdy's tubercle "at least a
centimetre lateral of the tuberosity, on the anterior face"). No Z-Anatomy
point moved; `landmarks.json` was regenerated and `verify_landmarks` passes.

Six landmarks exceed 10 mm on their worse side and carry `fitConfidence: low`
in the exported landmark parts, with the residual beside it: Gerdy's tubercle
20.6, superior nuchal line 16.6, ASIS 12.6, knee joint line 11.8, fibular head
11.7, ulnar styloid 10.2. The other 36 carry `high`.

## What went across

| System | Parts | Triangles | Treatment |
|---|---:|---:|---|
| fascia | 165 | 201,678 | transformed as geometry |
| ligaments (joints & ligaments) | 409 | 163,607 | transformed as geometry |
| insertions | 705 | 63,843 | transformed, then projected onto BP3D bone |
| peripheral-nerves | 16 | 30,912 | tubes rebuilt from the authored centrelines through the fit, tapered; schematic |
| central-nerves | 120 | 35,656 | cervical roots and lumbosacral plexus through the fit; spinal cord, 80 roots, 30 cauda strands and dura authored here through the BP3D canal; schematic |
| landmarks | 77 | 1,540 | the BP3D rule results, as 4 mm spheres |
| muscular | 36 | 144,234 | the muscles BodyParts3D lacks, transformed as geometry (see "Muscles BodyParts3D lacks" below); the epicranial aponeurosis with them, as fascia |

Every part carries `source` (`zanatomy` or `schematic`), `sourceName`, `region`,
the regions it spans, the MVMT structures that claim it, and its FMA concept
where BP3D has one. Skeletal meshes are BP3D's own and did not come across;
muscular meshes are BP3D's own except the thirteen structures it does not
model. Collection 7 (spinal dura, spinal ganglia) was not exported: its
licence scope is unchecked, and it is a possible later addition.

## Insertions: projection onto BP3D bone

A patch is projected onto the BP3D bone of the same name as the Z-Anatomy bone
it sits on (found from Z-Anatomy's own skeleton in the region files), so an
insertion stays on its bone; the name map covers vertebrae (Vertebra T10 →
tenth thoracic vertebra), phalanges (fifth finger of foot → little toe) and the
odd wrist bone. The side comes from the bone the patch sits on, not from the
name: 25 insertion names end in `.l` while their geometry lies on the right
bone (pronator quadratus, piriformis, the plantar interossei, the serrati and
others; the list is in `bp3d-export.json`). That is a finding about the source
export as much as about this one.

| | Count |
|---|---:|
| patches | 705 |
| on bone in the source, projected onto the same-named BP3D bone | 697 |
| on soft tissue in the source (rectus abdominis, external oblique origin 5), left to the fit | 4 |
| on a bone BP3D lacks (costal cartilages 8 and 10), left to the fit | 4 |
| moved more than 5 mm in projection, by the patch's mean vertex shift | 148 |
| moved more than 5 mm at their furthest vertex | 303 |
| mean of the per-patch mean shifts | 4.4 mm (median 2.1 mm) |

The largest shifts are the toe insertions (extensor and flexor digitorum longus
at 30 to 32 mm): BP3D's toes sit 3 cm from where Z-Anatomy's do and no landmark
reaches them, so the fit is honest there and the projection puts each patch
on the right phalanx. Landmarks confirm as on bone: every one of the 77 sits
0.2 to 2.0 mm off the BP3D bone its rule ran on.

## Seams

For structures spanning two regions, the residual displacement (blended fit
minus global fit) was compared along every mesh edge whose two vertices fall
in different regions. Max difference per boundary, and per centimetre of edge:

| Boundary | Max Δ | Max Δ per cm | Structures crossing |
|---|---:|---:|---|
| lumbar / thoracic | 10.5 mm | 1.86 mm/cm | investing abdominal fascia, linea alba, posterior layer of thoracolumbar fascia |
| hip / lumbar | 7.4 mm | 0.67 mm/cm | investing abdominal fascia, linea alba, fascia lata, iliotibial tract, sciatic nerve |
| hip / knee | 5.9 mm | 1.85 mm/cm | fascia lata, iliotibial tract, sciatic nerve |
| ankle-foot / knee | 3.6 mm | 1.69 mm/cm | crural fascia, common fibular and tibial nerves |
| elbow-wrist / shoulder | 2.0 mm | 0.93 mm/cm | brachial fascia, median, radial and ulnar nerves |

The 10.5 mm is on a 6 cm edge of the thoracolumbar fascia; no boundary exceeds
2 mm per cm of edge, which is a gradient, not a kink, and none is visible in
the renders. The erector spinae fascia is not a mesh of ours (the SBL station is
the muscles, which are BP3D's), so it has no seam to check.

## The schematic spinal cord

The cord follows published cross-sections (8 x 6 mm in the thorax, 13 x 7 mm at
the cervical enlargement, 12 x 8 mm at the lumbar) through the BP3D vertebral
canal, from 2 cm above the atlas (the foramen magnum) to the conus in the body
of L1, in three segments (cervical, thoracic, lumbar) so each region's chunk
holds its own. Dorsal and ventral roots leave it at every level from C1 to L1,
descend inside the canal to the height of their foramen and turn out through
it; below the conus thirty cauda strands run down the canal to the lumbar
foramina and the sacral foramina. A dura sheath 3.5 mm wider than the cord runs
from the foramen magnum to S2. All of it `authored: true, source: "schematic"`,
the same flags the nerves carry.

**The canal is read from the bone, and the first reading was wrong.** Phase 4
found it per vertebra as "the largest midline gap between vertices at
mid-height", and recorded gaps of 10 to 22 mm in the neck and thorax and 33 to
36 mm at L3 to L5. The 33 to 36 mm was the lumbar vertebral body: at mid-height
the body's front and back walls leave few vertices on the midline, so the
largest gap between vertices is the body's own thickness from T1 down, and
the cord below C7 was authored through bone. It is a wrong description, the
failure class CLAUDE.md separates from a wrong coordinate, and the fit rule
for central nerves (below) is what found it. The canal is now "the empty
stretch immediately posterior to the body, at mid-height on the midline",
solid and empty read with the winding number along the sagittal line, and its
width is the interpedicular distance: the narrowest empty stretch across the
midline over seven heights through the vertebra, at six depths in the
anterior half of the canal (a line further back runs between the laminae to
the transverse processes and reads 70 mm, one at the body wall clips its
corners and reads 6 mm). AP 14 to 20 mm from C2 to L5 and 34 mm at the atlas;
transverse 20 to 27 mm in the neck, 13 to 18 mm in the thorax, 18 to 22 mm in
the lumbar spine. The record keeps both per vertebra.

The intervertebral foramina are found as passages, not points: the height and
depth nearest the interspace at which a line from inside the canal to 6 mm
beyond the pedicles meets no bone, in the anterior third of the canal's
depth. 42 of the 50 moved from the interspace's midpoint, by a median of
4.1 mm and at most 8.9 mm (T6); at T4 and T5 no fully clear passage exists on
this decimated skeleton (1 to 3 of 10 steps in bone), which is why those
roots stay low below. The dura is the norm's sheath held to three quarters of
the canal's half-width and half-depth where the norm would reach past that
(14 mm AP at C5 here): the canal is not an ellipse and its corners are bone.
[`bp3d/spine-cord-midsagittal.png`](bp3d/spine-cord-midsagittal.png) is the
skeleton cut at the midline with the cord in the canal from skull base to
sacrum.

## Fit confidence, one rule per system

Phase 4 judged every carried-over part by one rule, the fraction of sampled
vertices further than 6 mm from any BP3D bone or muscle surface. That is a fit
test for a ligament or a fascia, which sit on bone and muscle, and a clearance
test for a nerve, which sits in soft tissue by design: it flagged the cord for
being in the middle of its canal and the sciatic for being in the middle of the
thigh. Each system now has its own rule, named in every part's `fitRule`, and
`low` means more than 20% of the part's sampled vertices fail it:

| System | Rule | Low before | Low now |
|---|---|---:|---:|
| ligaments | `surface`: further than 6 mm from any BP3D bone or muscle surface | 23 / 409 | 23 / 409 |
| fascia | `surface`, the same | 52 / 165 | 52 / 165 |
| central nerves | `canal`: inside bone, the vertebral canal wall; the median clearance from the wall is recorded (`fitWallClearance`), not judged | 44 / 120 | 9 / 120 |
| peripheral nerves | `envelope`: outside the body envelope (BP3D's skin) or inside bone; no surface-distance test | 10 / 16 | 0 / 16 |
| muscles carried from Z-Anatomy | `envelope`, the same; the surface distance is recorded, not judged | - | 14 / 36 |

Two things about the BodyParts3D meshes decided how "inside" is measured.
Its skin is a two-layer shell about 2 mm thick, so ray parity is even for
every point inside the body; a point is enclosed when a ray in each of the
six axis directions meets the skin. Its bones are open meshes (480 boundary
edges on L3, 792 on the atlas, 992 on the skin), so a ray through an open
lamina crosses once and parity calls the canal bone; inside bone is the
generalised winding number against every bone whose box comes within 2 cm,
which reads 0 or 1 cleanly on these meshes because their faces are
consistently oriented (checked on eight bones and the skin). Ray parity was
what CLAUDE.md prescribed for the Z-Anatomy meshes, whose problem is winding,
not holes; it is the wrong tool here.

The nine central parts still low are five roots at 21 to 23% in bone (T4
dorsal and ventral left, T9 dorsal left, T10 dorsal both sides, where the
passage is not fully clear) and the four S2 cauda strands at 22%, which cross
the sacrum's anterior wall on the way to a sacral foramen the decimated
sacrum does not resolve as a hole. The cord's three segments are at 0 to 4.5%
with 4 to 6 mm of clearance from the wall, the dura's at 5 to 19%. Every
peripheral nerve is under 6% in bone (the tibial behind the tibia) and under
5% outside the skin (the median and common fibular at the wrist and knee); the
record holds every nerve's fractions, low or not.

## Muscles BodyParts3D lacks

The depth match in mvmt-atlas reported 29 MVMT muscle structures with no
BodyParts3D concept. A substring search of BP3D's part names (latissimus,
rectus abdom, obliq, masseter, temporal, rhomb, multifid, quadratus lumb,
transvers, pterygoid, occipit, frontal, epicran, psoas, spinalis, rotator,
digitorum brevis, articularis) and renders of the muscle layer
(`verification/carried-muscles/` in mvmt-atlas: the back with no latissimus,
the abdomen with the external oblique alone) sort them three ways:

| | Structures | What |
|---|---|---|
| BP3D's names, not absences | rhomboids, rotatores, hamstring origin | sided concepts ("right rhomboid major"), "rotator" for rotatores, a group of present muscles; matched in `CONCEPT_MATCHES` |
| nothing to carry | common extensor origin, common flexor origin, articularis genus, psoas minor | attachment sites with no belly in Z-Anatomy either; psoas minor absent from both |
| genuinely absent, carried | masseter (both parts), temporalis, medial and lateral pterygoid (both heads), occipitofrontalis (frontalis, occipitalis, epicranial aponeurosis), latissimus dorsi, multifidus (cervical, thoracic, lumbar), quadratus lumborum, transversus abdominis, internal oblique, rectus abdominis, spinalis capitis, extensor digitorum brevis | 13 structures, 38 Z-Anatomy meshes: 36 muscular parts (144,234 triangles) and the two aponeuroses as fascia |

`CARRIED_MUSCLES` in `tools/bp3d_export.py` names the structures; the meshes
come from the join, and the build stops if a carried name is a BP3D concept
(the external oblique is BP3D's, so "Obliques" is not listed and only the
internal is carried) or a listed mesh is not in the region files. They are
transformed through the fit like the fascia, land in their home region's
chunk, and reach the viewer as Muscles with `source: zanatomy` and `carried`
set, take their depth from the structure that claims them (367 of 452 muscle
parts classified now, 20 carried structures), and light as full stations on
the fascial lines: the SBL's occipitofrontalis and the SFL's rectus abdominis
flipped from "attachments only" to full with nothing changed in the viewer,
as did the internal oblique, temporalis, medial pterygoid and latissimus
dorsi; only the patellar tendon and the common extensor origin remain
attachments only. Renders:
[`bp3d/body-carried-muscles-anterior.png`](bp3d/body-carried-muscles-anterior.png),
[`bp3d/body-carried-muscles-posterior.png`](bp3d/body-carried-muscles-posterior.png).

Their fit is judged by the envelope rule, not the surface one: the surface
set is BP3D's bones and muscles, and where these muscles live BP3D has no
neighbours to measure against, so the rectus abdominis, internal oblique and
transversus read 48 to 59% of their surface further than 6 mm from anything
for sitting exactly where BP3D has nothing (median 7 to 9 mm; recorded as
`fitFarFraction`, not judged). 14 of the 36 are low, all for bone: the deep
part of the masseter (36%), the pterygoids (21 to 55%), the multifidus in the
neck and thorax (22 to 27%) and spinalis capitis (26%) intersect the ramus,
the pterygoid plates and the laminae they lie on by the fit's own error; the
rest are under 20%, and every one is inside the skin (frontalis 10% and
occipitalis 15% outside it, the scalp being thinner here than on the fit's
source). The abdominal wall's seams (lumbar / thoracic, hip / lumbar) are
under 2.2 mm on the bellies and 3.6 mm on the rectus patches.

## Chunks

One chunk per region, holding only that region's parts (gzipped): head-jaw
0.63 MB, cervical 0.44, shoulder 1.03, thoracic 0.83, lumbar 1.70, hip 1.49,
knee 0.58, elbow-wrist 0.74, ankle-foot 0.73 (8.2 MB in all; the head-jaw
and lumbar chunks grew with the muscles carried into them). A part lives in
its home region's chunk; the parts that span into a neighbouring region are
listed under that region's `spanningParts` in `atlas.json`. BP3D's own 15
chunks are untouched.

The whole-body overview (`atlas.overview`) simplifies every part, BP3D's and
ours: 635,612 triangles from 2,949,854 (22%), 9.1 MB gzipped, in 4 chunks.
Quadric simplification at a 3% relative error bound stops early on thin
vessels and flat patches, so some parts fall back to the topology-free sloppy
simplifier.

## Names, ids and fascial lines

Every exported part and MVMT structure is a searchable concept in
`atlas.json`, so `?select=`, `postMessage select` and search accept our ids
(`knee-acl`, `lm-asis`, `ZA-iliotibial-tract`) as they do FMA ids. The FMA
match table (`public/models/mvmt-fma-match.json` in mvmt-atlas) matches our
names to BP3D concepts by normalised token set: fascia 9 of 84 names,
ligaments 7 of 234, insertions 0 of 705, landmarks 0 of 42. BP3D's vocabulary
barely covers ligaments and has nothing for insertion patches, so the FMA ids
on the systems we add are sparse by the nature of the source, not the match.

The twelve fascial lines keep their named-structure storage
(`public/models/fascial-lines.json`): each station resolves at build to our
exported concept and to every BP3D concept under the same normalised name
(BP3D holds many muscles as sided pairs, so a name is several concepts and a
match must return all of them), with `CONCEPT_MATCHES` in mvmt-atlas's
`scripts/overrides.mjs` for the structures BP3D names differently, the same
table that gives BP3D's muscles their depth. Each station records what it
resolved to, a `status` and its mesh count per side. 92 stations: 79 resolve
to the structure itself, 13 to its insertion patches alone because BP3D has no
belly for it (occipitofrontalis, temporalis, medial pterygoid, latissimus
dorsi, rectus abdominis, internal oblique, patellar tendon, the common
extensor origin), none to nothing; every bilateral station resolves on both
sides. The viewer lights the stations and ghosts the rest of the body, and
says on the row when a station is attachments only.
