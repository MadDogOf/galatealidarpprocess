#!/usr/bin/env python3
"""
align_scan.py — Auto-align a LiDAR body scan OBJ to stand upright facing forward

Fixes three common problems from body scanners:
  1. Wrong body axis  (person lying flat → rotates so body stands along Z)
  2. Upside-down      (head at bottom → flips so head is at top)
  3. Wrong facing     (back to camera → rotates 180° so person faces -Y / camera)

Usage:
    python align_scan.py input/models/your_scan.obj
        → saves to output/models/aligned/your_scan_aligned.obj

    python align_scan.py input/models/your_scan.obj custom/path.obj
        → custom output path

    python align_scan.py input/models/your_scan.obj --axis y      # force body axis
    python align_scan.py input/models/your_scan.obj --face +y     # force facing
    python align_scan.py input/models/your_scan.obj --no-facing   # skip facing step
    python align_scan.py input/models/your_scan.obj --debug       # save debug SVGs

Requirements:
    pip install trimesh numpy scipy shapely
"""

import sys
import json
import argparse
import numpy as np
import trimesh
import trimesh.transformations as tf
from pathlib import Path
from typing import Optional, Tuple

# Force UTF-8 output so Unicode symbols (→ ★ ✓) print cleanly on Windows cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 – Load
# ─────────────────────────────────────────────────────────────────────────────

def load_mesh(path: str) -> trimesh.Trimesh:
    raw = trimesh.load(path, force="mesh", process=True)
    if isinstance(raw, trimesh.Scene):
        raw = trimesh.util.concatenate(list(raw.geometry.values()))
    return raw


