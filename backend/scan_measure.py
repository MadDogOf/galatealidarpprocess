#!/usr/bin/env python3
"""
scan_measure.py — Body measurement extractor from a LiDAR body scan OBJ

Derives tailor-style measurements matching metahuman_dimensions.json (body, no face).
No SMPL-X model files required — works directly on the mesh geometry.

Works best with an upright A-pose or T-pose scan.
T-pose (arms extended horizontally) gives the most accurate arm measurements.

Requirements:
    pip install trimesh numpy scipy shapely

Usage:
    python scan_measure.py output/models/aligned/your_scan_aligned.obj
        → saves to output/models/aligned/your_scan_measurements.json

    python scan_measure.py <obj> --output custom/path.json   # custom output
    python scan_measure.py <obj> --stdout                    # print to stdout
    python scan_measure.py <obj> --pose t                    # force T-pose mode
"""

import sys
import json
import argparse
import numpy as np
import trimesh
import trimesh.path
from pathlib import Path
from typing import Optional

# Force UTF-8 output so Unicode symbols print cleanly on Windows cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# Anthropometric landmark proportions (fraction of total height, floor = 0)
# Based on ISO 7250-1 / ANSUR II standards
# ─────────────────────────────────────────────────────────────────────────────
PROPORTIONS = {
    "top_head":   1.000,
    "chin":       0.871,
    "neck_mid":   0.847,
    "neck_base":  0.818,
    "shoulder":   0.808,
    "armpit":     0.787,
    "chest":      0.749,
    "underbust":  0.702,
    "waist":      0.618,
    "high_hip":   0.566,
    "hip":        0.515,
    "crotch":     0.466,
    "mid_thigh":  0.388,
    "knee":       0.265,
    "mid_calf":   0.177,
    "ankle":      0.073,
}

# Upper arm = 54%, lower arm = 46% of (shoulder-to-wrist) horizontal span
# Derived from ISO 7250: upper arm ≈ 33 cm, lower arm ≈ 28 cm for 176 cm person
ARM_UPPER_FRAC = 0.541
ARM_LOWER_FRAC = 0.459

# Arm measurements as fractions of total body height (fallback for non-T-pose)
ARM_HEIGHT_RATIOS = {
    "upper_arm_length": 0.188,
    "lower_arm_length": 0.159,
    "bicep_girth":      0.172,
    "forearm_girth":    0.148,
    "elbow_width":      0.042,
}


# ─────────────────────────────────────────────────────────────────────────────
# Mesh loading and orientation
# ─────────────────────────────────────────────────────────────────────────────

def load_and_orient(obj_path: str) -> trimesh.Trimesh:
    """Load OBJ, merge into a single mesh, orient Z-up with floor at z=0."""
    raw = trimesh.load(obj_path, force="mesh", process=True)
    if isinstance(raw, trimesh.Scene):
        raw = trimesh.util.concatenate(list(raw.geometry.values()))
    mesh: trimesh.Trimesh = raw

    # Auto-detect up axis: the axis with the greatest extent is the height axis
    up_axis = int(np.argmax(mesh.extents))
    if up_axis == 1:   # Y-up (Blender/most OBJ exporters) → rotate to Z-up
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    elif up_axis == 0:  # X-up (unusual) → rotate to Z-up
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))

    # Centre on XY plane; floor at z = 0
    b = mesh.bounds
    mesh.apply_translation([
        -(b[0][0] + b[1][0]) / 2,
        -(b[0][1] + b[1][1]) / 2,
        -b[0][2],
    ])
    return mesh


def auto_scale_to_cm(raw_height: float) -> float:
    """Return scale factor to convert raw mesh units → centimetres."""
    if raw_height > 500:  return 0.1    # millimetres  → cm
    if raw_height > 50:   return 1.0    # centimetres  (already cm)
    if raw_height > 1.0:  return 100.0  # metres       → cm
    print(f"[warn] Unusual raw height {raw_height:.4f}; assuming metres.", file=sys.stderr)
    return 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Pose detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_pose(mesh: trimesh.Trimesh) -> str:
    """
    Classify scan pose by comparing mesh width at shoulder vs hip height.
    T-pose:  arms fully horizontal → width at shoulders >> width at hips
    A-pose:  arms slightly out     → moderate ratio
    Neutral: arms at sides         → width similar at shoulder and hip
    """
    total_h = mesh.bounds[1][2]
    w_sh = _width_at(mesh, PROPORTIONS["shoulder"] * total_h)
    w_hp = _width_at(mesh, PROPORTIONS["hip"]      * total_h)
    if w_sh is None or w_hp is None or w_hp == 0:
        return "n"
    ratio = w_sh / w_hp
    if ratio > 1.8:  return "t"
    if ratio > 1.3:  return "a"
    return "n"


