"""Fit the Z-Anatomy body onto the BodyParts3D body, landmark by landmark.

The 42 palpable landmarks in landmark_anchors.py are rules on a bone's real
vertices - "the most lateral femoral vertex", "the most anterior vertex in the
top 3 mm of the manubrium's midline". A rule is a description, and a
description can be run on another model's bone as well as on ours. So the
correspondence between the two bodies is not thirty hand-picked points but the
same 42 descriptions resolved on both: on Z-Anatomy by build_landmarks.py
(landmarks.json), and here on the BodyParts3D bones read straight out of the
atlas chunks. Both sides of BP3D are measured on their own bones - the right
bone with the left rule mirrored - so an asymmetry in BP3D shows in the
residuals instead of being hidden by a reflection.

The fit is a global similarity (scale, rotation, translation; Umeyama), then
one residual similarity per MVMT region on that region's own landmarks,
blended between regions by a Gaussian of the distance to each region's
landmarks so a vertex between two regions moves smoothly. A region with fewer
than six points gets a translation only: seven degrees of freedom on five
points is a fit to noise.

Frames. Z-Anatomy and landmark_anchors.py: metres, Z up, +X left, -Y anterior.
BodyParts3D atlas.json and our glTF export: metres, Y up, +X left, +Z anterior.
BP3D vertices are converted into the Z-Anatomy frame before a rule sees them,
the whole fit lives in that frame, and the record carries both forms.

Runs in Blender's Python for mathutils only; no .blend is opened.

    blender -b --python tools/bp3d_fit.py -- --atlas <mvmt-atlas/public/models> [--out bp3d-fit.json]

Prints the residual table and BP3D_FIT_OK, or exits non-zero.
"""

import argparse
import gzip
import json
import math
import os
import sys

import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.append(HERE)
from landmark_anchors import LANDMARKS, PUSH, ext, resolve_bounds  # noqa: E402

# ------------------------------------------------------------------ frames

def bp3d_to_za(p):
    """BP3D (x, y up, z anterior) -> Z-Anatomy (x, -y anterior, z up)."""
    return np.stack([p[..., 0], -p[..., 2], p[..., 1]], axis=-1)


def za_to_bp3d(p):
    return np.stack([p[..., 0], p[..., 2], -p[..., 1]], axis=-1)


# ------------------------------------------------------------ bone name map

# Z-Anatomy anchor object -> the BP3D part carrying the same bone, left side or
# unsided. The right side is right_name() of it.
BONE_MAP = {
    "Temporal bone.l": "Left temporal bone",
    "Occipital bone": "Occipital bone",
    "Atlas (C1)": "Atlas",
    "Axis (C2)": "Axis",
    "Vertebra C7": "Seventh cervical vertebra",
    "Mandible": "Mandible",
    "Zygomatic bone.l": "Left zygomatic bone",
    "Scapula.l": "Left scapula",
    "Humerus.l": "Left humerus",
    "Manubrium of sternum": "Manubrium",
    "Seventh rib.l": "Left seventh rib",
    "Ulna.l": "Left ulna",
    "Radius.l": "Left radius",
    "Scaphoid bone.l": "Left scaphoid",
    "Pisiform bone.l": "Left pisiform",
    "Hip bone.l": "Left hip bone",
    "Femur.l": "Left femur",
    "Sacrum": "Sacrum",
    "Tibia.l": "Left tibia",
    "Fibula.l": "Left fibula",
    "Navicular bone.l": "Navicular bone of left foot",
    "Fifth metatarsal bone.l": "Left fifth metatarsal bone",
    "Calcaneus.l": "Left calcaneus",
}


def right_name(name):
    if name.startswith("Left "):
        return "Right " + name[5:]
    if " left " in name:
        return name.replace(" left ", " right ")
    return name


