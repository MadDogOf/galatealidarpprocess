#!/usr/bin/env python3
"""
runfor3dmodel.py — End-to-end body-scan → tailor-measurements pipeline.

Runs three stages back-to-back on a single input OBJ:

    1. backend/align_scan.py          → orient the raw scan upright (Z-up, face −Y)
    2. backend/smplx_measure.py       → fit SMPL-X and extract 25 measurements
    3. backend/verify_measurements.py → sanity-check the output

Usage:
    python runfor3dmodel.py                              # uses input/models/your_scan.obj
    python runfor3dmodel.py path/to/custom_scan.obj

    # Flags passed through to SMPL-X fitter
    python runfor3dmodel.py --gender male                # skip auto-detect
    python runfor3dmodel.py --iters 600                  # longer fit, tighter Chamfer
    python runfor3dmodel.py --fast                       # --iters 200 --no-pose (≈ 25 s)
    python runfor3dmodel.py --device cuda                # GPU if available

    # Skip stages
    python runfor3dmodel.py --skip-align                 # scan is already aligned
    python runfor3dmodel.py --skip-verify                # don't run sanity checks

    # Clean first, then run
    python runfor3dmodel.py --clean
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent
BACKEND     = ROOT / "backend"
INPUT_DIR   = ROOT / "input"  / "models"
OUT_ALIGN   = ROOT / "output" / "models" / "aligned"
OUT_FINAL   = ROOT / "output" / "models" / "final"
DEFAULT_IN  = INPUT_DIR / "your_scan.obj"


# ─────────────────────────────────────────────────────────────────────────────
# Pretty console helpers (ASCII-only to survive Windows cp1252)
# ─────────────────────────────────────────────────────────────────────────────
def banner(stage: int, total: int, title: str) -> None:
    print()
    print("=" * 72)
    print(f"  Step {stage}/{total}  |  {title}")
    print("=" * 72)


def run_stage(cmd: list[str], stage_name: str) -> None:
    """Run a subprocess stage, abort the pipeline on non-zero exit."""
    t0 = time.time()
    result = subprocess.run(cmd)
    dt = time.time() - t0
    if result.returncode != 0:
        print(f"\n[FATAL] {stage_name} failed (exit {result.returncode}). "
              f"Pipeline aborted.", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"[ok] {stage_name} finished in {dt:.1f}s")


# ─────────────────────────────────────────────────────────────────────────────
# Path derivations — match the conventions used by each backend script
# ─────────────────────────────────────────────────────────────────────────────
def expected_aligned_path(scan: Path) -> Path:
    """align_scan.py writes to output/models/aligned/<stem>_aligned.obj"""
    return OUT_ALIGN / f"{scan.stem}_aligned.obj"


def expected_measurements_path(aligned: Path) -> Path:
    """smplx_measure.py strips trailing '_aligned' and writes ..._smplx_measurements.json"""
    stem = aligned.stem
    if stem.endswith("_aligned"):
        stem = stem[: -len("_aligned")]
    return OUT_FINAL / f"{stem}_smplx_measurements.json"


# ─────────────────────────────────────────────────────────────────────────────
# Optional cleanup
# ─────────────────────────────────────────────────────────────────────────────
def clean_outputs() -> None:
    """Wipe output/ and rebuild the canonical tree. Matches clean_outputs.ps1."""
    import shutil
    out = ROOT / "output"
    if out.exists():
        print(f"Cleaning: {out}")
        shutil.rmtree(out)
    for sub in ("images", "models/aligned", "models/final"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    print("[ok] output/ wiped and rebuilt")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(
        description="Full body-scan -> tailor-measurements pipeline "
                    "(align + SMPL-X fit + verify)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="If <scan> is omitted, uses input/models/your_scan.obj.",
    )
    p.add_argument("scan", nargs="?", default=None,
                   help="Input body scan OBJ path")

    # Forwarded to smplx_measure.py
    p.add_argument("--gender", choices=["auto", "male", "female", "neutral"],
                   default="auto", help="SMPL-X gender model (default: auto)")
    p.add_argument("--iters", type=int, default=400,
                   help="SMPL-X fit iterations (default: 400)")
    p.add_argument("--fast", action="store_true",
                   help="Shape-only fit, ~25 s total")
    p.add_argument("--no-pose", action="store_true",
                   help="Skip body-pose optimisation (faster, less accurate)")
    p.add_argument("--device", default="cpu",
                   help="Torch device: cpu or cuda (default: cpu)")
    p.add_argument("--no-save-obj", action="store_true",
                   help="Don't write the fitted SMPL-X OBJ, only the JSON")

    # Pipeline controls
    p.add_argument("--skip-align",  action="store_true",
                   help="Skip alignment (use when scan is already aligned)")
    p.add_argument("--skip-verify", action="store_true",
                   help="Skip measurement validation")
    p.add_argument("--skip-annotate", action="store_true",
                   help="Skip 3D annotation visualization")
    p.add_argument("--clean", action="store_true",
                   help="Wipe output/ before running")
    p.add_argument("--ui", action="store_true", default=True,
                   help="Start the web dashboard automatically (default: True)")
    p.add_argument("--no-ui", action="store_false", dest="ui",
                   help="Disable automatic dashboard launch")
    args = p.parse_args()

    # Auto-start UI if requested
    if args.ui:
        print("\n" + "=" * 72)
        print("  GALATEA VISION: STARTING WEB DASHBOARD")
        print("=" * 72)
        try:
            import webbrowser
            # Start api_server.py in a separate process
            subprocess.Popen([sys.executable, str(ROOT / "api_server.py")])
            time.sleep(2)
            webbrowser.open("http://127.0.0.1:5001")
            print("\n[ok] Dashboard launched at http://127.0.0.1:5001")
            print("[info] Keep this terminal open to maintain the backend server.")
            # If ONLY --ui was requested, we might want to stay here
            if not args.scan:
                while True: time.sleep(1)
        except Exception as e:
            print(f"[ERROR] Could not start UI: {e}")

    # Optional clean
    if args.clean:
        clean_outputs()

    # Resolve input path
    scan = Path(args.scan).resolve() if args.scan else DEFAULT_IN
    if not scan.exists():
        print(f"[FATAL] Input scan not found: {scan}", file=sys.stderr)
        print(f"        Default location is {DEFAULT_IN}", file=sys.stderr)
        sys.exit(1)

    # Count stages for progress display
    total_stages = 1  # SMPL-X stage is always run
    if not args.skip_align:  total_stages += 1
    if not args.skip_verify: total_stages += 1
    if not args.skip_annotate and not args.no_save_obj: total_stages += 1
    stage = 0

    print()
    print("#" * 72)
    print("#  Body scan -> tailor measurements pipeline")
    print(f"#  Input     : {scan}")
    print(f"#  Backend   : {BACKEND}")
    print(f"#  Gender    : {args.gender}")
    print(f"#  Iters     : {args.iters}{'  (fast)' if args.fast else ''}")
    print(f"#  Device    : {args.device}")
    print("#" * 72)

    # ── Stage 1: alignment ────────────────────────────────────────────────────
    if args.skip_align:
        aligned_obj = scan
        print("\n[skip] alignment stage skipped (--skip-align)")
    else:
        stage += 1
        banner(stage, total_stages, "Aligning scan (upright, face -Y, Z-up)")
        run_stage(
            [sys.executable, str(BACKEND / "align_scan.py"), str(scan)],
            "Alignment",
        )
        aligned_obj = expected_aligned_path(scan)
        if not aligned_obj.exists():
            print(f"[FATAL] expected aligned OBJ not found: {aligned_obj}",
                  file=sys.stderr)
            sys.exit(1)

    # ── Stage 2: SMPL-X fit + measurement extraction ─────────────────────────
    stage += 1
    banner(stage, total_stages, "Fitting SMPL-X + extracting measurements")

    cmd = [sys.executable, str(BACKEND / "smplx_measure.py"), str(aligned_obj),
           "--gender", args.gender, "--iters", str(args.iters),
           "--device", args.device]
    if args.fast:        cmd.append("--fast")
    if args.no_pose:     cmd.append("--no-pose")
    if args.no_save_obj: cmd.append("--no-save-obj")

    run_stage(cmd, "SMPL-X measurement")
    measurements_json = expected_measurements_path(aligned_obj)

    # ── Stage 3: validation ──────────────────────────────────────────────────
    if args.skip_verify:
        print("\n[skip] verification stage skipped (--skip-verify)")
    else:
        stage += 1
        banner(stage, total_stages, "Validating measurements")
        run_stage(
            [sys.executable, str(BACKEND / "verify_measurements.py"),
             str(measurements_json)],
            "Verification",
        )

    # ── Stage 4: annotation ──────────────────────────────────────────────────
    if args.skip_annotate or args.no_save_obj:
        if args.no_save_obj:
            print("\n[skip] annotation skipped (no fitted OBJ saved)")
        else:
            print("\n[skip] annotation stage skipped (--skip-annotate)")
    else:
        stage += 1
        banner(stage, total_stages, "Generating 3D annotation visualization")
        fitted_obj = measurements_json.with_suffix('.obj')
        if fitted_obj.exists():
            run_stage(
                [sys.executable, str(BACKEND / "annotate_measurements.py"),
                 str(fitted_obj)],
                "Annotation",
            )
        else:
            print(f"[WARN] Fitted OBJ not found for annotation: {fitted_obj}")

    # ── Done — report artefacts ──────────────────────────────────────────────
    print()
    print("#" * 72)
    print("#  Pipeline complete")
    print("#" * 72)
    print(f"  Aligned OBJ      : {aligned_obj}")
    print(f"  Fitted SMPL-X OBJ: {measurements_json.with_suffix('.obj')}")
    print(f"  Measurements JSON: {measurements_json}")
    if not args.skip_annotate and not args.no_save_obj:
        print(f"  Exploded OBJ     : {measurements_json.with_name(measurements_json.stem + '_exploded.obj')}")
    print()


if __name__ == "__main__":
    main()