# ─────────────────────────────────────────────────────────────────────────────
# Low-level mesh query helpers
# ─────────────────────────────────────────────────────────────────────────────

def _section_z(mesh: trimesh.Trimesh, z: float) -> Optional[trimesh.path.Path2D]:
    """Horizontal cross-section (normal = Z) at height z. Returns None on failure."""
    try:
        s = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if s is None or len(s.entities) == 0:
            return None
        path2d, _ = s.to_planar()
        return path2d
    except Exception:
        return None


def _section_x(mesh: trimesh.Trimesh, x: float) -> Optional[trimesh.path.Path2D]:
    """Vertical cross-section (normal = X) at position x. Used for arm cuts in T-pose."""
    try:
        s = mesh.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
        if s is None or len(s.entities) == 0:
            return None
        path2d, _ = s.to_planar()
        return path2d
    except Exception:
        return None


def _contour_lengths(path2d: trimesh.path.Path2D) -> list:
    """
    Return the arc length of every closed contour in a Path2D.
    Uses shapely polygons when available; falls back to entity vertices.
    """
    lengths = []
    try:
        polys = path2d.polygons_closed
        if polys:
            for poly in polys:
                coords = np.array(poly.exterior.coords)
                diffs = np.diff(coords, axis=0)
                lengths.append(float(np.linalg.norm(diffs, axis=1).sum()))
            return lengths
    except Exception:
        pass

    # Fallback: iterate entities directly
    try:
        for entity in path2d.entities:
            pts = path2d.vertices[entity.points]
            diffs = np.diff(pts, axis=0)
            length = float(np.linalg.norm(diffs, axis=1).sum())
            length += float(np.linalg.norm(pts[-1] - pts[0]))  # close loop
            lengths.append(length)
    except Exception:
        lengths = [float(path2d.length)]
    return lengths


def _largest_contour(path2d: Optional[trimesh.path.Path2D]) -> Optional[float]:
    """Length of the single largest closed contour (best for single-body cross-sections)."""
    if path2d is None:
        return None
    lens = _contour_lengths(path2d)
    return max(lens) if lens else None


def _central_contour(path2d: Optional[trimesh.path.Path2D]) -> Optional[float]:
    """
    Length of the contour whose centroid is closest to x=0.
    Used at shoulder height in T-pose to isolate torso from arm contours.
    """
    if path2d is None:
        return None
    try:
        polys = path2d.polygons_closed
        if polys and len(polys) > 1:
            centroids_x = [np.array(p.exterior.coords)[:, 0].mean() for p in polys]
            idx = int(np.argmin(np.abs(centroids_x)))
            coords = np.array(polys[idx].exterior.coords)
            diffs = np.diff(coords, axis=0)
            return float(np.linalg.norm(diffs, axis=1).sum())
    except Exception:
        pass
    return _largest_contour(path2d)


def _single_leg_contour(path2d: Optional[trimesh.path.Path2D]) -> Optional[float]:
    """
    At thigh/calf/ankle heights the cross-section shows two contours (two legs).
    Returns circumference of the larger one (one leg).
    If only one contour (legs touching), returns half the total as an estimate.
    """
    if path2d is None:
        return None
    lens = sorted(_contour_lengths(path2d), reverse=True)
    if not lens:
        return None
    if len(lens) == 1:
        return lens[0] / 2.0  # legs touching: halve total
    return lens[0]


def _width_at(mesh: trimesh.Trimesh, z: float, band: float = 0.015) -> Optional[float]:
    """X-axis width of all vertices within ±band of height z."""
    v = mesh.vertices
    near = v[(v[:, 2] >= z - band) & (v[:, 2] <= z + band)]
    return float(np.ptp(near[:, 0])) if len(near) >= 2 else None


def _depth_at(mesh: trimesh.Trimesh, z: float, band: float = 0.015) -> Optional[float]:
    """Y-axis (front-to-back) depth within ±band of height z."""
    v = mesh.vertices
    near = v[(v[:, 2] >= z - band) & (v[:, 2] <= z + band)]
    return float(np.ptp(near[:, 1])) if len(near) >= 2 else None


def _torso_x_half(mesh: trimesh.Trimesh, z: float) -> Optional[float]:
    """
    Half-width of the torso at height z, excluding arms.
    Uses the central contour in T-pose; full width / 2 otherwise.
    """
    path2d = _section_z(mesh, z)
    if path2d is None:
        w = _width_at(mesh, z)
        return (w / 2) if w else None
    try:
        polys = path2d.polygons_closed
        if polys and len(polys) > 1:
            centroids_x = [np.array(p.exterior.coords)[:, 0].mean() for p in polys]
            idx = int(np.argmin(np.abs(centroids_x)))
            coords = np.array(polys[idx].exterior.coords)
            return float(np.ptp(coords[:, 0])) / 2.0
    except Exception:
        pass
    w = _width_at(mesh, z)
    return (w / 2) if w else None


