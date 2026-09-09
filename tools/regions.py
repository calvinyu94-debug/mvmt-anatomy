"""Region assignment for the musculoskeletal export.

Pure Python, no bpy. Run directly against inventory.csv to review the result
without Blender:

    python tools/regions.py            # prints the review tables
    python tools/regions.py --csv region-assignment.csv

The same `assign()` is what tools/export_regions.py calls inside Blender, fed
from the live model, so the committed CSV and the exported extras cannot
disagree.

Nine regions, matching the app. Every kept mesh goes to exactly one. Each
assignment records which signal decided it, in this order of precedence:

  override   A short clinical table, below. The atlas files muscles by
             compartment and by "Trunk", which is not how a shoulder or a knee
             is thought about: latissimus dorsi is a back muscle to the atlas
             and a shoulder muscle to a clinician. Everything in the table is
             there because the hierarchy would have put it somewhere a user of
             the app would not look for it. Review this table first.
  hierarchy  The Bonus collection hierarchy - the anatomical one (compartments,
             joints, vertebral levels) and the Regions of human body / Main
             divisions one. Side words are stripped from the division tags
             before use, because the divisions are not left-right symmetric
             upstream (see inventory-summary.md); the side comes from the name
             suffix instead. A division tag only decides when it maps to a
             single region: a ligament tagged Neck, Thorax and Abdomen at once
             falls through.
  parent     Muscular insertions (.ol/.or/.el/.er) follow the muscle they
             belong to, looked up by name, so a region's insertion layer shows
             its own muscles' attachments wherever they land on bone.
  pairing    A sided object with no decision inherits its contralateral twin's.
             This is what repairs the asymmetric upstream tagging directly.
  centroid   Height bands and a lateral test for the limbs, on the world-space
             bounding-box centroid. Fallback and tie-breaker only. Anything
             decided this way is listed separately in the summary for review.

Per CLAUDE.md, a centroid is a coarse signal and is used only as a last resort
here - never to place anything against another structure.
"""

import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import scope  # noqa: E402

REGIONS = ("head-jaw", "cervical", "shoulder", "thoracic", "lumbar",
           "hip", "knee", "elbow-wrist", "ankle-foot")

# Neighbour map from the brief. Each region exports its neighbours as context.
NEIGHBOURS = {
    "cervical": ["head-jaw", "shoulder", "thoracic"],
    "shoulder": ["cervical", "thoracic", "elbow-wrist"],
    "thoracic": ["cervical", "shoulder", "lumbar"],
    "lumbar": ["thoracic", "hip"],
    "hip": ["lumbar", "knee"],
    "knee": ["hip", "ankle-foot"],
    "ankle-foot": ["knee"],
    "elbow-wrist": ["shoulder"],
    "head-jaw": ["cervical"],
}

