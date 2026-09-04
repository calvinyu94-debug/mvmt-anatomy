"""The mannequin's rig as the exported file states it. Pure Python and numpy,
no bpy: everything here is computed from mannequin.glb itself, so what it
says is what a glTF viewer will do with the file.

Three things live here, shared by build_mannequin.py (which writes
rig-manifest.json) and verify_mannequin.py (which re-derives the table from
the shipped file and compares):

  * a GLB reader that rebuilds the joint hierarchy and skins the mesh by
    linear blend skinning - the same arithmetic three.js's SkinnedMesh does;
  * the app's joint vocabulary, each joint resolved to a bone, with the probe
    that makes its motion observable (the knee for the hip, the wrist for the
    elbow, the knuckle for the wrist, ...);
  * the calibration: for every anatomical motion, the unit vector in the
    bone's own frame about which a positive rotation IS that motion, measured
    by applying the rotation and watching where the probe goes - never read
    off the bone's axis labels. The game-engine rig's bones are rolled
    obliquely (the thigh by a third of a right angle), so "flexion is +X" is
    exactly the trap the brief warns about; the table carries vectors, and
    says how far the nearest labelled axis is from each.

Frames. glTF is Y-up; this file is exported +Z anterior, +X the figure's
left, metres, feet on the floor. A bone's "own frame" is the one three.js
applies `bone.quaternion` in: the joint node's rest orientation, so a pose is
`rest x neutral x Q(axis, angle)` with quaternions post-multiplied. The
shoulder bones need a `neutral` offset because the rest pose is a T-pose and
anatomical zero is arms at the sides; every other bone's neutral is the rest.
"""

import json
import math
import struct

import numpy as np

# ------------------------------------------------------------------ vocabulary

# Which bone each of the app's joints drives, with the probe whose motion
# reveals what a rotation did. `distal` is a node whose origin sits at the far
# end of the segment; `tip` means "extrapolate one more bone length", for the
# last phalanges, which have no child node. Both sides come from one template.
_TEMPLATE = [
    # joint, bone, group, params, distal probe
    ("cervical", "neck_01", "spine", ["flex", "sideBend", "rot"], "head"),
    ("thoracic", "spine_03", "spine", ["flex", "sideBend", "rot"], "neck_01"),
    ("lumbar", "spine_01", "spine", ["flex", "sideBend", "rot"], "spine_02"),
    ("pelvis", "pelvis", "pelvis", ["tilt", "pitch"], "spine_01"),
    ("shoulder{S}", "upperarm_{s}", "shoulder", ["flex", "abd", "rot", "hAdd"], "lowerarm_{s}"),
    ("elbow{S}", "lowerarm_{s}", "elbow", ["flex"], "hand_{s}"),
    ("forearm{S}", "lowerarm_{s}", "forearm", ["sup"], "hand_{s}"),
    ("wrist{S}", "hand_{s}", "wrist", ["flex", "dev"], "middle_01_{s}"),
    ("hip{S}", "thigh_{s}", "hip", ["flex", "abd", "rot"], "calf_{s}"),
    ("knee{S}", "calf_{s}", "knee", ["flex"], "foot_{s}"),
    ("ankle{S}", "foot_{s}", "ankle", ["df"], "ball_{s}"),
]
FINGERS = ["index", "middle", "ring", "pinky"]     # the thumb is not in the vocabulary

# The effectors the app pins. Each names the bone whose origin is the point
# that stays put: the wrist for a planted hand, the ankle for a planted foot.
_EFFECTORS = {
    "hand{S}": "hand_{s}", "foot{S}": "foot_{s}", "knee{S}": "calf_{s}", "thorax": "spine_03",
}

# Parameter order within a bone: an intrinsic sequence, each rotation about
# the bone's then-current axis. Flexion first, then the frontal-plane motion,
# then anything about the long axis. hAdd sits before rot because it is only
# meaningful once the arm is raised.
PARAM_ORDER = ["flex", "tilt", "pitch", "abd", "sideBend", "dev", "hAdd", "rot", "sup"]

