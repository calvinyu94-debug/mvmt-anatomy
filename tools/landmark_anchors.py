"""The 42 palpable landmarks, each as a rule on the real geometry of one bone.

None of these exist as meshes. Epicondyles, malleoli, the fibular neck and the
rest are label anchors in Z-Anatomy, which the export correctly dropped, so
each becomes a point on a bone, recorded in landmarks.json with the same
anchor scheme the authored nerves use:

    object    the bone the landmark sits on
    uvw       normalised position in that object's world bounding box
    offset    metres, applied afterwards

The bounding-box trap is worse here than it was for the nerves. The model
stands in an A-pose and the long bones are oblique in it, so a normalised
bounding-box coordinate conflates medial with proximal on every limb bone
(CLAUDE.md, "Bounding-box axes are not anatomical axes"). The first-pass uvw
values in the brief were estimated against those boxes and are wrong in most
places - they are kept below as FIRST_PASS so the build can report how far each
one was off, and they decide nothing.

What decides each landmark is its RULE: the anatomical description written as
a selection on the bone's actual vertices. "The most lateral prominence at the
proximal femur" is the femoral vertex with the greatest X. "The most posterior
point of the C7 spinous process" is the C7 vertex with the greatest Y. Where
the description needs a region ("the distal humerus", "the top of the crest")
the rule restricts to a slab measured in metres from the bone's own extent at
that end, never a fraction of the box. The build resolves the rule to a vertex,
pushes it PUSH metres outward along a direction with a positive component along
the rule's own direction - which guarantees the point is outside the bone,
since nothing on the mesh lies beyond its extreme vertex in that direction -
then writes the uvw and offset that reproduce it. The uvw in landmarks.json is
therefore an output of the rule, not an input.

Coordinate system, from tools/inventory.py: metres, Z up (superior), +X left,
-Y anterior. Every rule is written for the LEFT side; the right is the mirror,
by negating X, never by scaling.
"""

from mathutils import Vector

# ----------------------------------------------------------------- helpers

X = Vector((1, 0, 0))          # lateral, on the left side
MED = Vector((-1, 0, 0))       # medial, on the left side
ANT = Vector((0, -1, 0))
POST = Vector((0, 1, 0))
UP = Vector((0, 0, 1))
DOWN = Vector((0, 0, -1))


def unit(*c):
    return Vector(c).normalized()


# The occipital bone has no discrete bump at the midline in this model: its
# posterior profile is smoothly convex with the most posterior point 3 cm
# above where the inion belongs. What it does have is the kink where the
# nuchal plane (sloping ~40 deg, dy/dz ~0.8) turns into the occipital plane
# (dy/dz ~0.2). The extreme vertex in a direction between those two surface
# normals is the vertex on that kink - a supporting plane of intermediate
# slope touches a convex profile exactly at the change of slope.
INION_DIR = unit(0, 1, -0.5)


def bound(b, lo, hi, axis):
    """A bound is None (open), a float in metres, or a string measured from
    the bone's own extent on that axis: "max-0.04", "min+0.035", "mid"."""
    if b is None or isinstance(b, (int, float)):
        return b
    ref = b[:3]
    base = {"min": getattr(lo, axis), "max": getattr(hi, axis),
            "mid": (getattr(lo, axis) + getattr(hi, axis)) / 2.0}[ref]
    return base + (float(b[3:]) if len(b) > 3 else 0.0)


def resolve_bounds(bounds, lo, hi):
    return {ax: (bound(b[0], lo, hi, ax), bound(b[1], lo, hi, ax))
            for ax, b in bounds.items()}


def sel(V, x=None, y=None, z=None):
    """Vertices within the given (lo, hi) bounds on each axis; None is open."""
    out = []
    for v in V:
        if x and ((x[0] is not None and v.x < x[0]) or (x[1] is not None and v.x > x[1])):
            continue
        if y and ((y[0] is not None and v.y < y[0]) or (y[1] is not None and v.y > y[1])):
            continue
        if z and ((z[0] is not None and v.z < z[0]) or (z[1] is not None and v.z > z[1])):
            continue
        out.append(v)
    return out


def ext(V, d, **bounds):
    """The vertex furthest along direction d, within bounds."""
    S = sel(V, **bounds) if bounds else V
    if not S:
        raise ValueError("rule selected no vertices with bounds %r" % (bounds,))
    return max(S, key=lambda v: v.dot(d))


def centroid(V):
    return sum(V, Vector()) / len(V)


def mid(V, axis):
    vals = [getattr(v, axis) for v in V]
    return (min(vals) + max(vals)) / 2.0


