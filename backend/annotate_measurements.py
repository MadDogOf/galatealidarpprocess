#!/usr/bin/env python3
"""
annotate_measurements.py — Exploded-view 3D visualisation of measurement slices.

Takes the fitted SMPL-X OBJ and its JSON (which contains slice_z_m — the
exact Z heights used during measurement), cuts the mesh at each anatomical
landmark, displaces each chunk along Z so the body "comes apart" at the right
locations, and saves a multi-coloured OBJ for visual verification.

Usage:
    python annotate_measurements.py output/models/final/your_scan_smplx_measurements.obj
    python annotate_measurements.py <obj> --gap 0.10   # wider gaps
    python annotate_measurements.py <obj> -o out.obj
"""

import json
import sys
import argparse
import numpy as np
import trimesh
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Colour palette — one per chunk, bottom → top
# ─────────────────────────────────────────────────────────────────────────────
PALETTE = [
    [70,  130, 180, 255],   # steel blue      — feet
    [46,  204, 113, 255],   # emerald green   — lower leg
    [241, 196,  15, 255],   # sunflower       — knee / mid-thigh
    [231,  76,  60, 255],   # alizarin red    — upper thigh
    [155,  89, 182, 255],   # amethyst purple — hip
    [52,  152, 219, 255],   # peter river     — waist / high-hip
    [26,  188, 156, 255],   # turquoise       — underbust
    [230, 126,  34, 255],   # carrot orange   — chest
    [236,  64, 122, 255],   # pink            — neck / shoulders
    [100, 149, 237, 255],   # cornflower blue — head
]

DEFAULT_GAP_M = 0.08   # metres of separation per chunk boundary


# ─────────────────────────────────────────────────────────────────────────────
# Slicing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cut_above(mesh: trimesh.Trimesh, z: float) -> trimesh.Trimesh | None:
    """Return the part of *mesh* with Z >= z."""
    try:
        # mesh.slice_plane returns the part of the mesh on the side of the normal
        result = mesh.slice_plane(
            plane_normal=[0.0, 0.0, 1.0],
            plane_origin=[0.0, 0.0, z],
        )
        if result is None or len(result.vertices) == 0:
            return None
        return result
    except Exception:
        return None


def _cut_below(mesh: trimesh.Trimesh, z: float) -> trimesh.Trimesh | None:
    """Return the part of *mesh* with Z <= z."""
    try:
        # To get below, we use a downward normal [0, 0, -1]
        result = mesh.slice_plane(
            plane_normal=[0.0, 0.0, -1.0],
            plane_origin=[0.0, 0.0, z],
        )
        if result is None or len(result.vertices) == 0:
            return None
        return result
    except Exception:
        return None