# --------------------------------------------------------------- overrides
#
# (regex on the object name, case-insensitive; region; why)
# First match wins. Keep each entry to one clinical reason.
OVERRIDES = [
    # Two-joint and girdle muscles the atlas files under Trunk or Back.
    (r"trapezius|rhomboid|latissimus dorsi|serratus anterior|pectoralis (major|minor)"
     r"|subclavius|teres major|coracobrachialis|clavipectoral fascia|pectoral fascia"
     r"|^humerus\b",
     "shoulder", "scapular / glenohumeral muscles and the humerus: the shoulder to a clinician"),
    # Respiratory muscles of the back and the diaphragm, filed under Back / Abdomen.
    (r"serratus posterior|levatores .*costarum|^diaphragm|interspinales thoracis|intercostal",
     "thoracic", "act on the ribs"),
    # The lumbar spine and pelvis: the Lumbar/pelvis band of the brief.
    (r"psoas (major|minor)|iliopsoas fascia|iliopectineal arch|quadratus lumborum"
     r"|thoracolumbar fascia|levator ani|coccygeus|pubococcygeus|iliococcygeus|pubo-analis"
     r"|puborectalis|anal sphincter|inguinal ligament|interspinales lumborum"
     r"|intertransversarii lumborum|^linea alba|pyramidalis|transversalis fascia"
     r"|^sacrum\b|^coccyx\b|^hip bone\b|sacrococcygeal|intercornual",
     "lumbar", "lumbar spine, pelvis and pelvic floor"),
    # Erector spinae and transversospinal parts are named by level.
    (r"lumborum", "lumbar", "named lumbar part of a long back muscle"),
    (r"thoracis", "thoracic", "named thoracic part of a long back muscle"),
    (r"\b(colli|cervicis|capitis)\b|^hyoid bone|nuchal ligament",
     "cervical", "named cervical / capital part; hyoid and nuchal ligament"),
    # Whole-column ligaments are single objects spanning C2 to the sacrum; the
    # thoracic export is the one that shows most of them.
    (r"ligamenta flava|interspinous ligaments|longitudinal ligament|supraspinous ligament",
     "thoracic", "single objects spanning the whole column; placed at their middle"),
    # Vertebral discs by level.
    (r"(intervertebral disc|nucleus pulposus) C", "cervical", "cervical level"),
    (r"(intervertebral disc|nucleus pulposus) T", "thoracic", "thoracic level"),
    (r"(intervertebral disc|nucleus pulposus) L", "lumbar", "lumbar level"),
    # Knee: the atlas has no knee compartment, so the leg's proximal muscles
    # and the leg bones are named here.
    (r"gastrocnemius|popliteus|popliteal|^patella\b|^tibia\b|^fibula\b"
     r"|interosseous membrane of leg|patellar|anserine|tuberosity of tibia|semimembranosus bursa"
     r"|inferior subtendinous bursa of biceps femoris|bursa of sartorius",
     "knee", "structures at the knee the hierarchy files under leg / thigh / lower limb"),
    # Hip / thigh: the Hip/thigh band of the brief.
    (r"^femur\b|iliotibial tract|fascia lata|^iliacus|femoral intermuscular septum"
     r"|trochanteric|gluteal|bursa of piriformis|obturator internus|iliopectineal bursa"
     r"|bursa of iliacus|superior bursa of biceps femoris",
     "hip", "thigh and gluteal region"),
    # Forearm bones and arm fascia: "Bones of upper limb" is not split by segment.
    (r"^radius\b|^ulna\b|brachial fascia|antebrachial|intermuscular septum of arm"
     r"|bicipitoradial|bursa of triceps",
     "elbow-wrist", "arm distal to the shoulder"),
    (r"ethmoid|masseter|temporalis|pterygoid", "head-jaw",
     "ethmoid air cells carry no collection tags; the masticator insertions are named as a group"),
]
_OVERRIDES = [(re.compile(rx, re.IGNORECASE), region, why) for rx, region, why in OVERRIDES]

# --------------------------------------------------------------- hierarchy
#
# Anatomical-hierarchy tags, in priority order. A tag is any single segment of
# a Bonus collection path. First matching tag decides.
HIERARCHY_TAGS = [
    # thoracic before shoulder: the manubrium is filed under "Bones of pectoral girdle"
    ("Sternum", "thoracic"), ("Ribs", "thoracic"), ("Costal cartilages", "thoracic"),
    ("Thoracic vertebrae", "thoracic"), ("Thoracic joints", "thoracic"),
    ("Thoracic skeleton", "thoracic"),
    ("Cervical vertebrae", "cervical"), ("Lumbar vertebrae", "lumbar"),
    ("Bony pelvis", "lumbar"), ("Joints of pelvic girdle", "lumbar"),
    ("Muscles of abdomen", "lumbar"), ("Abdominal part of muscular system", "lumbar"),
    ("Joints of skull", "head-jaw"), ("Cranium", "head-jaw"), ("Teeth", "head-jaw"),
    ("Mandible", "head-jaw"), ("Extracranial bones of head", "head-jaw"),
    ("Muscles of head", "head-jaw"), ("Cranial part of muscular system", "head-jaw"),
    ("Muscles of neck", "cervical"), ("Cervical part of muscular system", "cervical"),
    ("Suboccipital muscles", "cervical"), ("Laryngeal joints", "cervical"),
    ("Joints of pectoral girdle", "shoulder"), ("Glenohumeral joint", "shoulder"),
    ("Bones of pectoral girdle", "shoulder"), ("Scapulohumeral muscles", "shoulder"),
    ("Thoracic part of muscular system", "shoulder"),   # pectoralis major only
    ("Elbow joint", "elbow-wrist"), ("Radio-ulnar syndesmoses", "elbow-wrist"),
    ("Distal radio-ulnar joint", "elbow-wrist"), ("Radiocarpal joint", "elbow-wrist"),
    ("Joints of hand", "elbow-wrist"), ("Muscles of hand", "elbow-wrist"),
    ("Anterior compartment of arm", "elbow-wrist"), ("Posterior compartment of arm", "elbow-wrist"),
    ("Anterior compartment of forearm", "elbow-wrist"),
    ("Posterior compartment of forearm", "elbow-wrist"), ("Fascia of upper limb", "elbow-wrist"),
    ("Hip joint", "hip"), ("Superficial gluteal muscles", "hip"), ("Deep gluteal muscles", "hip"),
    ("Anterior compartment of thigh", "hip"), ("Medial compartment of thigh", "hip"),
    ("Posterior compartment of thigh", "hip"),
    ("Knee joint", "knee"), ("Superior tibiofibular joint", "knee"),
    ("Ankle joint", "ankle-foot"), ("Joints of foot", "ankle-foot"),
    ("Tibiofibular syndesmosis", "ankle-foot"), ("Muscles of foot", "ankle-foot"),
    ("Anterior compartment of leg", "ankle-foot"), ("Lateral compartment of leg", "ankle-foot"),
    ("Posterior compartment of leg", "ankle-foot"),
]