# ------------------------------------------------- rules that need two steps


def nuchal_line(V, lo, hi):
    """A third of the way from the inion toward the mastoid, on the ridge.

    The mastoid sits at X~0.07, so a third of the way is X~0.024. The point is
    the most posterior occipital vertex at that X within +/-12 mm of the inion's
    height, which is the ridge itself: the superior nuchal line is the crest
    where the posterior surface turns under to the nuchal plane.
    """
    inion = ext(V, INION_DIR, x=(-0.006, 0.006))
    return ext(V, INION_DIR, x=(0.021, 0.027), z=(inion.z - 0.012, inion.z + 0.012))


def mandible_angle(V, lo, hi):
    """Gonion: the vertex furthest posteroinferiorly on the left half, then
    the lateral-most vertex within 5 mm of it, so the point is on the outer
    surface of the angle rather than its inner face."""
    g = ext(V, unit(0, 1, -1), x=(0.03, None))
    return ext(V, X, y=(g.y - 0.005, g.y + 0.005), z=(g.z - 0.005, g.z + 0.005))


def bicipital_groove(V, lo, hi):
    """The anterior surface midway between the two tubercles.

    At 4,280 triangles the humerus does not resolve the groove as a channel:
    in a transverse slab 30-40 mm below the top of the bone the anterior
    profile has one prominence, the lesser tubercle, and recedes steadily
    lateral of it into the greater tubercle. So the groove is placed where it
    lies between them - on the anterior surface at the X midway between the
    lesser tubercle's anterior-most vertex and the greater tubercle's
    lateral-most vertex, which puts it about 10 mm lateral of the lesser
    tubercle, 8-10 mm posterior of its tip.
    """
    slab = sel(V, z=(hi.z - 0.040, hi.z - 0.030))
    lesser = ext(slab, ANT)
    greater = ext(slab, X)
    xg = (lesser.x + greater.x) / 2.0
    return ext(slab, ANT, x=(xg - 0.002, xg + 0.002))


def costal_margin(V, lo, hi):
    """The inferior edge of the seventh rib at its anterior (costochondral) end."""
    tip = ext(V, ANT)
    return ext(V, DOWN, x=(tip.x - 0.012, tip.x + 0.012), y=(None, tip.y + 0.012))


def pisiform_surface(V, lo, hi):
    """The palmar surface directly under the centroid.

    The brief says centroid; the surface criterion in the same brief forbids a
    point inside the bone, and the pisiform is felt on its palmar face. So: the
    centroid's X and Z, on the anterior surface.
    """
    c = centroid(V)
    return ext(V, ANT, x=(c.x - 0.003, c.x + 0.003), z=(c.z - 0.003, c.z + 0.003))


def pubic_tubercle(V, lo, hi):
    """The anterosuperior lip of the pubic body, 20-30 mm from the symphysis.

    The tubercle is at the lateral end of the pubic crest. Among vertices in
    that X band and below the acetabulum, take the one furthest anterosuperiorly.
    """
    return ext(V, unit(0, -1, 0.6), x=(0.020, 0.032), z=(None, lo.z + 0.075))


def jugular_notch(V, lo, hi):
    """The anterior lip of the manubrium's superior border at the midline.

    The floor of the notch is the top of the manubrium; the point a finger
    rests on is its anterior edge, so: the most anterior vertex in the top
    3 mm of the midline.
    """
    midline = sel(V, x=(-0.003, 0.003))
    top = max(v.z for v in midline)
    return ext(midline, ANT, z=(top - 0.003, None))


def sacral_base(V, lo, hi):
    """The centre of the S1 superior endplate at the midline.

    The superior articular processes stand 18 mm above the endplate, so the
    top of the sacrum's box is not the base. The endplate is the top 6 mm of
    the midline itself (|X| < 3 mm); the point is the vertex there whose Y is
    nearest the endplate's mid-depth.
    """
    midline = sel(V, x=(-0.003, 0.003))
    top = max(v.z for v in midline)
    plate = sel(midline, z=(top - 0.006, None))
    ym = mid(plate, "y")
    return min(plate, key=lambda v: abs(v.y - ym))


def adductor_tubercle(V, lo, hi):
    """The top of the medial epicondylar prominence.

    Read as a medial profile, the distal femur is most medial over a 3 cm
    band (the epicondyle, X within 5 mm of the bone's medial extreme) and
    then the shaft recedes 1 cm laterally within a single 2.5 mm step. The
    adductor tubercle is where the medial supracondylar line ends on that
    prominence: its most proximal vertex. The medial-most vertex of the band
    is the epicondyle itself, which the brief's first pass landed on.
    """
    xmin = min(v.x for v in V)
    return ext(V, UP, x=(None, xmin + 0.005), z=(None, lo.z + 0.08))