# Which landmarks anchor each MVMT region's residual fit. A landmark may serve
# more than one region: the acromion is where the cervical fit meets the
# shoulder's, the iliac crest where the lumbar fit meets the hip's.
REGION_LANDMARKS = {
    "head-jaw": ["lm-mastoid-process", "lm-occipital-protuberance", "lm-superior-nuchal-line",
                 "lm-mandible-angle", "lm-zygomatic-arch", "lm-c1-transverse", "lm-c2-spinous"],
    "cervical": ["lm-c1-transverse", "lm-c2-spinous", "lm-c7-spinous", "lm-mastoid-process",
                 "lm-occipital-protuberance", "lm-jugular-notch", "lm-acromion"],
    "shoulder": ["lm-acromion", "lm-coracoid", "lm-scapular-spine", "lm-inferior-angle",
                 "lm-scapular-medial-border", "lm-greater-tubercle", "lm-bicipital-groove",
                 "lm-c7-spinous", "lm-jugular-notch", "lm-sternal-angle"],
    "thoracic": ["lm-jugular-notch", "lm-sternal-angle", "lm-costal-margin", "lm-c7-spinous",
                 "lm-inferior-angle", "lm-scapular-medial-border", "lm-scapular-spine"],
    "lumbar": ["lm-costal-margin", "lm-iliac-crest", "lm-psis", "lm-sacral-base", "lm-asis"],
    "hip": ["lm-iliac-crest", "lm-asis", "lm-psis", "lm-ischial-tuberosity", "lm-pubic-tubercle",
            "lm-greater-trochanter", "lm-sacral-base"],
    "knee": ["lm-tibial-tuberosity", "lm-gerdys-tubercle", "lm-knee-joint-line", "lm-fibular-head",
             "lm-adductor-tubercle", "lm-greater-trochanter"],
    "elbow-wrist": ["lm-medial-epicondyle", "lm-lateral-epicondyle", "lm-olecranon",
                    "lm-radial-styloid", "lm-ulnar-styloid", "lm-anatomical-snuffbox", "lm-pisiform"],
    "ankle-foot": ["lm-medial-malleolus", "lm-lateral-malleolus", "lm-navicular-tuberosity",
                   "lm-fifth-metatarsal-base", "lm-sustentaculum-tali", "lm-fibular-head"],
}
MIN_SIMILARITY_POINTS = 6
BLEND_SIGMA = 0.12      # metres; how far a region's residual reaches
BLEND_FLOOR = 0.02      # weight of "no residual" so a point far from every landmark stays on the global fit


# --------------------------------------------------------------- the atlas

def load_atlas(models_dir):
    atlas = json.load(open(os.path.join(models_dir, "atlas.json"), encoding="utf-8"))
    chunks = []
    for c in atlas["chunks"]:
        path = os.path.join(models_dir, os.path.basename(c["gzip"] if c.get("gzip") else c["url"]))
        with open(path, "rb") as f:
            raw = f.read()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        assert len(raw) == c["bytes"], "%s: %d bytes, manifest says %d" % (path, len(raw), c["bytes"])
        chunks.append(raw)
    parts = {}
    for p in atlas["parts"]:
        parts.setdefault(p["name"].lower(), p)
    return atlas, chunks, parts


def part_vertices(part, chunks):
    """Positions in the BP3D frame, only those a triangle references."""
    b = chunks[part["chunk"]]
    pos = np.frombuffer(b, dtype=np.float32, count=part["vertexCount"] * 3, offset=part["positions"]).reshape(-1, 3)
    idx = np.frombuffer(b, dtype=np.uint32, count=part["indexCount"], offset=part["indices"])
    used = np.zeros(part["vertexCount"], dtype=bool)
    used[idx] = True
    return pos[used].astype(np.float64)


# ------------------------------------------------------------ resolving

def resolve_rule(spec, V, lo, hi):
    rule = spec["rule"]
    if callable(rule):
        v = rule(V, lo, hi)
    else:
        d, bounds = rule
        v = ext(V, d, **resolve_bounds(bounds, lo, hi))
    return v, v + spec["push"] * PUSH


def resolve_on_bp3d(spec, verts_za, mirror):
    """Run a left-side rule on a BP3D bone. For a right bone the vertices are
    reflected to the left, the rule runs, and the result reflects back."""
    pts = verts_za.copy()
    if mirror:
        pts[:, 0] = -pts[:, 0]
    V = [Vector(p) for p in pts]
    lo = Vector(pts.min(axis=0))
    hi = Vector(pts.max(axis=0))
    v, p = resolve_rule(spec, V, lo, hi)
    v, p = Vector(v), Vector(p)
    if mirror:
        v.x, p.x = -v.x, -p.x
    return np.array(v), np.array(p)


# ---------------------------------------------------------------- fitting

