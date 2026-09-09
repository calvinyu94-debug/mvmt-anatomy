# Our layers on the BodyParts3D body

What `tools/bp3d_fit.py` and `tools/bp3d_export.py` did on 2026-09-08, read back
from `bp3d-fit.json`, `bp3d-export.json` and the merged `atlas.json` in mvmt-atlas.
The renders are in [`bp3d/`](bp3d/).

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
| peripheral-nerves | 16 | 41,152 | transformed as geometry; schematic |
| central-nerves | 13 | 10,840 | cervical roots and lumbosacral plexus transformed; spinal cord and cauda equina authored here; schematic |
| landmarks | 77 | 1,540 | the BP3D rule results, as 4 mm spheres |

Every part carries `source` (`zanatomy` or `schematic`), `sourceName`, `region`,
the regions it spans, the MVMT structures that claim it, and its FMA concept
where BP3D has one. Skeletal and muscular meshes are BP3D's own and did not
come across. Collection 7 (spinal dura, spinal ganglia) was not exported: its
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

A 5 mm tube through the BP3D vertebral canal, found per vertebra as the largest
midline gap between body and lamina at mid-height (gaps of 10 to 22 mm in the
cervical and thoracic canal, 33 to 36 mm at L3 to L5), from 2 cm above the
atlas (the foramen magnum) to the conus at the L1 mid-height, in three
segments (cervical, thoracic, lumbar) so each region's chunk holds its own;
cauda equina as six 1.2 mm strands fanning from the conus to L5, S1 and S2
through the sacral canal. All of it `authored: true, source: "schematic"`,
the same flags the nerves carry.

## Chunks

One chunk per region, holding only that region's parts (gzipped): head-jaw
0.13 MB, cervical 0.34, shoulder 0.79, thoracic 0.69, lumbar 0.62, hip 1.52,
knee 0.60, elbow-wrist 0.78, ankle-foot 0.70 (6.2 MB in all). A part lives in
its home region's chunk; the parts that span into a neighbouring region are
listed under that region's `spanningParts` in `atlas.json` (head-jaw 90,
cervical 105, shoulder 127, thoracic 41, lumbar 62, hip 31, knee 69,
elbow-wrist 3, ankle-foot 4). BP3D's own 15 chunks are untouched.

The whole-body overview (`atlas.overview`) simplifies every part, BP3D's and
ours: 582,102 triangles from 2,770,928 (21%), 8.4 MB gzipped against 39.1 MB
for the full set, in 4 chunks. Quadric simplification at a 3% relative error
bound stops early on thin vessels and flat patches, so 229 parts fell back to
the topology-free sloppy simplifier.

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
(`public/models/fascial-lines.json`): each station resolves at load to our
exported concept and to the BP3D concept of the same name, with a manual table
for groups BP3D names differently (hamstrings, erector spinae, rotator cuff,
adductors, the first plantar layer). 94 stations; 93 resolve on this body;
the one that does not is the Lateral Line's intercostals (BP3D names each
intercostal space separately, and no group concept matches).