def gerdys_tubercle(V, lo, hi):
    """Anterolateral proximal tibia, at and just above the tuberosity's height."""
    tub = ext(V, ANT, z=(hi.z - 0.07, hi.z - 0.02))
    return ext(V, unit(1, -1, 0), z=(tub.z, tub.z + 0.02))


def knee_joint_line(V, lo, hi):
    """The anteromedial rim of the tibial plateau.

    The brief's first pass put this at the centre of the plateau top, which is
    the intercondylar eminence: inside the joint under the femur, not a thing a
    hand reaches. The joint line is palpated at the plateau rim beside the
    patellar tendon; this is the anteromedial corner of the medial condyle,
    the vertex of the top 12 mm furthest anteromedially.
    """
    rim = sel(V, z=(hi.z - 0.012, None))
    return ext(rim, unit(-1, -1, 0))


# ------------------------------------------------------------------- spec

# object may be a .l object (the right is the .r twin) or an unsided midline
# object (the right is the same object, and the point mirrors across it).
#
# region  one of the app's groupings, for the report
# limb    True for the landmarks the 20 mm depth limit applies to: the elbow,
#         wrist, hand, knee, ankle and foot groups and the greater trochanter.
#         The two humeral shoulder landmarks are measured against the same
#         upper-limb hull but reported rather than asserted - see hull below
# hull    which limb cross-section the hull depth is measured in, if any
# paired  False for the six midline landmarks, which carry one resolved point
# rule    (direction, bounds) for a plain extreme, or a function (V, lo, hi)
# push    direction to step PUSH metres outward along; must have a positive
#         component along the rule's own direction (see module docstring)

PUSH = 0.002

L = []


def lm(id, name, obj, target, rule, push, region, limb=False, paired=True,
       first_pass=None, first_pass_offset=(0, 0, 0), hull=None):
    if hull is None and limb:
        hull = "upper" if region in ("shoulder", "elbow", "wrist") else "lower"
    L.append(dict(id=id, name=name, object=obj, target=target, rule=rule,
                  push=Vector(push).normalized(), region=region, limb=limb,
                  hull=hull, paired=paired, first_pass=first_pass,
                  first_pass_offset=first_pass_offset))


# ----- head and neck

lm("lm-mastoid-process", "Mastoid process", "Temporal bone.l",
   "The bony bump behind the earlobe - the inferolateral surface of the mastoid process",
   (unit(1, 0, -1), dict(y=(0.012, None))), unit(1, 0, -1), "head-neck",
   first_pass=(0.55, 0.75, 0.15))

lm("lm-occipital-protuberance", "External occipital protuberance", "Occipital bone",
   "Midline bump on the outer occipital surface, where the nuchal plane meets the occipital plane",
   (INION_DIR, dict(x=(-0.006, 0.006))), POST, "head-neck", paired=False,
   first_pass=(0.50, 0.95, 0.55))

lm("lm-superior-nuchal-line", "Superior nuchal line", "Occipital bone",
   "On the ridge running laterally from the protuberance toward the mastoid - a third of the way along",
   nuchal_line, POST, "head-neck",
   first_pass=(0.68, 0.90, 0.48))

lm("lm-c1-transverse", "C1 transverse process", "Atlas (C1)",
   "The most lateral point of the atlas transverse process",
   (X, {}), X, "head-neck",
   first_pass=(0.95, 0.50, 0.50))

lm("lm-c2-spinous", "C2 spinous process", "Axis (C2)",
   "The most posterior point of the C2 spinous process",
   (POST, {}), POST, "head-neck", paired=False,
   first_pass=(0.50, 0.95, 0.40))

lm("lm-c7-spinous", "C7 spinous process", "Vertebra C7",
   "The most posterior point of the C7 spinous process",
   (POST, {}), POST, "head-neck", paired=False,
   first_pass=(0.50, 0.95, 0.45))

lm("lm-mandible-angle", "Angle of mandible", "Mandible",
   "The posteroinferior corner of the mandible where ramus meets body",
   mandible_angle, unit(0.5, 1, -1), "head-neck",
   first_pass=(0.85, 0.70, 0.10))

lm("lm-zygomatic-arch", "Zygomatic arch", "Zygomatic bone.l",
   "Mid-length of the arch, on its lateral surface",
   (X, dict(y=("max-0.010", None))), X, "head-neck",
   first_pass=(0.80, 0.55, 0.45))