def umeyama(src, dst, with_scale=True):
    """Similarity s*R*x + t minimising |dst - (s R src + t)|^2 (Umeyama 1991)."""
    n = src.shape[0]
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    xs, xd = src - mu_s, dst - mu_d
    cov = xd.T @ xs / n
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1
    R = U @ S @ Vt
    var_s = (xs ** 2).sum() / n
    s = float((D * np.diag(S)).sum() / var_s) if with_scale else 1.0
    t = mu_d - s * R @ mu_s
    return s, R, t


def apply_sim(sim, p):
    s, R, t = sim
    return s * (p @ R.T) + t


def rms(d):
    return float(np.sqrt((d ** 2).sum(axis=1).mean()))


class Fit:
    """The blended transform, Z-Anatomy frame in, Z-Anatomy frame out."""

    def __init__(self, glob, regions, anchors):
        self.glob = glob
        self.regions = regions          # id -> dict(kind, sim or t)
        self.anchors = anchors          # id -> (n,3) Z-Anatomy landmark points of that region

    @classmethod
    def from_record(cls, rec):
        """Rebuild the transform from bp3d-fit.json, so the export applies
        exactly what the record says and nothing recomputed."""
        g = rec["globalFit"]
        glob = (g["scale"], np.array(g["rotation"], dtype=np.float64), np.array(g["translation"], dtype=np.float64))
        regions, anchors = {}, {}
        for rid, r in rec["regions"].items():
            if r["kind"] == "similarity":
                regions[rid] = dict(kind="similarity", sim=(r["scale"], np.array(r["rotation"], dtype=np.float64),
                                                            np.array(r["translation"], dtype=np.float64)))
            elif r["kind"] == "translation":
                regions[rid] = dict(kind="translation", t=np.array(r["translation"], dtype=np.float64))
            else:
                regions[rid] = dict(kind="none")
            anchors[rid] = np.array(r["anchors"], dtype=np.float64).reshape(-1, 3)
        fit = cls(glob, regions, anchors)
        fit.sigma = rec["blend"]["sigma"]
        fit.floor = rec["blend"]["floor"]
        return fit

    def weights(self, p):
        """Blend weight of every region at p, plus the floor; the export's
        region-of-a-point and the seam check both read these."""
        p = np.asarray(p, dtype=np.float64).reshape(-1, 3)
        sigma = getattr(self, "sigma", BLEND_SIGMA)
        out = {}
        for rid, pts in self.anchors.items():
            d2 = ((p[:, None, :] - pts[None, :, :]) ** 2).sum(axis=2).min(axis=1)
            out[rid] = np.exp(-d2 / (sigma ** 2))
        return out

    def residual(self, rid, q):
        r = self.regions[rid]
        if r["kind"] == "similarity":
            return apply_sim(r["sim"], q) - q
        if r["kind"] == "translation":
            return np.broadcast_to(r["t"], q.shape)
        return np.zeros_like(q)

    def __call__(self, p, allowed=None):
        """allowed: the regions whose residuals may act on these points. The
        blend is by distance to landmarks, and the hand hangs beside the
        abdomen in the A-pose, so without it the wrist's residual reaches the
        abdominal fascia. A part is blended from its home region and that
        region's neighbours only."""
        p = np.asarray(p, dtype=np.float64)
        q = apply_sim(self.glob, p)
        num = np.zeros_like(q)
        den = np.full(q.shape[0], getattr(self, "floor", BLEND_FLOOR))
        sigma = getattr(self, "sigma", BLEND_SIGMA)
        for rid, pts in self.anchors.items():
            if allowed is not None and rid not in allowed:
                continue
            d2 = ((p[:, None, :] - pts[None, :, :]) ** 2).sum(axis=2).min(axis=1)
            w = np.exp(-d2 / (sigma ** 2))
            num += w[:, None] * self.residual(rid, q)
            den += w
        return q + num / den[:, None]