# (world axis, probe, expected world direction of the probe's displacement).
# World axes: ML = +X, AP = +Z, S = +Y, LONG = along the segment. Expected
# directions: A anterior, S superior, LAT lateral for that side, X the
# figure's left (so -X is toward the right, which is what "bend / look to the
# right" means for a midline bone).
MOTIONS = {
    "spine": {"flex": ("ML", "distal", "+A"), "sideBend": ("AP", "distal", "-X"), "rot": ("S", "anterior", "-X")},
    "pelvis": {"tilt": ("ML", "distal", "+A"), "pitch": ("ML", "distal", "+A")},
    "shoulder": {"flex": ("ML", "distal", "+A"), "abd": ("AP", "distal", "+LAT"),
                 "rot": ("LONG", "anterior", "+LAT"), "hAdd": ("S", "distal", "+A")},
    "elbow": {"flex": ("ML", "distal", "+A")},
    "forearm": {"sup": ("LONG", "anterior", "+LAT")},
    "wrist": {"flex": ("AP", "distal", "-LAT"), "dev": ("ML", "distal", "+A")},
    "fingers": {"flex": ("AP", "distal", "-LAT")},
    "hip": {"flex": ("ML", "distal", "+A"), "abd": ("AP", "distal", "+LAT"), "rot": ("LONG", "anterior", "+LAT")},
    "knee": {"flex": ("ML", "distal", "-A")},
    "ankle": {"df": ("ML", "distal", "+S")},
}
# hAdd is measured in the rest pose (arm abducted 90), every other motion in
# anatomical neutral; see calibrate().
MEASURED_AT_REST = {("shoulder", "hAdd")}

MOTION_PROSE = {
    "flex": "flexion", "sideBend": "side bend toward the right", "rot": "rotation (spine: turn to look right; limb: external)",
    "tilt": "anterior pelvic tilt", "pitch": "whole-body lean forward", "abd": "abduction",
    "hAdd": "horizontal adduction across the body (measured at 90 abduction)", "sup": "supination",
    "dev": "radial deviation", "df": "dorsiflexion",
}

ACCEPT_COSINE = 0.7     # the probe must move within ~45 degrees of the expected direction


def vocabulary():
    """[{joint, bones, group, params, probes}] for both sides, in the order
    the pose is applied (elbow before forearm, which share a bone)."""
    out = []
    for joint, bone, group, params, probe in _TEMPLATE:
        if "{S}" in joint:
            for S, s in (("L", "l"), ("R", "r")):
                out.append({"joint": joint.format(S=S), "bones": [bone.format(s=s)], "group": group,
                            "params": params, "probes": {bone.format(s=s): probe.format(s=s)}, "side": s})
                if joint == "wrist{S}":
                    bones, probes = [], {}
                    for f in FINGERS:
                        for k in (1, 2, 3):
                            b = "%s_%02d_%s" % (f, k, s)
                            bones.append(b)
                            probes[b] = ("%s_%02d_%s" % (f, k + 1, s)) if k < 3 else "tip"
                    out.append({"joint": "fingers" + S, "bones": bones, "group": "fingers", "params": ["flex"],
                                "probes": probes, "side": s})
        else:
            out.append({"joint": joint, "bones": [bone], "group": group, "params": params,
                        "probes": {bone: probe}, "side": ""})
    return out


def effectors():
    out = {}
    for k, v in _EFFECTORS.items():
        if "{S}" in k:
            for S, s in (("L", "l"), ("R", "r")):
                out[k.format(S=S)] = v.format(s=s)
        else:
            out[k] = v
    return out


# ------------------------------------------------------------------ quaternions
# (x, y, z, w) throughout, as glTF and three.js store them.


def q_identity():
    return np.array([0.0, 0.0, 0.0, 1.0])


def q_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz])


def q_axis_angle(axis, deg):
    axis = np.asarray(axis, dtype=float)
    n = np.linalg.norm(axis)
    if n == 0:
        raise ValueError("zero axis")
    axis = axis / n
    h = math.radians(deg) / 2.0
    return np.array([axis[0] * math.sin(h), axis[1] * math.sin(h), axis[2] * math.sin(h), math.cos(h)])


