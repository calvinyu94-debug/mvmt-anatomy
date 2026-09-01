"""Waypoint specification for the authored peripheral nerves.

These paths are SCHEMATIC. They are not derived from imaging or cadaveric data,
unlike every other mesh in this project. See ATTRIBUTION.md.

Each waypoint is anchored to a landmark object rather than hardcoded, so the
paths follow if the source geometry is ever updated:

    ("Humerus.l", (u, v, w), (dx, dy, dz))

    u, v, w   normalised position in that object world bounding box, 0..1 on X, Y, Z
    dx,dy,dz  offset in metres applied afterwards

Coordinate system, established by tools/inventory.py:
    metres, Z up (superior), +X left, -Y anterior.
    Author the left side only; the right is mirrored by negating X.

On the normalised coordinates
-----------------------------
Several of these bones are oblique in the A-pose the model stands in, so a
bounding-box axis is not an anatomical axis. The humerus runs from X=0.145 at
the head to X=0.249 at the elbow, which means u conflates "medial" with
"proximal" - u=0.55 at the elbow is not the cubital fossa, it is 4 cm medial of
it. Ulna.l has the same problem in reverse: its bounding box reaches X=0.203
only at the olecranon, while the shaft sits at X=0.228 or beyond.

Every waypoint below was therefore checked against the real cross-section of
the surrounding bones at its own height, and against the measured distance to
the nearest skeletal surface. The values are what clears bone and lands on the
correct side of each landmark relationship; tools/verify_nerves.py asserts both.
"""

# Departures from the paths as first specified, with the reason for each.
# Written into nerves.json so the record travels with the geometry.
DEVIATIONS = [
    ("nerve-median", "anchor", "Radius.l -> Flexor retinaculum of wrist.l",
     "Radius.l stops at Z=0.856, proximal to the carpal tunnel at Z~0.85, and "
     "its Y range bottoms out at -0.027, so the tunnel was not reachable "
     "without an offset that no longer tracked the geometry. The retinaculum "
     "is the roof of the tunnel and localises it exactly."),
    ("nerve-median", "anchor", "Radius.l -> Third metacarpal bone.l",
     "The palm is outside Radius.l's bounding box. Anchored to the radius, the "
     "terminus landed dorsal to the metacarpals rather than in the palm."),
    ("nerve-median", "added waypoint", "distal forearm, palmar to the radius",
     "Without it the curve grazed the palmar surface of the distal radius."),
    ("nerve-ulnar", "anchor", "Ulna.l -> Pisiform bone.l",
     "Guyon's canal is bounded by the pisiform. Ulna.l's bounding box is "
     "skewed by the olecranon and does not localise the canal."),
    ("nerve-ulnar", "anchor", "Ulna.l -> Fifth metacarpal bone.l",
     "As for the median terminus: the hand is outside Ulna.l's bounding box."),
    ("nerve-radial", "added waypoint", "distal spiral groove",
     "The nerve turned lateral too early and was anterior to the humerus over "
     "part of the spiral groove, which is the opposite of the relationship "
     "that matters here."),
    ("nerve-brachial-plexus", "added waypoints", "six to nine control points",
     "This is the tightest path in the set. At a 6 mm radius the tube is 12 mm "
     "across and the costoclavicular space in this model is narrower than that "
     "on the direct line: the retroclavicular route pinches to 4.4 mm and the "
     "lateral route to 0.8 mm against the clavicle. The corridor that does fit "
     "runs above the second rib and then behind the clavicle, and holding the "
     "curve inside it needs three clavicle control points rather than one."),
    ("nerve-brachial-plexus", "moved", "axilla lowered from Z~1.38 to Z~1.31",
     "The axilla point sat above the pectoralis minor point, so the path "
     "folded back on itself and the bezier overshot into the rib cage."),
    ("nerve-sciatic", "rerouted", "exits the greater sciatic notch posteriorly",
     "The anterior route is solid bone: measured clearance to the ischium "
     "there is 0.1-3 mm against a 5 mm tube. The nerve now passes posterior to "
     "the ilium into the gluteal region, which is also where it actually runs."),
    ("nerve-common-fibular", "added waypoint", "ankle, deep to the extensor retinaculum",
     "Without it the curve overshot anteriorly out of the shin between the leg "
     "and the foot, and the terminus dived into the tarsus."),
    ("nerve-femoral", "added waypoint", "medial knee, anterior to the condyles",
     "The curve from mid-thigh to the medial leg bowed through the femoral "
     "condyles and the tibia."),
]