# Regions of human body / Main divisions, after the side word is stripped.
# Only decides when the object's division tags map to a single region.
DIVISION_REGION = {
    "Head": "head-jaw", "Neck": "cervical", "Thorax": "thoracic", "Abdomen": "lumbar",
    "Pelvis": "lumbar", "Hand": "elbow-wrist", "Foot": "ankle-foot",
    # "Upper limb", "Lower limb", "Trunk", "Back" span several regions and are
    # deliberately absent: they fall through to pairing and centroid.
}

_SIDE_WORD = re.compile(r"^(Left|Right) ")


def tags_of(all_collections):
    """Every path segment under Bonus collection, side words stripped."""
    tags = set()
    for c in all_collections:
        if "Bonus collection/" not in c:
            continue
        for seg in c.split("Bonus collection/", 1)[1].split("/"):
            seg = _SIDE_WORD.sub("", seg)
            tags.add(seg[:1].upper() + seg[1:])      # "Right hand" -> "Hand"
    return tags


# --------------------------------------------------------------- centroid
#
# Heights are landmark-derived from inventory.csv (metres, Z up):
#   occipital condyles ~1.55, C7/T1 boundary ~1.445, T12/L1 ~1.12,
#   sacral promontory ~0.98, femoral head ~0.87, knee joint line ~0.43,
#   ankle joint ~0.07. The upper limb hangs beside the trunk from z 1.45 down
#   to the fingertips at z 0.70; nothing of the trunk is lateral of |x| 0.14
#   above the pelvis, and nothing of the leg is lateral of |x| 0.20.
def centroid_region(x, y, z):
    ax = abs(x)
    if (ax > 0.14 and z > 0.86) or (ax > 0.20 and z > 0.65):
        return "shoulder" if z >= 1.19 else "elbow-wrist"
    if z >= 1.565:
        return "head-jaw"
    if z >= 1.445:
        # the face and jaw sit anterior to the cervical column at these heights
        return "head-jaw" if (z > 1.50 and y < -0.03) else "cervical"
    if z >= 1.12:
        return "thoracic"
    if z >= 0.96 or (z >= 0.86 and ax < 0.095):
        return "lumbar"
    if z >= 0.55:
        return "hip"
    if z >= 0.34:
        return "knee"
    return "ankle-foot"


# --------------------------------------------------------------- assignment


def _muscle_of_insertion(name):
    """'(Abdominal part of pectoralis major muscle).o1l' -> the muscle base name."""
    return scope.base_name(name).strip("()")


def _base(name):
    return scope.base_name(name)