# ----- shoulder and thorax

lm("lm-acromion", "Acromion", "Scapula.l",
   "The flat lateral shelf forming the point of the shoulder - most lateral and superior scapular point",
   (X, dict(z=("max-0.025", None))), unit(1, 0, 0.5), "shoulder",
   first_pass=(0.90, 0.25, 0.95))

lm("lm-coracoid", "Coracoid process", "Scapula.l",
   "The anterior finger-shaped projection, roughly 2 cm inferomedial to the acromion",
   (ANT, {}), ANT, "shoulder",
   first_pass=(0.70, 0.10, 0.80))

lm("lm-scapular-spine", "Spine of scapula", "Scapula.l",
   "Mid-length of the posterior ridge",
   (POST, dict(x=("mid-0.003", "mid+0.003"))), POST, "shoulder",
   first_pass=(0.50, 0.85, 0.80))

lm("lm-inferior-angle", "Inferior angle of scapula", "Scapula.l",
   "The most inferior point of the scapula",
   (DOWN, {}), unit(0, 0.5, -1), "shoulder",
   first_pass=(0.35, 0.80, 0.02))

lm("lm-scapular-medial-border", "Medial border of scapula", "Scapula.l",
   "Mid-length of the medial (vertebral) border",
   (MED, dict(z=("mid-0.004", "mid+0.004"))), unit(-1, 0.5, 0), "shoulder",
   first_pass=(0.05, 0.80, 0.45))

lm("lm-greater-tubercle", "Greater tubercle", "Humerus.l",
   "The lateral prominence on the proximal humerus, distal to the head",
   (X, dict(z=("max-0.04", None))), X, "shoulder", hull="upper")

lm("lm-bicipital-groove", "Bicipital groove", "Humerus.l",
   "The anterior vertical channel between greater and lesser tubercles",
   bicipital_groove, ANT, "shoulder", hull="upper")

lm("lm-jugular-notch", "Jugular notch", "Manubrium of sternum",
   "The midline hollow at the superior border",
   jugular_notch, unit(0, -0.5, 1), "thorax", paired=False,
   first_pass=(0.50, 0.10, 0.95))

lm("lm-sternal-angle", "Sternal angle", "Manubrium of sternum",
   "The inferior border of the manubrium, where it meets the sternal body",
   (ANT, dict(x=(-0.003, 0.003), z=(None, "min+0.006"))), ANT, "thorax", paired=False,
   first_pass=(0.50, 0.10, 0.05))

lm("lm-costal-margin", "Costal margin", "Seventh rib.l",
   "The anterior inferior end of the seventh rib, on the costal arch",
   costal_margin, unit(0, -0.5, -1), "thorax",
   first_pass=(0.20, 0.10, 0.10))

# ----- elbow, wrist and hand

lm("lm-medial-epicondyle", "Medial epicondyle", "Humerus.l",
   "The medial bony bump at the distal humerus. Ulnar nerve groove sits immediately posterior",
   (MED, dict(z=(None, "min+0.04"))), MED, "elbow", limb=True)

lm("lm-lateral-epicondyle", "Lateral epicondyle", "Humerus.l",
   "The lateral bony bump at the distal humerus",
   (X, dict(z=(None, "min+0.04"))), X, "elbow", limb=True)

lm("lm-olecranon", "Olecranon", "Ulna.l",
   "The most proximal and posterior point of the ulna - the point of the elbow",
   (POST, dict(z=("max-0.015", None))), unit(0, 1, 0.5), "elbow", limb=True)

lm("lm-radial-styloid", "Radial styloid", "Radius.l",
   "The distal lateral projection of the radius, ~1 cm distal to the ulnar styloid",
   (DOWN, {}), unit(1, 0, -1), "wrist", limb=True)

lm("lm-ulnar-styloid", "Ulnar styloid", "Ulna.l",
   "The distal medial projection of the ulna",
   (DOWN, {}), unit(-1, 0.3, -1), "wrist", limb=True)

lm("lm-anatomical-snuffbox", "Anatomical snuffbox", "Scaphoid bone.l",
   "Dorsal-lateral surface of the scaphoid - the floor of the hollow",
   (unit(1, 1, 0), {}), unit(1, 1, 0), "wrist", limb=True)

lm("lm-pisiform", "Pisiform", "Pisiform bone.l",
   "The pisiform itself, on its palmar surface",
   pisiform_surface, ANT, "wrist", limb=True)

# ----- pelvis and hip