def _cm(raw: Optional[float], scale: float) -> Optional[float]:
    """Convert raw mesh units to cm and round."""
    return round(raw * scale, 1) if raw is not None else None


# ─────────────────────────────────────────────────────────────────────────────
# Measurement groups
# ─────────────────────────────────────────────────────────────────────────────

def measure_global(mesh: trimesh.Trimesh, scale: float) -> dict:
    return {
        "height": round(mesh.bounds[1][2] * scale, 1),
    }


def measure_neck(mesh: trimesh.Trimesh, lm: dict, scale: float) -> dict:
    neck_circ = _largest_contour(_section_z(mesh, lm["neck_mid"]))
    base_circ = _largest_contour(_section_z(mesh, lm["neck_base"]))
    return {
        "neck_circumference": _cm(neck_circ, scale),
        "neck_base":          _cm(base_circ, scale),
        "neck_length":        round((lm["chin"] - lm["neck_base"]) * scale, 1),
    }


def measure_upper_torso(mesh: trimesh.Trimesh, lm: dict, scale: float, pose: str) -> dict:
    chest_circ     = _largest_contour(_section_z(mesh, lm["chest"]))
    underbust_circ = _largest_contour(_section_z(mesh, lm["underbust"]))

    if pose == "t":
        torso_half = _torso_x_half(mesh, lm["shoulder"])
        across_sh  = (torso_half * 2) if torso_half else _width_at(mesh, lm["shoulder"])
    else:
        across_sh = _width_at(mesh, lm["shoulder"])

    sh_width_cm   = _cm(across_sh, scale)
    indiv_sh_cm   = round(sh_width_cm / 2, 1) if sh_width_cm else None
    fis_cm        = round(sh_width_cm * 1.05, 1) if sh_width_cm else None  # slight arc

    return {
        "across_shoulder":      sh_width_cm,
        "shoulder_width":       indiv_sh_cm,
        "front_inner_shoulder": fis_cm,
        "chest":                _cm(chest_circ, scale),
        "bust_size":            _cm(chest_circ, scale),  # same as chest on surface scan
        "underbust":            _cm(underbust_circ, scale),
        "neck_to_waist":        round((lm["neck_base"] - lm["waist"]) * scale, 1),
    }


def measure_lower_torso(mesh: trimesh.Trimesh, lm: dict, scale: float) -> dict:
    return {
        "waist":    _cm(_largest_contour(_section_z(mesh, lm["waist"])),    scale),
        "high_hip": _cm(_largest_contour(_section_z(mesh, lm["high_hip"])), scale),
        "hip":      _cm(_largest_contour(_section_z(mesh, lm["hip"])),      scale),
    }


def measure_arms_tpose(mesh: trimesh.Trimesh, lm: dict, scale: float) -> dict:
    """
    Direct arm measurements via vertical (X-plane) cross-sections.
    Only valid for T-pose scans where arms are horizontal.
    """
    z_arm = lm["shoulder"]
    v = mesh.vertices
    near = v[(v[:, 2] >= z_arm - 0.02) & (v[:, 2] <= z_arm + 0.02)]
    if len(near) == 0:
        return _arms_proportional(mesh.bounds[1][2] * scale)

    torso_half = _torso_x_half(mesh, z_arm) or 0.0
    arm_x_end  = float(near[:, 0].max())     # rightmost point at shoulder height
    arm_span   = arm_x_end - torso_half

    if arm_span <= 0:
        return _arms_proportional(mesh.bounds[1][2] * scale)

    upper_raw = arm_span * ARM_UPPER_FRAC
    lower_raw = arm_span * ARM_LOWER_FRAC

    x_bicep   = torso_half + upper_raw * 0.40
    x_elbow   = torso_half + upper_raw
    x_forearm = torso_half + upper_raw + lower_raw * 0.40

    bicep_circ   = _largest_contour(_section_x(mesh, x_bicep))
    forearm_circ = _largest_contour(_section_x(mesh, x_forearm))

    # Elbow width: front-to-back depth at elbow X position
    v_el = v[
        (v[:, 0] >= x_elbow - 0.015) & (v[:, 0] <= x_elbow + 0.015) &
        (v[:, 2] >= z_arm - 0.04)    & (v[:, 2] <= z_arm + 0.04)
    ]
    elbow_width = float(np.ptp(v_el[:, 1])) if len(v_el) >= 2 else None

    return {
        "upper_arm_length": round(upper_raw * scale, 1),
        "lower_arm_length": round(lower_raw * scale, 1),
        "bicep_girth":      _cm(bicep_circ, scale),
        "forearm_girth":    _cm(forearm_circ, scale),
        "elbow_width":      _cm(elbow_width, scale),
    }