NERVES = {

"nerve-brachial-plexus": dict(radius=0.006, waypoints=[
    ("Scalenus anterior muscle.l", (0.70, 0.85, 0.95), (0.000, 0.006, 0.010)),  # roots, lateral to spine
    ("Scalenus anterior muscle.l", (0.91, 1.00, 0.42), (0.000, 0.002, 0.000)),  # between ant/mid scalene
    ("First rib.l",                (0.87, 1.00, 0.86), (0.000, 0.000, 0.000)),  # crossing the first rib
    ("Clavicle.l",                 (0.44, 0.98, 1.00), (0.000, 0.000, 0.001)),  # over the second rib, behind the clavicle
    ("Clavicle.l",                 (0.58, 0.90, 0.58), (0.000, 0.000, 0.000)),  # costoclavicular space
    ("Clavicle.l",                 (0.66, 0.76, 0.31), (0.000, 0.000, 0.000)),  # emerging below the clavicle
    ("Pectoralis minor muscle.l",  (0.83, 0.85, 0.80), (0.000, 0.000, 0.000)),  # lateral border of pec minor
    ("Pectoralis minor muscle.l",  (1.00, 0.86, 0.55), (0.015, 0.000, 0.000)),  # deep to pec minor
    ("Humerus.l",                  (0.13, 0.17, 0.70), (0.000, 0.000, 0.000)),  # into the axilla
]),

"nerve-median": dict(radius=0.003, waypoints=[
    ("Humerus.l",                     (0.13, 0.02, 0.70), ( 0.000,  0.000, 0.000)),  # axilla
    ("Humerus.l",                     (0.32, 0.26, 0.60), ( 0.000,  0.000, 0.000)),  # medial arm, with brachial artery
    ("Humerus.l",                     (0.55, 0.40, 0.06), (-0.004, -0.010, 0.000)),  # cubital fossa, medial to biceps tendon
    ("Ulna.l",                        (0.63, 0.26, 0.78), ( 0.000,  0.000, 0.000)),  # between pronator teres heads
    ("Ulna.l",                        (0.76, 0.23, 0.40), ( 0.000,  0.000, 0.000)),  # forearm midline, deep
    ("Ulna.l",                        (1.00, 0.00, 0.11), ( 0.000, -0.010, 0.000)),  # distal forearm, palmar to the radius
    ("Flexor retinaculum of wrist.l", (0.47, 0.29, 0.32), ( 0.000,  0.000, 0.000)),  # carpal tunnel, deep to the retinaculum
    ("Third metacarpal bone.l",       (0.35, 0.00, 0.47), ( 0.000, -0.004, 0.000)),  # into the palm
]),

"nerve-ulnar": dict(radius=0.003, waypoints=[
    ("Humerus.l",               (0.13, 0.28, 0.70), ( 0.000,  0.000, 0.000)),  # axilla
    ("Humerus.l",               (0.34, 0.55, 0.55), ( 0.000,  0.000, 0.000)),  # medial arm, posterior to median
    ("Humerus.l",               (0.39, 1.00, 0.10), ( 0.000,  0.005, 0.000)),  # behind the medial epicondyle
    ("Ulna.l",                  (0.00, 0.88, 0.85), (-0.005,  0.000, 0.000)),  # cubital tunnel exit
    ("Ulna.l",                  (0.36, 0.35, 0.40), ( 0.000,  0.000, 0.000)),  # medial forearm, on ulna
    ("Pisiform bone.l",         (1.00, 0.00, 0.51), ( 0.002, -0.001, 0.000)),  # Guyon's canal at the wrist
    ("Fifth metacarpal bone.l", (0.50, 0.00, 0.35), ( 0.000, -0.004, 0.000)),  # into the hand
]),

"nerve-radial": dict(radius=0.003, waypoints=[
    ("Humerus.l", (0.13, 0.93, 0.70), (0.000, 0.000, 0.000)),   # axilla, posterior cord
    ("Humerus.l", (0.52, 1.00, 0.60), (0.000, 0.002, 0.000)),   # spiral groove, posterior humerus
    ("Humerus.l", (0.70, 1.00, 0.42), (0.000, 0.007, 0.000)),   # distal spiral groove, still posterior
    ("Humerus.l", (0.94, 0.64, 0.17), (0.000, 0.000, 0.000)),   # lateral, piercing intermuscular septum
    ("Humerus.l", (0.96, 0.25, 0.04), (0.000, 0.000, 0.000)),   # anterior to lateral epicondyle
    ("Radius.l",  (0.50, 0.86, 0.80), (0.000, 0.000, 0.000)),   # into the posterior compartment
    ("Radius.l",  (0.66, 0.68, 0.30), (0.000, 0.000, 0.000)),   # posterior forearm
    ("Radius.l",  (0.77, 0.25, 0.00), (0.000, 0.000,-0.036)),   # dorsum of the hand
]),

"nerve-cervical-roots": dict(radius=0.002, waypoints=[
    ("Scalenus anterior muscle.l", (0.38, 1.00, 1.00), (0.000, 0.002, 0.006)),  # C5
    ("Scalenus anterior muscle.l", (0.44, 1.00, 0.71), (0.000, 0.000, 0.000)),  # C6-C7
    ("Scalenus anterior muscle.l", (0.62, 0.78, 0.31), (0.000, 0.000, 0.000)),  # C8-T1, converging
]),

"nerve-lumbosacral-plexus": dict(radius=0.005, waypoints=[
    ("Sacrum",     (0.75, 0.25, 1.00), (0.010, -0.010, 0.060)),  # L2-L4 roots, anterior to spine
    ("Sacrum",     (0.91, 0.00, 0.85), (0.000, -0.004, 0.000)),  # descending on psoas, anterior to the ala
    ("Hip bone.l", (0.27, 0.39, 0.55), (0.000,  0.000, 0.000)),  # over the pelvic brim, medial to the ilium
    ("Sacrum",     (0.83, 0.09, 0.23), (0.000,  0.000, 0.000)),  # sacral contribution, anterior to piriformis
]),

"nerve-sciatic": dict(radius=0.005, waypoints=[
    ("Piriformis muscle.l", (0.16, 0.29, 0.54), (0.000, 0.000, 0.000)),  # greater sciatic foramen
    ("Piriformis muscle.l", (0.21, 0.63, 0.37), (0.000, 0.000, 0.000)),  # through the notch, posterior to the ilium
    ("Piriformis muscle.l", (0.38, 0.86, 0.00), (0.000, 0.000,-0.006)),  # emerging below piriformis
    ("Femur.l",             (0.55, 0.90, 0.88), (0.000, 0.014, 0.000)),  # posterior thigh, deep to hamstrings
    ("Femur.l",             (0.52, 0.90, 0.50), (0.000, 0.014, 0.000)),  # mid posterior thigh
    ("Femur.l",             (0.60, 0.88, 0.12), (0.000, 0.008, 0.000)),  # bifurcation, popliteal fossa
]),

"nerve-tibial": dict(radius=0.003, waypoints=[
    ("Femur.l",                       (0.60, 0.88, 0.12), (0.000, 0.008, 0.000)),  # from the bifurcation
    ("Tibia.l",                       (0.50, 0.95, 0.92), (0.000, 0.014, 0.000)),  # deep posterior calf
    ("Tibia.l",                       (0.40, 0.95, 0.45), (0.000, 0.012, 0.000)),  # on tibialis posterior
    ("Tibia.l",                       (0.47, 1.00, 0.18), (0.000, 0.002, 0.000)),  # distal calf, still near the midline
    ("Tibia.l",                       (0.42, 1.00, 0.11), (0.000, 0.006, 0.000)),  # turning medially above the malleolus
    ("Medial malleolus.l",            (0.89, 1.00, 0.70), (0.000, 0.006, 0.000)),  # behind medial malleolus
    ("Flexor retinaculum of ankle.l", (0.50, 0.60, 0.25), (0.000, 0.000,-0.006)),  # tarsal tunnel, into sole
]),

"nerve-common-fibular": dict(radius=0.003, waypoints=[
    ("Femur.l",  (0.60, 0.88, 0.12), (0.000, 0.008, 0.000)),  # from the bifurcation
    ("Fibula.l", (0.97, 1.00, 0.96), (0.000, 0.000, 0.000)),  # posterior to the fibular head, on biceps femoris
    ("Fibula.l", (1.00, 0.48, 0.89), (0.004, 0.000, 0.000)),  # wrapping the fibular neck - most superficial point
    ("Fibula.l", (0.64, 0.00, 0.70), (0.000,-0.001, 0.000)),  # into the anterior compartment
    ("Tibia.l",  (0.79, 0.54, 0.30), (0.000, 0.000, 0.000)),  # anterior compartment, lateral to the tibia
    ("Tibia.l",  (0.77, 0.54, 0.18), (0.000, 0.000, 0.000)),  # anterior shin
    ("Tibia.l",  (0.65, 0.26, 0.09), (0.000, 0.000, 0.000)),  # ankle, deep to the extensor retinaculum
    ("Tibia.l",  (0.62, 0.15, 0.04), (0.000, 0.000, 0.000)),  # crossing the ankle joint
    ("Tibia.l",  (0.60, 0.00, 0.00), (0.000,-0.017, 0.001)),  # dorsum of the foot
]),

"nerve-femoral": dict(radius=0.004, waypoints=[
    ("Sacrum",              (0.95, 0.00, 0.85), (0.000,-0.006, 0.000)),  # from the lumbar plexus
    ("Hip bone.l",          (0.40, 0.25, 0.60), (0.000,-0.006, 0.000)),  # on iliacus, lateral to psoas
    ("Inguinal ligament.l", (0.45, 0.50, 0.35), (0.000, 0.004, 0.000)),  # under the inguinal ligament
    ("Femur.l",             (0.33, 0.00, 0.90), (0.000,-0.009, 0.000)),  # anterior thigh
    ("Femur.l",             (0.31, 0.01, 0.55), (0.000, 0.000, 0.000)),  # becoming saphenous
    ("Femur.l",             (0.10, 0.24, 0.09), (0.000, 0.000, 0.000)),  # medial knee, clear of the condyles
    ("Tibia.l",             (0.14, 0.19, 0.91), (0.000, 0.000, 0.000)),  # saphenous, medial knee
]),

}