def extract_chunk(mesh: trimesh.Trimesh,
                  z_low: float | None,
                  z_high: float | None) -> trimesh.Trimesh | None:
    """
    Return the open-shell mesh slice between z_low and z_high.
    Pass None for z_low / z_high to leave that end unbounded.
    """
    m = mesh
    if z_low is not None:
        m = _cut_above(m, z_low)
        if m is None:
            return None
    if z_high is not None:
        m = _cut_below(m, z_high)
        if m is None:
            return None
    if m is None or len(m.vertices) == 0:
        return None
    return m


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Exploded-view body mesh sliced at anatomical landmarks"
    )
    ap.add_argument("obj",  help="Fitted SMPL-X .obj file")
    ap.add_argument("--json", default=None,
                    help="Measurement JSON (default: same stem as OBJ)")
    ap.add_argument("--output", "-o", default=None,
                    help="Output path for the exploded OBJ")
    ap.add_argument("--gap", type=float, default=DEFAULT_GAP_M,
                    help=f"Gap in metres per chunk boundary (default: {DEFAULT_GAP_M})")
    args = ap.parse_args()

    obj_path  = Path(args.obj)
    json_path = Path(args.json) if args.json else obj_path.with_suffix(".json")

    if not obj_path.exists():
        print(f"[error] OBJ not found: {obj_path}", file=sys.stderr)
        sys.exit(1)
    if not json_path.exists():
        print(f"[error] JSON not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    # ── Load ────────────────────────────────────────────────────────────────
    print(f"Loading model     : {obj_path}")
    mesh = trimesh.load(obj_path, process=False)
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(list(mesh.geometry.values()))

    print(f"Loading measurements: {json_path}")
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    slice_z: dict = data.get("slice_z_m", {})
    if not slice_z:
        print("[error] JSON has no 'slice_z_m' block.", file=sys.stderr)
        print("        Re-run smplx_measure.py to regenerate the JSON.", file=sys.stderr)
        sys.exit(1)

    # ── Build ordered cut list ───────────────────────────────────────────────
    # Sort cuts bottom → top (by Z value) and deduplicate near-identical values
    raw_cuts = sorted(slice_z.items(), key=lambda x: x[1])
    cuts: list[tuple[str, float]] = []
    for name, z in raw_cuts:
        if cuts and abs(z - cuts[-1][1]) < 0.002:
            continue   # skip near-duplicate
        cuts.append((name, z))

    cut_labels = [name for name, _ in cuts]
    cut_zs     = [z    for _, z    in cuts]

    print(f"\nCut planes ({len(cuts)} total, Z in metres):")
    for name, z in cuts:
        print(f"  {name:12s}  z = {z:.4f} m")

    # ── Define chunk boundaries ──────────────────────────────────────────────
    # N cuts produce N+1 chunks: (-∞, z0), (z0, z1), …, (z_{N-1}, +∞)
    n = len(cut_zs)
    bounds: list[tuple[float | None, float | None, str]] = []
    bounds.append((None, cut_zs[0], f"below {cut_labels[0]}"))
    for i in range(n - 1):
        label = f"{cut_labels[i]} → {cut_labels[i+1]}"
        bounds.append((cut_zs[i], cut_zs[i + 1], label))
    bounds.append((cut_zs[-1], None, f"above {cut_labels[-1]}"))

    # Centre index — this chunk gets zero offset; others displace from it
    centre_idx = len(bounds) // 2

    # ── Slice, colour, displace ──────────────────────────────────────────────
    print(f"\nSlicing into {len(bounds)} chunks (gap = {args.gap} m each)…")
    pieces: list[trimesh.Trimesh] = []

    for i, (z_lo, z_hi, label) in enumerate(bounds):
        chunk = extract_chunk(mesh, z_lo, z_hi)
        if chunk is None or len(chunk.vertices) < 3:
            print(f"  chunk {i:2d}  [{label}]  → empty, skipped")
            continue

        # Z displacement: proportional distance from centre chunk
        offset_z = (i - centre_idx) * args.gap
        chunk.apply_translation([0.0, 0.0, offset_z])

        # Flat colour for this chunk
        colour = PALETTE[i % len(PALETTE)]
        chunk.visual = trimesh.visual.ColorVisuals(
            mesh=chunk,
            face_colors=np.tile(colour, (len(chunk.faces), 1)).astype(np.uint8),
        )

        pieces.append(chunk)
        lo_str = f"{z_lo:.3f}" if z_lo is not None else "-∞"
        hi_str = f"{z_hi:.3f}" if z_hi is not None else "+∞"
        print(f"  chunk {i:2d}  z=[{lo_str}, {hi_str}]  "
              f"offset={offset_z:+.3f} m  "
              f"({len(chunk.vertices):,} verts)  [{label}]")

    if not pieces:
        print("[error] No chunks produced — check that the OBJ and JSON are from the same run.",
              file=sys.stderr)
        sys.exit(1)

    # ── Combine and export ───────────────────────────────────────────────────
    print("\nCombining chunks…")
    final = trimesh.util.concatenate(pieces)

    out_path = (Path(args.output) if args.output
                else obj_path.with_name(obj_path.stem + "_exploded.obj"))

    print(f"Saving to: {out_path}")
    final.export(str(out_path))

    print(f"\nSuccessfully created: {out_path.name}")
    print(f"  {len(bounds)} segments  ·  {n} cuts  ·  gap = {args.gap} m per boundary")
    print("Open in any 3D viewer — each coloured band is one measurement zone.")


if __name__ == "__main__":
    main()