def _arms_proportional(total_h_cm: float) -> dict:
    """
    Fallback: estimate arm measurements from body-height ratios (ISO 7250).
    Used when pose is not T-pose and arms cannot be directly sectioned.
    """
    return {
        k: round(total_h_cm * r, 1)
        for k, r in ARM_HEIGHT_RATIOS.items()
    } | {"_note": "estimated from height ratios (non-T-pose scan)"}


def measure_arms(mesh: trimesh.Trimesh, lm: dict, scale: float, pose: str) -> dict:
    if pose == "t":
        return measure_arms_tpose(mesh, lm, scale)
    return _arms_proportional(mesh.bounds[1][2] * scale)


def measure_legs(mesh: trimesh.Trimesh, lm: dict, scale: float) -> dict:
    thigh_circ = _single_leg_contour(_section_z(mesh, lm["mid_thigh"]))
    calf_circ  = _single_leg_contour(_section_z(mesh, lm["mid_calf"]))
    ankle_circ = _single_leg_contour(_section_z(mesh, lm["ankle"]))

    # Knee width: total mesh width at knee height ÷ 2 (two knees side by side)
    knee_w_full = _width_at(mesh, lm["knee"])
    knee_width  = (knee_w_full / 2) if knee_w_full else None

    return {
        "upper_leg_length": round((lm["crotch"] - lm["knee"])   * scale, 1),
        "lower_leg_length": round((lm["knee"]   - lm["ankle"])   * scale, 1),
        "thigh_girth":      _cm(thigh_circ, scale),
        "calf_girth":       _cm(calf_circ,  scale),
        "ankle_girth":      _cm(ankle_circ, scale),
        "knee_width":       _cm(knee_width, scale),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def extract(obj_path: str, pose_override: Optional[str] = None) -> dict:
    print(f"Loading  : {obj_path}")
    mesh  = load_and_orient(obj_path)
    raw_h = float(mesh.bounds[1][2])
    scale = auto_scale_to_cm(raw_h)
    pose  = pose_override or detect_pose(mesh)

    print(f"Height   : {raw_h * scale:.1f} cm")
    print(f"Vertices : {len(mesh.vertices):,}")
    print(f"Pose     : {pose!r} ({'detected' if not pose_override else 'forced'})")
    print("Measuring…")

    # Absolute landmark heights in raw mesh units
    lm = {k: v * raw_h for k, v in PROPORTIONS.items()}

    return {
        "source": Path(obj_path).name,
        "pose":   pose,
        "units":  "cm",
        "measurements": {
            "global":       measure_global(mesh, scale),
            "upper_torso":  measure_upper_torso(mesh, lm, scale, pose),
            "lower_torso":  measure_lower_torso(mesh, lm, scale),
            "neck":         measure_neck(mesh, lm, scale),
            "arms":         measure_arms(mesh, lm, scale, pose),
            "legs":         measure_legs(mesh, lm, scale),
        },
    }


def _default_output_path(obj_path: str) -> Path:
    """
    Default measurements path: output/models/aligned/<stem>_measurements.json
    (lives alongside the aligned OBJ it was derived from).
    Script lives in backend/, so the project root is one level up.
    """
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "output" / "models" / "aligned"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(obj_path).stem
    # Strip a trailing "_aligned" so the measurements file stays tidy
    if stem.endswith("_aligned"):
        stem = stem[: -len("_aligned")]
    return out_dir / f"{stem}_measurements.json"


def main():
    parser = argparse.ArgumentParser(
        description="Extract body measurements from a LiDAR body scan OBJ file"
    )
    parser.add_argument("obj", help="Path to body scan .obj file "
                                    "(typically output/models/aligned/*_aligned.obj)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output JSON path "
                             "(default: output/models/aligned/<stem>_measurements.json)")
    parser.add_argument("--pose", "-p", choices=["t", "a", "n"], default=None,
                        help="Pose override: t=T-pose  a=A-pose  n=neutral/standing")
    parser.add_argument("--stdout", action="store_true",
                        help="Print JSON to stdout instead of writing a file")
    args = parser.parse_args()

    result   = extract(args.obj, args.pose)
    out_json = json.dumps(result, indent=2)

    if args.stdout:
        print(out_json)
        return

    dst = Path(args.output) if args.output else _default_output_path(args.obj)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out_json, encoding="utf-8")
    print(f"Saved to : {dst}")


if __name__ == "__main__":
    main()