def q_to_mat(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def mat_to_q(m):
    t = np.trace(m)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        return np.array([(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s])
    i = int(np.argmax(np.diag(m)))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(max(1.0 + m[i, i] - m[j, j] - m[k, k], 0.0)) * 2
    q = np.zeros(4)
    q[i] = 0.25 * s
    q[j] = (m[j, i] + m[i, j]) / s
    q[k] = (m[k, i] + m[i, k]) / s
    q[3] = (m[k, j] - m[j, k]) / s
    return q


# ------------------------------------------------------------------ GLB

_CTYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_glb(path):
    with open(path, "rb") as f:
        b = f.read()
    magic, _, length = struct.unpack("<III", b[:12])
    if magic != 0x46546C67:
        raise ValueError("%s is not a GLB" % path)
    off, js, blob = 12, None, None
    while off < length:
        clen, ctype = struct.unpack("<II", b[off:off + 8])
        off += 8
        chunk = b[off:off + clen]
        off += clen
        if ctype == 0x4E4F534A:
            js = json.loads(chunk)
        elif ctype == 0x004E4942:
            blob = chunk
    return js, blob


def accessor(g, blob, idx):
    a = g["accessors"][idx]
    bv = g["bufferViews"][a["bufferView"]]
    dt = _CTYPES[a["componentType"]]
    n = _NCOMP[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    item = np.dtype(dt).itemsize * n
    stride = bv.get("byteStride", 0) or item
    if stride == item:
        arr = np.frombuffer(blob, dtype=dt, count=a["count"] * n, offset=start).reshape(a["count"], n)
    else:
        raw = np.frombuffer(blob, dtype=np.uint8, count=stride * (a["count"] - 1) + item, offset=start)
        arr = np.array([np.frombuffer(raw[i * stride:i * stride + item].tobytes(), dtype=dt)
                        for i in range(a["count"])])
    arr = np.array(arr)
    if a.get("normalized"):
        arr = arr.astype(np.float64) / np.iinfo(dt).max
    return arr


class Rig:
    """The joint hierarchy and the skinned mesh of a single-skin GLB."""

    def __init__(self, path):
        self.path = path
        self.g, self.blob = read_glb(path)
        g = self.g
        self.nodes = g["nodes"]
        self.parent = [-1] * len(self.nodes)
        for i, n in enumerate(self.nodes):
            for c in n.get("children", []):
                self.parent[c] = i
        if len(g.get("skins", [])) != 1:
            raise ValueError("expected exactly one skin, found %d" % len(g.get("skins", [])))
        self.skin = g["skins"][0]
        self.joints = list(self.skin["joints"])
        ibm = accessor(g, self.blob, self.skin["inverseBindMatrices"]).reshape(-1, 4, 4)
        self.ibm = np.transpose(ibm, (0, 2, 1))          # glTF matrices are column-major
        self.by_name = {}
        for j in self.joints:
            name = self.nodes[j].get("name", "")
            self.by_name.setdefault(name, []).append(j)
        meshes = [i for i, n in enumerate(self.nodes) if "mesh" in n]
        if len(meshes) != 1:
            raise ValueError("expected exactly one mesh node, found %d" % len(meshes))
        self.mesh_node = meshes[0]
        mesh = g["meshes"][self.nodes[self.mesh_node]["mesh"]]
        if len(mesh["primitives"]) != 1:
            raise ValueError("expected one primitive, found %d" % len(mesh["primitives"]))
        prim = mesh["primitives"][0]
        att = prim["attributes"]
        self.positions = accessor(g, self.blob, att["POSITION"]).astype(np.float64)
        self.skin_joints = accessor(g, self.blob, att["JOINTS_0"]).astype(int)
        self.skin_weights = accessor(g, self.blob, att["WEIGHTS_0"]).astype(np.float64)
        if "JOINTS_1" in att:
            raise ValueError("more than four influences per vertex; the app skins with four")
        self.indices = accessor(g, self.blob, prim["indices"]).reshape(-1) if "indices" in prim else None
        self.triangles = len(self.indices) // 3 if self.indices is not None else len(self.positions) // 3
        # topological order: parents before children
        order, seen = [], set()

        def visit(i):
            if i in seen:
                return
            if self.parent[i] >= 0:
                visit(self.parent[i])
            seen.add(i)
            order.append(i)
        for i in range(len(self.nodes)):
            visit(i)
        self.order = order

    # -- names -------------------------------------------------------------
    def joint(self, name):
        """The one joint node with this name; a hard error otherwise."""
        hits = self.by_name.get(name, [])
        if len(hits) != 1:
            raise KeyError("bone %r resolves to %d joints, expected exactly 1" % (name, len(hits)))
        return hits[0]

    def rest_local(self, i):
        n = self.nodes[i]
        t = np.array(n.get("translation", [0, 0, 0]), dtype=float)
        q = np.array(n.get("rotation", [0, 0, 0, 1]), dtype=float)
        s = np.array(n.get("scale", [1, 1, 1]), dtype=float)
        if "matrix" in n:
            m = np.array(n["matrix"], dtype=float).reshape(4, 4).T
            t = m[:3, 3]
            r = m[:3, :3]
            s = np.linalg.norm(r, axis=0)
            q = mat_to_q(r / s)
        return t, q, s

    # -- transforms --------------------------------------------------------
    def world(self, pose=None):
        """(n_nodes, 4, 4) world matrices. `pose` maps node index to a local
        quaternion (x, y, z, w) post-multiplied onto the rest rotation, and
        may map an index to (quaternion, translation) to move a root."""
        pose = pose or {}
        W = np.zeros((len(self.nodes), 4, 4))
        for i in self.order:
            t, q, s = self.rest_local(i)
            p = pose.get(i)
            if p is not None:
                if isinstance(p, tuple):
                    q = q_mul(q, p[0])
                    t = t + np.asarray(p[1], dtype=float)
                else:
                    q = q_mul(q, p)
            m = np.eye(4)
            m[:3, :3] = q_to_mat(q) * s
            m[:3, 3] = t
            W[i] = m if self.parent[i] < 0 else W[self.parent[i]] @ m
        return W

    def skinned(self, pose=None, W=None):
        """World-space vertex positions under `pose`, by linear blend skinning
        of the file's own weights: sum_k w_k (World_k x IBM_k) v."""
        if W is None:
            W = self.world(pose)
        S = np.array([W[j] @ self.ibm[k] for k, j in enumerate(self.joints)])
        out = np.zeros_like(self.positions)
        P = self.positions
        for k in range(self.skin_joints.shape[1]):
            M = S[self.skin_joints[:, k]]
            out += self.skin_weights[:, k:k + 1] * (np.einsum("nij,nj->ni", M[:, :3, :3], P) + M[:, :3, 3])
        return out

    def dominant_joint(self):
        """Per vertex, the joint node index carrying its largest weight."""
        k = np.argmax(self.skin_weights, axis=1)
        return np.array([self.joints[j] for j in self.skin_joints[np.arange(len(k)), k]])


# ------------------------------------------------------------------ calibration

_WORLD = {"ML": np.array([1.0, 0, 0]), "AP": np.array([0, 0, 1.0]), "S": np.array([0, 1.0, 0])}


def _expected(label, side):
    lat = 1.0 if side == "l" else -1.0
    return {"+A": np.array([0, 0, 1.0]), "-A": np.array([0, 0, -1.0]), "+S": np.array([0, 1.0, 0]),
            "-S": np.array([0, -1.0, 0]), "+X": np.array([1.0, 0, 0]), "-X": np.array([-1.0, 0, 0]),
            "+LAT": np.array([lat, 0, 0]), "-LAT": np.array([-lat, 0, 0])}[label]


def _nearest_axis(v):
    i = int(np.argmax(np.abs(v)))
    sign = "+" if v[i] >= 0 else "-"
    off = math.degrees(math.acos(min(1.0, abs(v[i]))))
    return sign + "XYZ"[i], off


def probe_point(rig, W, bone_node, probe_name):
    """World position of a bone's distal probe under the world matrices W."""
    if probe_name == "tip":
        # extrapolate one bone length beyond the last phalanx
        o = W[bone_node][:3, 3]
        po = W[rig.parent[bone_node]][:3, 3]
        return o + (o - po)
    return W[rig.joint(probe_name)][:3, 3]


def neutral_offsets(rig):
    """The rotation taking each shoulder from the T-pose rest to anatomical
    neutral: a quarter turn about the anteroposterior axis, in the direction
    that lowers the elbow. Measured, like everything else."""
    W = rig.world()
    out = {}
    for s in ("l", "r"):
        b = rig.joint("upperarm_" + s)
        R = W[b][:3, :3]
        o = W[b][:3, 3]
        p = W[rig.joint("lowerarm_" + s)][:3, 3]
        a = R.T @ _WORLD["AP"]
        a /= np.linalg.norm(a)
        best = None
        for sign in (1.0, -1.0):
            Q = q_to_mat(q_axis_angle(a * sign, 10.0))
            d = (o + R @ Q @ R.T @ (p - o)) - p
            c = float(d @ np.array([0, -1.0, 0]) / np.linalg.norm(d))
            if best is None or c > best[0]:
                best = (c, sign)
        out["upperarm_" + s] = {"axis": [round(float(x), 6) for x in a * best[1]], "deg": 90.0,
                                "note": "quarter turn about the anteroposterior axis that lowers the elbow; "
                                        "probe cosine %.3f" % best[0]}
    return out


def _pose_for(rig, neutral, at_rest):
    if at_rest:
        return {}
    return {rig.joint(b): q_axis_angle(v["axis"], v["deg"]) for b, v in neutral.items()}


def calibrate(rig, neutral=None):
    """{joint: {param: entry}} - for single-bone joints the entry is the
    measurement itself; for the finger groups it is {"bones": {bone: entry}}.
    Each entry: the unit axis in the bone's own frame, the nearest labelled
    axis and how far off it is, the probe used, where it was expected to move
    and the cosine between expectation and result."""
    neutral = neutral if neutral is not None else neutral_offsets(rig)
    table = {}
    for jt in vocabulary():
        entry = {}
        for param in jt["params"]:
            axis_kind, probe_kind, expect = MOTIONS[jt["group"]][param]
            at_rest = (jt["group"], param) in MEASURED_AT_REST
            per_bone = {}
            for bone in jt["bones"]:
                per_bone[bone] = _measure(rig, neutral, jt, bone, param, axis_kind, probe_kind, expect, at_rest)
            entry[param] = per_bone[jt["bones"][0]] if len(jt["bones"]) == 1 else {"bones": per_bone}
        table[jt["joint"]] = entry
    return table


def _measure(rig, neutral, jt, bone, param, axis_kind, probe_kind, expect, at_rest, deg=15.0):
    pose = _pose_for(rig, neutral, at_rest)
    W = rig.world(pose)
    b = rig.joint(bone)
    R = W[b][:3, :3]
    o = W[b][:3, 3]
    pd = probe_point(rig, W, b, jt["probes"][bone])
    if axis_kind == "LONG":
        w = pd - o
    else:
        w = _WORLD[axis_kind]
    w = w / np.linalg.norm(w)
    if probe_kind == "anterior":
        p = o + 0.5 * (pd - o) + 0.08 * np.array([0, 0, 1.0])
    else:
        p = pd
    a = R.T @ w
    a /= np.linalg.norm(a)
    v = _expected(expect, jt["side"])
    best = None
    for sign in (1.0, -1.0):
        Q = q_to_mat(q_axis_angle(a * sign, deg))
        d = (o + R @ Q @ R.T @ (p - o)) - p
        c = float(d @ v / np.linalg.norm(d))
        if best is None or c > best[0]:
            best = (c, sign)
    axis = a * best[1]
    nearest, off = _nearest_axis(axis)
    if best[0] < ACCEPT_COSINE:
        raise ValueError("%s.%s on %s: probe %s moved with cosine %.3f to %s" % (
            jt["joint"], param, bone, jt["probes"][bone], best[0], expect))
    return {
        "axis": [round(float(x), 6) for x in axis],
        "nearestLocal": nearest,
        "offAxisDeg": round(off, 1),
        "worldAxis": {"ML": "mediolateral (X)", "AP": "anteroposterior (Z)", "S": "vertical (Y)",
                      "LONG": "the segment's own long axis"}[axis_kind],
        "measuredIn": "rest (T-pose)" if at_rest else "anatomical neutral",
        "probe": ("%s origin" % jt["probes"][bone]) if jt["probes"][bone] != "tip" else "extrapolated fingertip",
        "probeOffset": "midpoint of the segment, 8 cm anterior" if probe_kind == "anterior" else "on the segment",
        "moves": expect.replace("A", "anterior").replace("S", "superior").replace("LAT", "lateral")
                       .replace("X", "the figure's left"),
        "cosine": round(best[0], 3),
    }


# ------------------------------------------------------------------ posing

def pose_from_angles(rig, manifest, angles):
    """The reference implementation of the manifest: {joint: {param: deg}}
    in anatomical degrees -> {node index: local quaternion}. This is what the
    viewer's engine has to reproduce: for each bone,
        q = neutral x Q(axis[flex], flex) x Q(axis[abd], abd) x ... x Q(axis[rot], rot)
    with the parameters in PARAM_ORDER and each Q post-multiplied, so every
    rotation is about the bone's own axis as it then stands."""
    bones = manifest["bones"]
    pose = {}
    for bone, spec in manifest["neutral"].items():
        pose[rig.joint(bone)] = q_axis_angle(spec["axis"], spec["deg"])
    for jt in vocabulary():
        params = angles.get(jt["joint"])
        if not params:
            continue
        for p in params:
            if p not in jt["params"]:
                raise KeyError("%s has no parameter %r" % (jt["joint"], p))
        names = bones[jt["joint"]]
        names = [names] if isinstance(names, str) else names
        for bone in names:
            i = rig.joint(bone)
            q = pose.get(i, q_identity())
            for p in PARAM_ORDER:
                if p not in params or params[p] == 0:
                    continue
                entry = manifest["axes"][jt["joint"]][p]
                axis = entry["bones"][bone]["axis"] if "bones" in entry else entry["axis"]
                q = q_mul(q, q_axis_angle(axis, params[p]))
            pose[i] = q
    return pose


# The calibration pose from the brief. If the render does not show exactly
# this, the table is wrong.
CALIBRATION_POSE = {
    "hipR": {"flex": 90}, "kneeR": {"flex": 90},
    "shoulderL": {"abd": 90}, "elbowL": {"flex": 90},
    "cervical": {"rot": 45},
    "wristR": {"flex": -45},
}
CALIBRATION_PROSE = ("right hip flexed 90, right knee flexed 90, left shoulder abducted 90 with elbow "
                     "flexed 90, neck rotated 45 to the right, right wrist extended 45")


def rest_world(rig):
    """Per joint: rest world position and orientation (x, y, z, w)."""
    W = rig.world()
    out = {}
    for j in rig.joints:
        m = W[j]
        r = m[:3, :3]
        s = np.linalg.norm(r, axis=0)
        out[rig.nodes[j]["name"]] = {"position": [round(float(x), 5) for x in m[:3, 3]],
                                     "quaternion": [round(float(x), 6) for x in mat_to_q(r / s)]}
    return out


def blender_to_gltf(v):
    """Blender Z-up world (x, y, z) -> glTF Y-up (x, z, -y)."""
    v = np.asarray(v, dtype=float)
    return np.stack([v[..., 0], v[..., 2], -v[..., 1]], axis=-1)


def gltf_to_blender(v):
    v = np.asarray(v, dtype=float)
    return np.stack([v[..., 0], -v[..., 2], v[..., 1]], axis=-1)