lm("lm-iliac-crest", "Iliac crest", "Hip bone.l",
   "The highest point of the iliac crest",
   (UP, {}), unit(0.3, 0, 1), "pelvis",
   first_pass=(0.45, 0.50, 1.00))

lm("lm-asis", "ASIS", "Hip bone.l",
   "The anterior-most superior projection of the ilium",
   (ANT, dict(z=("max-0.09", None))), ANT, "pelvis",
   first_pass=(0.35, 0.05, 0.85))

lm("lm-psis", "PSIS", "Hip bone.l",
   "The posterior-most superior projection of the ilium",
   (POST, dict(z=("max-0.09", None))), POST, "pelvis",
   first_pass=(0.15, 0.95, 0.80))

lm("lm-ischial-tuberosity", "Ischial tuberosity", "Hip bone.l",
   "The most inferior posterior prominence - the sitting bone",
   (DOWN, dict(y=(0.02, None))), unit(0, 0.5, -1), "pelvis",
   first_pass=(0.35, 0.75, 0.02))

lm("lm-pubic-tubercle", "Pubic tubercle", "Hip bone.l",
   "Small anterior projection near the midline at the pubis",
   pubic_tubercle, unit(0, -1, 0.6), "pelvis",
   first_pass=(0.15, 0.05, 0.20))

lm("lm-greater-trochanter", "Greater trochanter", "Femur.l",
   "The most lateral prominence at the proximal femur",
   (X, {}), X, "hip", limb=True,
   first_pass=(0.95, 0.50, 0.97))

lm("lm-sacral-base", "Sacral base", "Sacrum",
   "Midline, superior surface of S1",
   sacral_base, UP, "pelvis", paired=False,
   first_pass=(0.50, 0.30, 0.98))

# ----- knee, ankle and foot

lm("lm-tibial-tuberosity", "Tibial tuberosity", "Tibia.l",
   "The anterior bump on the proximal tibia",
   (ANT, dict(z=("max-0.07", "max-0.02"))), ANT, "knee", limb=True,
   first_pass=(0.50, 0.05, 0.95))

lm("lm-gerdys-tubercle", "Gerdy's tubercle", "Tibia.l",
   "Anterolateral proximal tibia, level with and lateral to the tuberosity",
   gerdys_tubercle, unit(1, -1, 0), "knee", limb=True,
   first_pass=(0.90, 0.20, 0.93))

lm("lm-knee-joint-line", "Knee joint line", "Tibia.l",
   "The tibial plateau rim - the joint line itself, anteromedially",
   knee_joint_line, unit(-1, -1, 0), "knee", limb=True,
   first_pass=(0.50, 0.50, 1.00))

lm("lm-fibular-head", "Fibular head", "Fibula.l",
   "The proximal knob of the fibula",
   (X, dict(z=("max-0.025", None))), X, "knee", limb=True,
   first_pass=(0.50, 0.50, 0.98))

lm("lm-adductor-tubercle", "Adductor tubercle", "Femur.l",
   "Small medial projection just proximal to the medial femoral condyle",
   adductor_tubercle, unit(-1, 0, 0.3), "knee", limb=True,
   first_pass=(0.10, 0.60, 0.06))

lm("lm-medial-malleolus", "Medial malleolus", "Tibia.l",
   "The medial distal projection of the tibia - higher and more anterior than the lateral malleolus",
   (DOWN, {}), unit(-1, 0, -1), "ankle", limb=True)

lm("lm-lateral-malleolus", "Lateral malleolus", "Fibula.l",
   "The distal end of the fibula - lower and more posterior than the medial malleolus",
   (DOWN, {}), unit(1, 0, -1), "ankle", limb=True)

lm("lm-navicular-tuberosity", "Navicular tuberosity", "Navicular bone.l",
   "The medial prominence of the navicular",
   (MED, {}), MED, "foot", limb=True,
   first_pass=(0.20, 0.55, 0.40))

lm("lm-fifth-metatarsal-base", "Fifth metatarsal base", "Fifth metatarsal bone.l",
   "The proximal lateral tuberosity",
   (X, dict(y=("max-0.015", None))), X, "foot", limb=True,
   first_pass=(0.85, 0.60, 0.55))

lm("lm-sustentaculum-tali", "Sustentaculum tali", "Calcaneus.l",
   "The medial shelf, roughly a thumb's width below the medial malleolus",
   (MED, dict(z=("mid", None))), MED, "foot", limb=True,
   first_pass=(0.10, 0.35, 0.75))

LANDMARKS = L
assert len(LANDMARKS) == 42, len(LANDMARKS)
assert len({l["id"] for l in LANDMARKS}) == 42
