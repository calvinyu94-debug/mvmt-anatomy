"""Scope and licence filters for the musculoskeletal export.

Pure Python, no bpy: the same code runs against inventory.csv for review and
against the live model inside Blender for the export, so the two can never
disagree about what is in scope.

Two filters, applied in this order:

  1. Scope. Keep real meshes filed under the four musculoskeletal top-level
     collections. Everything else - nervous system, viscera, vessels, lymphoid,
     regions, reference planes, label infrastructure - is payload the viewer
     does not want.

  2. Licence. EXCLUSIONS.md, applied to whatever survived scope. Most of it
     falls inside the collections scope already dropped, but this filter is the
     licence control and runs regardless. Its counts are asserted against the
     EXPECTED dict from EXCLUSIONS.md on the full inventory, so a drifted
     pattern or a changed upstream model stops the build.
"""

import re

# Top-level collections that make up the musculoskeletal scope.
KEEP_COLLECTIONS = (
    "1: Skeletal system",
    "2: Muscular insertions",
    "3: Joints",
    "4: Muscular system",
)

# Which `system` an object is exported under, keyed by the collection it is
# filed in. An object filed in more than one of these (there are none today,
# asserted at run time) would be a hard error.
SYSTEM_OF_COLLECTION = {
    "1: Skeletal system": "skeletal",
    "2: Muscular insertions": "insertion",
    "3: Joints": "articular",
    "4: Muscular system": "muscular",
}

# Copied verbatim from EXCLUSIONS.md. If these move, EXCLUSIONS.md moved.
EXCLUSION_PATTERNS = {
    "brain_cns": (
        r"telencephalon|diencephalon|mesencephalon|metencephalon|myelencephalon|"
        r"cerebrum|cerebral|cerebell|\bpons\b|medulla oblongata|brainstem|brain stem|"
        r"thalam|hypothalam|epithalam|subthalam|hippocamp|amygdal|corpus callosum|"
        r"basal (nuclei|ganglia)|caudate|putamen|globus pallidus|claustrum|"
        r"internal capsule|corona radiata|fornix of brain|septum pellucidum|"
        r"commissural fibres|projection fibres|association fibres|arcuate fasciculus|"
        r"olfactory (bulb|tract)|optic (chiasm|radiation)|pituitary|hypophysis|pineal|"
        r"choroid plexus|ventricle of brain|lateral ventricle|third ventricle|"
        r"fourth ventricle|cerebrospinal|arachnoid|pia mater of brain|dura mater of brain|"
        r"cranial dura|falx|tentorium|red nucleus|substantia nigra|"
        r"locus (coeruleus|ceruleus)|superior colliculus|inferior colliculus|"
        r"corpus striatum|insula\b|white matter of telencephalon|grey matter of telencephalon"
    ),
    "inner_middle_ear": (
        r"cochlea|cochlear (duct|nerve|canal)|semicircular|bony labyrinth|"
        r"membranous labyrinth|\bincus\b|\bmalleus\b|\bstapes\b|tympanic (membrane|cavity)|"
        r"auditory ossicle|utricle|saccule|spiral organ|organ of corti|endolymph|perilymph|"
        r"oval window|round window|vestibular (aqueduct|duct|nerve|ganglion)|"
        r"internal acoustic|auditory tube|middle ear|inner ear|internal ear"
    ),
    "kidney_renal": (
        r"\bkidney|\brenal\b|nephron|\bureter|renal (pelvis|calix|calyx)|"
        r"minor calix|major calix"
    ),
}
_EXCLUSION_RX = {k: re.compile(v, re.IGNORECASE) for k, v in EXCLUSION_PATTERNS.items()}

# From EXCLUSIONS.md "Verification". Counted over MESH objects only, which is
# how the document's tables were produced (FONT and CURVE label objects that
# match the same patterns are payload, not licence, and are dropped anyway).
EXPECTED = {
    "brain_cns": {"objects": 96, "with_geometry": 61, "triangles": 413041},
    "inner_middle_ear": {"objects": 61, "with_geometry": 17, "triangles": 30574},
    "kidney_renal": {"objects": 15, "with_geometry": 4, "triangles": 8016},
}

# The figures in the job brief for the musculoskeletal scope before the
# licence filter. Asserted so a drifted filter cannot pass silently.
EXPECTED_SCOPE = {"meshes": 2060, "triangles": 2959783}


def is_label(name):
    """Atlas label infrastructure, per EXCLUSIONS.md."""
    return name.endswith((".j", ".t", ".g")) or "-txt" in name


def in_scope_collections(all_collections):
    """The KEEP_COLLECTIONS an object is filed under, from its full collection
    paths (e.g. 'Scene Collection/4: Muscular system')."""
    hits = []
    for k in KEEP_COLLECTIONS:
        if any(c == k or c.endswith("/" + k) or ("/" + k + "/") in c or c.startswith(k + "/")
               for c in all_collections):
            hits.append(k)
    return hits


def exclusion_set(name):
    """Which licence set a name matches, or None."""
    for k, rx in _EXCLUSION_RX.items():
        if rx.search(name):
            return k
    return None