def assign(rows):
    """rows: dicts with object_name, system, all_collections (list), triangles,
    centroid_x/y/z. Returns {object_name: {"region", "signal", "detail"}}."""
    by_name = {r["object_name"]: r for r in rows}
    result = {}

    def decide_by_rules(r):
        name = r["object_name"]
        for rx, region, why in _OVERRIDES:
            if rx.search(name):
                return region, "override", why
        tags = tags_of(r["all_collections"])
        for tag, region in HIERARCHY_TAGS:
            if tag in tags:
                return region, "hierarchy", tag
        divs = sorted({DIVISION_REGION[t] for t in tags if t in DIVISION_REGION})
        if len(divs) == 1:
            return divs[0], "hierarchy", "division:" + "/".join(
                sorted(t for t in tags if t in DIVISION_REGION))
        return None, None, ("ambiguous divisions " + "/".join(divs)) if divs else "no usable tag"

    # Pass 1: overrides and hierarchy, muscles/bones/joints first so that
    # insertions can follow their muscle in pass 2.
    for r in rows:
        if r["system"] == "insertion":
            continue
        region, signal, detail = decide_by_rules(r)
        if region:
            result[r["object_name"]] = {"region": region, "signal": signal, "detail": detail}

    # Pass 2: insertions follow their muscle.
    for r in rows:
        if r["system"] != "insertion":
            continue
        name = r["object_name"]
        muscle = _muscle_of_insertion(name)
        side = scope.side_of(name)
        for cand in (muscle + "." + side, muscle + "." + ("r" if side == "l" else "l"), muscle):
            if cand in result:
                result[name] = {"region": result[cand]["region"], "signal": "parent",
                                "detail": cand}
                break
        else:
            region, signal, detail = decide_by_rules(r)
            if region:
                result[name] = {"region": region, "signal": signal, "detail": detail}

    # Pass 3: side pairing. Also checks that decided twins agree.
    conflicts = []
    for r in rows:
        name = r["object_name"]
        twin = scope.twin_of(name)
        if twin is None or twin not in by_name:
            continue
        if name in result and twin in result:
            if result[name]["region"] != result[twin]["region"]:
                conflicts.append((name, twin))
        elif name not in result and twin in result:
            result[name] = {"region": result[twin]["region"], "signal": "pairing",
                            "detail": twin}

    # Twins that disagree: resolve to the one decided by the stronger signal,
    # then by centroid of the pair. Recorded so it is visible in the CSV.
    rank = {"override": 0, "hierarchy": 1, "parent": 2, "pairing": 3}
    for a, b in conflicts:
        ra, rb = result[a], result[b]
        if rank[ra["signal"]] < rank[rb["signal"]]:
            win = ra
        elif rank[rb["signal"]] < rank[ra["signal"]]:
            win = rb
        else:
            ca = by_name[a]
            win = {"region": centroid_region(float(ca["centroid_x"]), float(ca["centroid_y"]),
                                             float(ca["centroid_z"])),
                   "signal": "centroid", "detail": "twin conflict"}
        for n, other in ((a, b), (b, a)):
            result[n] = {"region": win["region"], "signal": "pairing-conflict",
                         "detail": "%s vs %s -> %s" % (ra["region"], rb["region"], win["signal"])}

    # Pass 4: centroid fallback, symmetric by construction (|x|), so twins agree.
    for r in rows:
        name = r["object_name"]
        if name in result:
            continue
        region = centroid_region(float(r["centroid_x"]), float(r["centroid_y"]),
                                 float(r["centroid_z"]))
        result[name] = {"region": region, "signal": "centroid",
                        "detail": "z=%.3f |x|=%.3f y=%+.3f" % (
                            float(r["centroid_z"]), abs(float(r["centroid_x"])),
                            float(r["centroid_y"]))}

    verify(rows, result)
    return result


def verify(rows, result):
    """Every kept mesh in exactly one region; every region populated; twins agree."""
    names = [r["object_name"] for r in rows]
    missing = [n for n in names if n not in result]
    extra = [n for n in result if n not in set(names)]
    if missing or extra:
        raise AssertionError("assignment incomplete: %d unassigned, %d extra" % (len(missing), len(extra)))
    bad = [n for n in names if result[n]["region"] not in REGIONS]
    if bad:
        raise AssertionError("unknown region on %r" % bad[:5])
    per = Counter(result[n]["region"] for n in names)
    empty = [rg for rg in REGIONS if per[rg] == 0]
    if empty:
        raise AssertionError("regions with no mesh: %r" % empty)
    by = set(names)
    for n in names:
        t = scope.twin_of(n)
        if t and t in by and result[t]["region"] != result[n]["region"]:
            raise AssertionError("twins disagree: %s / %s" % (n, t))