def _export_obj_clean(mesh: trimesh.Trimesh, dst: Path) -> None:
    """
    Export as OBJ without trimesh's placeholder material.mtl / material_0.png.
    `mesh.export(path)` writes those side-cars automatically for any mesh that
    has a `.visual` attribute — they're a 1×1 blank texture + matching MTL
    stub, useless for our measurement workflow. Here we ask trimesh for the
    raw OBJ string and write it directly.
    """
    obj_text = trimesh.exchange.obj.export_obj(
        mesh,
        include_color=False,
        include_normals=True,
        include_texture=False,
        write_texture=False,
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(obj_text, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 – Find body axis and rotate to Z-up
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Smart body-axis detection
# ─────────────────────────────────────────────────────────────────────────────
# Simply picking the longest bounding-box axis fails when the scan contains
# background geometry (floor, walls, noise) that makes one axis artificially
# long. Example: Z extent = 339 cm, but the actual person is 170 cm along Y —
# the extra 169 cm of Z was ground/floor captured by the scanner.
#
# Strategy: score each axis on three signals:
#   1. Human-height plausibility  — extent should fall in 1.2–2.2 m (or equivalent)
#   2. Aspect ratio               — body is ≈3–6× taller than wide
#   3. PCA on the main component  — principal direction should align with it
# The highest-scoring axis wins.

HUMAN_HEIGHT_RANGE_CM = (120.0, 220.0)   # plausible adult height


def _plausible_height_score(extent: float) -> float:
    """
    1.0 if `extent` (in raw units) corresponds to a plausible human height
    under ANY common unit assumption (m / cm / mm).
    0.0 otherwise. Decays smoothly outside the ideal range.
    """
    for candidate_cm in (extent * 100.0, extent, extent / 10.0):
        lo, hi = HUMAN_HEIGHT_RANGE_CM
        if lo <= candidate_cm <= hi:
            return 1.0
        # Soft scoring near the edges (±30 %)
        if 0.7 * lo <= candidate_cm <= 1.3 * hi:
            if candidate_cm < lo:
                return max(0.0, (candidate_cm - 0.7 * lo) / (lo - 0.7 * lo)) * 0.6
            else:
                return max(0.0, (1.3 * hi - candidate_cm) / (1.3 * hi - hi)) * 0.6
    return 0.0


def _largest_connected_component(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Return the submesh with the most vertices (ignores detached floor/noise)."""
    try:
        parts = mesh.split(only_watertight=False)
        if len(parts) > 1:
            return max(parts, key=lambda m: len(m.vertices))
    except Exception:
        pass
    return mesh


def find_body_axis(mesh: trimesh.Trimesh, verbose: bool = False) -> int:
    """
    Pick the body-height axis (X=0, Y=1, Z=2) using a weighted score.

    Universality
    ------------
    This function has no preference for any particular axis. X, Y, and Z are
    evaluated with identical code paths on the same vertex data. The winner
    emerges from the geometry of the scan alone — a standing scan selects
    Z, a supine scan selects X, a side-lying scan selects Y. Running this
    on a fresh mesh never inherits the result of a previous mesh.

    Steps
    -----
    1. Isolate the largest connected component — excludes floor / stray noise.
    2. Compute robust extents at the 5th–95th percentile — rejects outliers.
    3. Score each axis symmetrically:
         • Height-plausibility (0.55 weight)  → is this length a valid human height?
         • Aspect ratio        (0.25 weight)  → is this axis noticeably longer than the others?
         • PCA agreement       (0.20 weight)  → does the principal direction point here?
    4. Return the axis with the highest total score.
    """
    main = _largest_connected_component(mesh)
    verts = main.vertices

    p5  = np.percentile(verts, 5,  axis=0)
    p95 = np.percentile(verts, 95, axis=0)
    robust_ext = p95 - p5
    full_ext   = main.extents

    # PCA direction
    centred = verts - verts.mean(axis=0)
    cov = np.cov(centred.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    principal = eigvecs[:, np.argmax(eigvals)]
    pca_axis = int(np.argmax(np.abs(principal)))

    scores = np.zeros(3)
    breakdown = []
    for axis in range(3):
        length = robust_ext[axis]
        others = [robust_ext[a] for a in range(3) if a != axis]
        second_longest = max(others) if others else 1e-9

        height_score = _plausible_height_score(length)
        aspect_ratio = length / second_longest if second_longest > 0 else 0.0
        aspect_score = float(np.clip((aspect_ratio - 1.0) / 2.0, 0.0, 1.0))
        pca_score    = 1.0 if axis == pca_axis else 0.0

        total = 0.55 * height_score + 0.25 * aspect_score + 0.20 * pca_score
        scores[axis] = total
        breakdown.append((axis, length, height_score, aspect_ratio,
                          aspect_score, pca_score, total))

    winner = int(np.argmax(scores))

    if verbose:
        print(f"  Full extents     (X,Y,Z): "
              f"[{full_ext[0]:.3f}, {full_ext[1]:.3f}, {full_ext[2]:.3f}]")
        print(f"  Robust 5-95%     (X,Y,Z): "
              f"[{robust_ext[0]:.3f}, {robust_ext[1]:.3f}, {robust_ext[2]:.3f}]")
        print(f"  PCA principal dir: [{principal[0]:+.3f}, {principal[1]:+.3f}, "
              f"{principal[2]:+.3f}]  → axis {'XYZ'[pca_axis]}")
        print(f"\n  Axis scoring:")
        print(f"  {'axis':<5}{'length':>9}{'humanlike':>12}{'aspect':>9}"
              f"{'asp_sc':>9}{'pca':>6}{'total':>9}")
        for axis, length, hs, ar, as_, ps, tot in breakdown:
            star = "  ★" if axis == winner else "   "
            print(f"  {'XYZ'[axis]:<5}{length:>9.3f}{hs:>12.2f}"
                  f"{ar:>9.2f}{as_:>9.2f}{ps:>6.2f}{tot:>9.2f}{star}")
        print(f"\n  → Selected axis: {'XYZ'[winner]}")
    return winner


def rotate_body_axis_to_z(mesh: trimesh.Trimesh, body_axis: int) -> trimesh.Trimesh:
    """Rotate mesh so that body_axis becomes the Z axis."""
    if body_axis == 2:
        return mesh  # already Z-up

    if body_axis == 1:  # Y is up → rotate around X by -90°
        R = tf.rotation_matrix(-np.pi / 2, [1, 0, 0])
    else:                # X is up → rotate around Y by +90°
        R = tf.rotation_matrix(np.pi / 2, [0, 1, 0])

    mesh.apply_transform(R)
    return mesh


def floor_and_center(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Translate mesh: XY centred, floor at z=0."""
    b = mesh.bounds
    mesh.apply_translation([
        -(b[0][0] + b[1][0]) / 2,
        -(b[0][1] + b[1][1]) / 2,
        -b[0][2],
    ])
    return mesh


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 – Detect and fix upside-down
# ─────────────────────────────────────────────────────────────────────────────

def is_upside_down(mesh: trimesh.Trimesh) -> bool:
    """
    For a right-side-up human, the centre of mass is in the LOWER half
    (heavy torso + long legs below mid-height).
    centroid_z / total_height is typically 0.42 – 0.52.

    If the ratio is > 0.55, the mass is concentrated in the upper half
    → the person is upside-down.

    Secondary check: the top region (head) should be NARROWER than the
    bottom region (torso+hips). If the top is wider, person is flipped.
    """
    total_h  = mesh.bounds[1][2]
    centroid_ratio = mesh.centroid[2] / total_h

    # Primary: centre-of-mass heuristic
    if centroid_ratio > 0.56:
        return True
    if centroid_ratio < 0.44:
        return False

    # Secondary: compare cross-sectional width at top 20% vs bottom 20%
    top_z    = total_h * 0.90
    bot_z    = total_h * 0.10
    band     = total_h * 0.08
    verts    = mesh.vertices

    top_verts = verts[(verts[:, 2] >= top_z - band) & (verts[:, 2] <= top_z + band)]
    bot_verts = verts[(verts[:, 2] >= bot_z - band) & (verts[:, 2] <= bot_z + band)]

    if len(top_verts) < 2 or len(bot_verts) < 2:
        return False

    top_width = float(np.ptp(top_verts[:, 0]))
    bot_width = float(np.ptp(bot_verts[:, 0]))

    # Head (top) should be narrower than hip (bottom)
    return top_width > bot_width * 1.3


def flip_upside_down(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Rotate 180° around X axis (flips Z), then re-floor."""
    mesh.apply_transform(tf.rotation_matrix(np.pi, [1, 0, 0]))
    return floor_and_center(mesh)


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 – Detect and fix facing direction
# ─────────────────────────────────────────────────────────────────────────────

def _vertices_in_band(mesh: trimesh.Trimesh, z_frac: float,
                      half_band_frac: float = 0.06) -> np.ndarray:
    total_h = mesh.bounds[1][2]
    z_c  = z_frac * total_h
    band = half_band_frac * total_h
    v    = mesh.vertices
    return v[(v[:, 2] >= z_c - band) & (v[:, 2] <= z_c + band)]


def facing_direction_y(mesh: trimesh.Trimesh) -> float:
    """
    Estimate the Y coordinate the person is facing toward.
    Returns +1.0 if facing +Y, -1.0 if facing -Y.

    Method: combine two depth-asymmetry checks
      A) At chest height (~75%): chest protrudes forward, back is flatter.
         The Y centroid of the chest slice is offset toward the face.
      B) At head height (~87%): nose is the most extreme forward point.
         max Y deviation from centroid > min Y deviation → face is toward max.

    Positive score → face toward +Y, negative → face toward -Y.
    """
    scores = []

    # A — Chest asymmetry
    chest_verts = _vertices_in_band(mesh, 0.75)
    if len(chest_verts) >= 4:
        cy = float(chest_verts[:, 1].mean())
        forward_depth = float(chest_verts[:, 1].max()) - cy
        backward_depth = cy - float(chest_verts[:, 1].min())
        scores.append(forward_depth - backward_depth)

    # B — Head / nose asymmetry
    head_verts = _vertices_in_band(mesh, 0.87, half_band_frac=0.05)
    if len(head_verts) >= 4:
        hy = float(head_verts[:, 1].mean())
        fwd = float(head_verts[:, 1].max()) - hy
        bwd = hy - float(head_verts[:, 1].min())
        scores.append(fwd - bwd)

    # C — Abdomen depth asymmetry (belly protrudes forward)
    belly_verts = _vertices_in_band(mesh, 0.62)
    if len(belly_verts) >= 4:
        by_ = float(belly_verts[:, 1].mean())
        fwd = float(belly_verts[:, 1].max()) - by_
        bwd = by_ - float(belly_verts[:, 1].min())
        scores.append(fwd - bwd)

    if not scores:
        return 1.0  # default: assume facing +Y

    mean_score = float(np.mean(scores))
    return 1.0 if mean_score >= 0 else -1.0


def fix_facing(mesh: trimesh.Trimesh,
               force_face: Optional[str] = None) -> Tuple[trimesh.Trimesh, str]:
    """
    Rotate the mesh so the person faces -Y (standard camera convention: camera at -Y∞).

    force_face: '+y' or '-y' to override auto-detection.
    Returns (corrected_mesh, detected_direction).
    """
    if force_face == "-y":
        return mesh, "forced -Y (no change)"
    if force_face == "+y":
        # User says person currently faces +Y → rotate 180° around Z so they face -Y
        mesh.apply_transform(tf.rotation_matrix(np.pi, [0, 0, 1]))
        floor_and_center(mesh)
        return mesh, "forced +Y → rotated to -Y"

    current_face_y = facing_direction_y(mesh)
    if current_face_y > 0:
        # Currently faces +Y → rotate 180° around Z
        mesh.apply_transform(tf.rotation_matrix(np.pi, [0, 0, 1]))
        floor_and_center(mesh)
        direction = "auto-detected +Y → rotated to -Y"
    else:
        direction = "auto-detected -Y (already correct)"

    return mesh, direction


# ─────────────────────────────────────────────────────────────────────────────
# Debug helpers
# ─────────────────────────────────────────────────────────────────────────────

def save_debug_sections(mesh: trimesh.Trimesh, out_dir: Path):
    """Save horizontal cross-section SVGs at key heights for visual inspection."""
    out_dir.mkdir(parents=True, exist_ok=True)
    total_h = mesh.bounds[1][2]
    heights = {
        "head_87pct":    0.87,
        "shoulder_81pct": 0.81,
        "chest_75pct":   0.75,
        "waist_62pct":   0.62,
        "hip_52pct":     0.52,
        "knee_27pct":    0.27,
    }
    for name, frac in heights.items():
        z = frac * total_h
        try:
            section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
            if section and len(section.entities) > 0:
                path2d, _ = section.to_planar()
                svg_path = out_dir / f"{name}.svg"
                path2d.export(str(svg_path))
                print(f"  Debug section: {svg_path.name}")
        except Exception as e:
            print(f"  [warn] Could not export {name}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Main alignment pipeline
# ─────────────────────────────────────────────────────────────────────────────

def align(obj_path: str,
          output_path: Optional[str] = None,
          force_face:  Optional[str] = None,
          force_axis:  Optional[str] = None,
          skip_facing: bool = False,
          debug:       bool = False) -> dict:

    src = Path(obj_path)
    if output_path:
        dst = Path(output_path)
    else:
        # Default output: output/models/aligned/<stem>_aligned.obj
        # Script lives in backend/, so the project root is one level up.
        project_root = Path(__file__).resolve().parent.parent
        default_dir = project_root / "output" / "models" / "aligned"
        default_dir.mkdir(parents=True, exist_ok=True)
        dst = default_dir / (src.stem + "_aligned.obj")

    print(f"\nLoading  : {src}")
    mesh = load_mesh(str(src))
    print(f"Vertices : {len(mesh.vertices):,}   Faces: {len(mesh.faces):,}")
    print(f"Bounds   : {mesh.bounds.tolist()}")

    report = {
        "source":           str(src),
        "output":           str(dst),
        "steps_applied":    [],
    }

    # ── Step 1: body axis → Z ────────────────────────────────────────────────
    print(f"\nDetecting body axis…")
    if force_axis is not None:
        body_axis = {"x": 0, "y": 1, "z": 2}[force_axis.lower()]
        print(f"  Forced by user: {force_axis.upper()}")
    else:
        body_axis = find_body_axis(mesh, verbose=True)
    axis_name = ["X", "Y", "Z"][body_axis]
    print(f"Body axis: {axis_name}")

    if body_axis != 2:
        mesh = rotate_body_axis_to_z(mesh, body_axis)
        msg = f"Rotated body axis from {axis_name} → Z"
        print(f"  ✓ {msg}")
        report["steps_applied"].append(msg)
    else:
        print("  ✓ Body axis already Z — no rotation needed")

    mesh = floor_and_center(mesh)

    # ── Step 2: upside-down check ─────────────────────────────────────────────
    upside = is_upside_down(mesh)
    print(f"\nUpside-down check: {'YES — will flip' if upside else 'No'}")
    centroid_ratio = mesh.centroid[2] / mesh.bounds[1][2]
    print(f"  Centroid Z ratio: {centroid_ratio:.3f}  (healthy range 0.44 – 0.54)")

    if upside:
        mesh = flip_upside_down(mesh)
        msg = "Flipped 180° (was upside-down)"
        print(f"  ✓ {msg}")
        report["steps_applied"].append(msg)

    # ── Step 3: facing direction ───────────────────────────────────────────────
    if not skip_facing:
        print("\nFacing direction check…")
        mesh, face_msg = fix_facing(mesh, force_face)
        print(f"  ✓ {face_msg}")
        if "rotated" in face_msg.lower():
            report["steps_applied"].append(face_msg)
    else:
        print("\nFacing correction: skipped")

    # ── Final stats ───────────────────────────────────────────────────────────
    mesh = floor_and_center(mesh)
    total_h_raw = float(mesh.bounds[1][2])
    # Auto-detect units for reporting
    if total_h_raw > 500:    h_cm = total_h_raw / 10
    elif total_h_raw > 50:   h_cm = total_h_raw
    elif total_h_raw > 1.0:  h_cm = total_h_raw * 100
    else:                    h_cm = total_h_raw * 100

    report["final_height_cm"] = round(h_cm, 1)
    report["final_bounds"]    = mesh.bounds.tolist()
    report["centroid_z_ratio"] = round(mesh.centroid[2] / mesh.bounds[1][2], 3)

    print(f"\nFinal height: {h_cm:.1f} cm")
    print(f"Final bounds: {mesh.bounds.tolist()}")

    # ── Debug sections ────────────────────────────────────────────────────────
    if debug:
        debug_dir = dst.parent / (dst.stem + "_debug")
        print(f"\nSaving debug cross-sections to {debug_dir}/")
        save_debug_sections(mesh, debug_dir)

    # ── Export ────────────────────────────────────────────────────────────────
    print(f"\nExporting: {dst}")
    _export_obj_clean(mesh, dst)
    print(f"  ✓ Saved")

    # Save alignment report alongside the OBJ
    report_path = dst.with_suffix(".align_report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  ✓ Report: {report_path.name}")

    return report


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Auto-align a LiDAR body scan OBJ: upright, right-side-up, facing camera"
    )
    parser.add_argument("input",  help="Input body scan .obj")
    parser.add_argument("output", nargs="?", default=None,
                        help="Output .obj path (default: <input>_aligned.obj)")

    orient = parser.add_argument_group("Orientation overrides")
    orient.add_argument("--axis", choices=["x", "y", "z"], default=None,
                        help="Force the body-height axis (x, y, or z). "
                             "Use if auto-detection picks the wrong one.")
    orient.add_argument("--face", choices=["+y", "-y"], default=None,
                        help="Force facing direction: +y or -y (default: auto-detect)")
    orient.add_argument("--no-facing", action="store_true",
                        help="Skip the facing-direction correction step")
    orient.add_argument("--debug", action="store_true",
                        help="Save cross-section SVGs for visual inspection")

    args = parser.parse_args()

    report = align(
        args.input,
        args.output,
        force_face=args.face,
        force_axis=args.axis,
        skip_facing=args.no_facing,
        debug=args.debug,
    )

    print("\nSteps applied:")
    if report["steps_applied"]:
        for step in report["steps_applied"]:
            print(f"  • {step}")
    else:
        print("  • None — model was already correctly oriented")


if __name__ == "__main__":
    main()