# ------------------------------------------------------------------- main

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, help="mvmt-atlas/public/models")
    ap.add_argument("--out", default=os.path.join(ROOT, "bp3d-fit.json"))
    args = ap.parse_args(argv)

    atlas, chunks, parts = load_atlas(args.atlas)
    za = json.load(open(os.path.join(ROOT, "landmarks.json"), encoding="utf-8"))
    za_by_id = {x["id"]: x for x in za["landmarks"]}
    specs = {s["id"]: s for s in LANDMARKS}
    assert set(za_by_id) == set(specs), "landmarks.json and landmark_anchors.py disagree"

    rows = []          # one per (landmark, side)
    failures = []
    for spec in LANDMARKS:
        rec = za_by_id[spec["id"]]
        left = BONE_MAP[spec["object"]]
        sides = [("l", left, False), ("r", right_name(left), True)] if spec["paired"] else [("m", left, False)]
        for side, bp_name, mirror in sides:
            part = parts.get(bp_name.lower())
            if part is None:
                failures.append((spec["id"], side, "no BP3D part named %r" % bp_name))
                continue
            verts = bp3d_to_za(part_vertices(part, chunks))
            try:
                v, p = resolve_on_bp3d(spec, verts, mirror)
            except ValueError as e:
                failures.append((spec["id"], side, str(e)))
                continue
            z = np.array(rec["resolved"][side], dtype=np.float64)
            rows.append(dict(id=spec["id"], name=spec["name"], side=side, bone=spec["object"],
                             bp3dPart=bp_name, bp3dPartId=part["id"], bp3dVertices=int(len(verts)),
                             za=z, bp=p, bpVertex=v))
    if failures:
        for f in failures:
            print("RULE FAILED %s %s: %s" % f)
    if len(rows) < 30:
        print("BP3D_FIT_FAILED: only %d landmark pairs resolved" % len(rows))
        sys.exit(1)

    Z = np.array([r["za"] for r in rows])
    B = np.array([r["bp"] for r in rows])

    # global similarity
    glob = umeyama(Z, B)
    G = apply_sim(glob, Z)
    for r, g in zip(rows, G):
        r["global"] = g
        r["resGlobal"] = float(np.linalg.norm(g - r["bp"]))

    # per-region residuals on the globally fitted points
    regions, anchors = {}, {}
    for rid, ids in REGION_LANDMARKS.items():
        sel = [i for i, r in enumerate(rows) if r["id"] in ids]
        src, dst = G[sel], B[sel]
        anchors[rid] = Z[sel]
        before = rms(dst - src)
        if len(sel) >= MIN_SIMILARITY_POINTS:
            sim = umeyama(src, dst)
            after = rms(dst - apply_sim(sim, src))
            regions[rid] = dict(kind="similarity", sim=sim, n=len(sel), ids=sorted(set(rows[i]["id"] for i in sel)),
                                rmsBefore=before, rmsAfter=after)
        elif sel:
            t = (dst - src).mean(axis=0)
            after = rms(dst - (src + t))
            regions[rid] = dict(kind="translation", t=t, n=len(sel), ids=sorted(set(rows[i]["id"] for i in sel)),
                                rmsBefore=before, rmsAfter=after)
        else:
            regions[rid] = dict(kind="none", n=0, ids=[], rmsBefore=0.0, rmsAfter=0.0)

    fit = Fit(glob, regions, anchors)
    F = fit(Z)
    for r, f in zip(rows, F):
        r["blended"] = f
        r["resBlended"] = float(np.linalg.norm(f - r["bp"]))

    # ---- report
    def mm(x):
        return "%6.1f" % (x * 1000)

    print("")
    print("%-28s %-4s %-30s %6s %8s %8s" % ("landmark", "side", "BP3D part", "verts", "global", "blended"))
    for r in rows:
        flag = "  <-- check" if r["resBlended"] > 0.020 else ""
        print("%-28s %-4s %-30s %6d %8s %8s%s" % (r["id"], r["side"], r["bpPart"] if "bpPart" in r else r["bp3dPart"],
                                                  r["bp3dVertices"], mm(r["resGlobal"]), mm(r["resBlended"]), flag))
    rg = np.array([r["resGlobal"] for r in rows])
    rb = np.array([r["resBlended"] for r in rows])
    print("")
    print("pairs %d   global: rms %s  median %s  max %s mm   blended: rms %s  median %s  max %s mm" % (
        len(rows), mm(math.sqrt((rg ** 2).mean())), mm(np.median(rg)), mm(rg.max()),
        mm(math.sqrt((rb ** 2).mean())), mm(np.median(rb)), mm(rb.max())))
    s, R, t = glob
    print("global: scale %.4f, rotation %.2f deg, translation (%s) mm" % (
        s, math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2)))), ", ".join(mm(c).strip() for c in t)))
    for rid, r in regions.items():
        extra = " scale %.4f" % r["sim"][0] if r["kind"] == "similarity" else ""
        print("region %-12s %-11s n=%2d  rms %s -> %s mm%s" % (rid, r["kind"], r["n"], mm(r["rmsBefore"]), mm(r["rmsAfter"]), extra))

    # ---- record
    def sim_json(sim):
        s, R, t = sim
        return dict(scale=round(float(s), 6), rotation=[[round(float(x), 6) for x in row] for row in R],
                    translation=[round(float(x), 6) for x in t])

    # the global similarity expressed in the BP3D / glTF frame as well: C x, where C converts frames
    C = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)   # za -> bp3d
    Rg = C @ R @ C.T
    tg = C @ t
    out = dict(
        version=1,
        note="Z-Anatomy -> BodyParts3D. The 42 landmark rules of landmark_anchors.py run on the BP3D bones "
             "(right bones with the left rule mirrored) against landmarks.json; global similarity by Umeyama, "
             "a residual similarity (or translation, under %d points) per MVMT region, blended by a Gaussian "
             "of the distance to each region's landmarks (sigma %.2f m, floor %.2f). Residuals are the blended "
             "transform at the landmark, in metres." % (MIN_SIMILARITY_POINTS, BLEND_SIGMA, BLEND_FLOOR),
        units="metres",
        frames=dict(zanatomy="Z up, +X left, -Y anterior (the fit's own frame)",
                    bp3d="Y up, +X left, +Z anterior (atlas.json and our glTF export)",
                    zanatomyToBp3d="(x, y, z) -> (x, z, -y)"),
        source=dict(atlas=atlas.get("version"), landmarks="landmarks.json", rules="tools/landmark_anchors.py"),
        boneMap=BONE_MAP,
        blend=dict(sigma=BLEND_SIGMA, floor=BLEND_FLOOR, minSimilarityPoints=MIN_SIMILARITY_POINTS),
        globalFit=dict(**sim_json(glob), inBp3dFrame=dict(scale=round(float(s), 6),
                                                          rotation=[[round(float(x), 6) for x in row] for row in Rg],
                                                          translation=[round(float(x), 6) for x in tg]),
                       rms=round(float(math.sqrt((rg ** 2).mean())), 5), median=round(float(np.median(rg)), 5),
                       max=round(float(rg.max()), 5)),
        regions={rid: dict(kind=r["kind"], n=r["n"], landmarks=r["ids"],
                           rmsBefore=round(r["rmsBefore"], 5), rmsAfter=round(r["rmsAfter"], 5),
                           **(sim_json(r["sim"]) if r["kind"] == "similarity" else
                              dict(translation=[round(float(x), 6) for x in r["t"]]) if r["kind"] == "translation" else {}),
                           anchors=[[round(float(c), 5) for c in p] for p in anchors[rid]])
                 for rid, r in regions.items()},
        summary=dict(pairs=len(rows), failed=[dict(id=a, side=b, why=c) for a, b, c in failures],
                     blended=dict(rms=round(float(math.sqrt((rb ** 2).mean())), 5), median=round(float(np.median(rb)), 5),
                                  max=round(float(rb.max()), 5), over20mm=int((rb > 0.02).sum()))),
        landmarks=[dict(id=r["id"], name=r["name"], side=r["side"], bone=r["bone"], bp3dPart=r["bp3dPart"],
                        bp3dPartId=r["bp3dPartId"], bp3dVertices=r["bp3dVertices"],
                        zanatomy=[round(float(c), 5) for c in r["za"]],
                        bp3d=[round(float(c), 5) for c in r["bp"]],
                        bp3dVertex=[round(float(c), 5) for c in r["bpVertex"]],
                        afterGlobal=[round(float(c), 5) for c in r["global"]],
                        afterBlend=[round(float(c), 5) for c in r["blended"]],
                        residualGlobal=round(r["resGlobal"], 5), residualBlended=round(r["resBlended"], 5))
                   for r in rows],
    )
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("wrote %s" % args.out)
    print("BP3D_FIT_OK")


if __name__ == "__main__":
    main()