# --------------------------------------------------------------- reporting


def csv_rows(rows, result):
    out = []
    for r in rows:
        a = result[r["object_name"]]
        out.append({
            "sourceName": r["object_name"],
            "region": a["region"],
            "system": r["system"],
            "side": scope.side_of_object(r["object_name"], float(r["centroid_x"])),
            "signal": a["signal"],
            "detail": a["detail"],
            "triangles": int(r["triangles"]),
        })
    out.sort(key=lambda x: (REGIONS.index(x["region"]), x["system"], x["sourceName"]))
    return out


CSV_FIELDS = ["sourceName", "region", "system", "side", "signal", "detail", "triangles"]


def write_csv(path, rows, result):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(csv_rows(rows, result))


def summary(rows, result):
    lines = []
    per = defaultdict(lambda: {"meshes": 0, "triangles": 0, "l": 0, "r": 0, "": 0,
                               "signals": Counter()})
    for r in rows:
        a = result[r["object_name"]]
        p = per[a["region"]]
        p["meshes"] += 1
        p["triangles"] += int(r["triangles"])
        p[scope.side_of(r["object_name"])] += 1
        p["signals"][a["signal"]] += 1
    lines.append("%-12s %6s %9s %5s %5s %5s  signals" % ("region", "meshes", "tris", "l", "r", "mid"))
    for rg in REGIONS:
        p = per[rg]
        lines.append("%-12s %6d %9d %5d %5d %5d  %s" % (
            rg, p["meshes"], p["triangles"], p["l"], p["r"], p[""],
            " ".join("%s=%d" % kv for kv in sorted(p["signals"].items()))))
    tot = Counter(result[r["object_name"]]["signal"] for r in rows)
    lines.append("signals overall: " + " ".join("%s=%d" % kv for kv in sorted(tot.items())))
    cent = [r for r in rows if result[r["object_name"]]["signal"] == "centroid"]
    lines.append("centroid-only: %d meshes / %d triangles" % (
        len(cent), sum(int(r["triangles"]) for r in cent)))
    return "\n".join(lines)


def centroid_only_table(rows, result):
    """The set to eyeball: one line per base name, both sides folded."""
    seen = {}
    for r in rows:
        a = result[r["object_name"]]
        if a["signal"] != "centroid":
            continue
        b = _base(r["object_name"])
        if b not in seen:
            seen[b] = (a["region"], r["system"], int(r["triangles"]), a["detail"])
    lines = ["%-12s %-9s %6s  %-58s %s" % ("region", "system", "tris", "object (both sides)", "centroid")]
    for b, (rg, sy, t, d) in sorted(seen.items(), key=lambda kv: (REGIONS.index(kv[1][0]), kv[0])):
        lines.append("%-12s %-9s %6d  %-58s %s" % (rg, sy, t, b[:58], d))
    return "\n".join(lines)


def load_inventory(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    for r in rows:
        r["all_collections"] = r["all_collections"].split(" | ") if r["all_collections"] else []
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", default=os.path.join(os.path.dirname(__file__), "..", "inventory.csv"))
    ap.add_argument("--csv", help="write region-assignment.csv here")
    ap.add_argument("--full", action="store_true", help="print every assignment")
    args = ap.parse_args()

    rows = load_inventory(args.inventory)
    kept, excluded, report = scope.partition(rows)
    print(scope.format_report(report))
    result = assign(kept)
    print()
    print(summary(kept, result))
    print()
    print(centroid_only_table(kept, result))
    if args.full:
        for x in csv_rows(kept, result):
            print("%-12s %-9s %-16s %7d  %s  [%s]" % (
                x["region"], x["system"], x["signal"], x["triangles"], x["sourceName"], x["detail"]))
    if args.csv:
        write_csv(args.csv, kept, result)
        print("wrote", args.csv)
    print("REGIONS_OK meshes=%d" % len(kept))


if __name__ == "__main__":
    main()