# Side suffixes. Muscles, bones and joints use .l/.r. Insertions use .ol/.or
# (origin) and .el/.er (insertion), numbered when a muscle has several
# footprints: .o1l, .e2r, .e10l. The side is always the final letter.
SIDE_SUFFIX = re.compile(r"^(.*\.[oe]?\d*)([lr])$")


def side_of(name):
    """'l', 'r' or '' from the atlas suffix."""
    m = SIDE_SUFFIX.match(name)
    return m.group(2) if m else ""


def twin_of(name):
    """Name of the contralateral object, or None if the name has no side."""
    m = SIDE_SUFFIX.match(name)
    if not m:
        return None
    return m.group(1) + ("r" if m.group(2) == "l" else "l")


def base_name(name):
    """The name without its side suffix."""
    m = SIDE_SUFFIX.match(name)
    return name[:name.rfind(".")] if m else name


def assert_exclusions(rows):
    """Assert EXPECTED over the full inventory. rows: dicts with object_name,
    object_type, triangles. Returns the per-set counts. Raises on drift."""
    counts = {k: {"objects": 0, "with_geometry": 0, "triangles": 0} for k in EXPECTED}
    for r in rows:
        if r["object_type"] != "MESH":
            continue
        k = exclusion_set(r["object_name"])
        if k is None:
            continue
        counts[k]["objects"] += 1
        if int(r["triangles"]) > 0:
            counts[k]["with_geometry"] += 1
        counts[k]["triangles"] += int(r["triangles"])
    for k, exp in EXPECTED.items():
        if counts[k] != exp:
            raise AssertionError(
                "EXCLUSIONS drift in %s: expected %r, found %r - stop, do not export"
                % (k, exp, counts[k]))
    return counts


def partition(rows):
    """Split the full inventory.

    rows: dicts with object_name, object_type, triangles, all_collections
    (a list of full collection paths).

    Returns (kept, excluded, report):
      kept      rows in scope and licence-clean, each given r['system']
      excluded  rows that passed scope but hit a licence exclusion
      report    the numbers the build prints and asserts
    """
    scoped = []
    for r in rows:
        if r["object_type"] != "MESH" or int(r["triangles"]) <= 0:
            continue
        if is_label(r["object_name"]):
            continue
        hits = in_scope_collections(r["all_collections"])
        if not hits:
            continue
        if len(hits) > 1:
            raise AssertionError("%s is filed under %r - one system per object is assumed"
                                 % (r["object_name"], hits))
        r["system"] = SYSTEM_OF_COLLECTION[hits[0]]
        scoped.append(r)

    scope_meshes = len(scoped)
    scope_tris = sum(int(r["triangles"]) for r in scoped)
    if (scope_meshes, scope_tris) != (EXPECTED_SCOPE["meshes"], EXPECTED_SCOPE["triangles"]):
        raise AssertionError(
            "scope drift: expected %d meshes / %d triangles, found %d / %d"
            % (EXPECTED_SCOPE["meshes"], EXPECTED_SCOPE["triangles"], scope_meshes, scope_tris))

    # Licence filter over the whole inventory, then over what scope kept. The
    # difference is how much the scope filter had already removed.
    full_counts = assert_exclusions(rows)
    kept, excluded = [], []
    for r in scoped:
        if exclusion_set(r["object_name"]):
            excluded.append(r)
        else:
            kept.append(r)

    total_excludable = sum(c["with_geometry"] for c in full_counts.values())
    report = {
        "scope_meshes": scope_meshes,
        "scope_triangles": scope_tris,
        "exclusion_counts": full_counts,
        "excludable_with_geometry": total_excludable,
        "caught_by_scope": total_excludable - len(excluded),
        "caught_by_licence_filter": len(excluded),
        "excluded_names": sorted(r["object_name"] for r in excluded),
        "excluded_triangles": sum(int(r["triangles"]) for r in excluded),
        "kept_meshes": len(kept),
        "kept_triangles": sum(int(r["triangles"]) for r in kept),
    }
    return kept, excluded, report


def format_report(report):
    lines = [
        "scope: %d meshes / %d triangles (expected %d / %d)" % (
            report["scope_meshes"], report["scope_triangles"],
            EXPECTED_SCOPE["meshes"], EXPECTED_SCOPE["triangles"]),
        "exclusions asserted on the full inventory: " + ", ".join(
            "%s=%d/%d/%d" % (k, c["objects"], c["with_geometry"], c["triangles"])
            for k, c in report["exclusion_counts"].items()),
        "excludable meshes with geometry: %d; already removed by the scope filter: %d; "
        "removed by the licence filter itself: %d (%d triangles)" % (
            report["excludable_with_geometry"], report["caught_by_scope"],
            report["caught_by_licence_filter"], report["excluded_triangles"]),
    ]
    if report["caught_by_licence_filter"] == 0:
        lines.append("WARNING: the licence filter removed nothing - every exclusion was "
                     "already outside scope. The filter is inert on this scope and its "
                     "correctness is only proven by the EXPECTED assertion above.")
    else:
        lines.append("licence filter removed: " + ", ".join(report["excluded_names"]))
    lines.append("kept: %d meshes / %d triangles" % (report["kept_meshes"], report["kept_triangles"]))
    return "\n".join(lines)
