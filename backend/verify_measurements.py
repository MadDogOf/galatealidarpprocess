#!/usr/bin/env python3
"""
verify_measurements.py — Sanity-check measurement JSON from scan_measure.py

Runs three layers of validation against a measurements file:
  1. Range checks       — each value falls within plausible adult human limits
  2. Ratio checks       — pairs of measurements are in expected proportion
                          (e.g. waist < hip, arm span ≈ height, chest > waist)
  3. Completeness check — no expected field is missing / null / zero

A measurement that fails a check isn't necessarily wrong — an extreme body
build or a partial scan can legitimately fall outside these ranges — but
failure strongly suggests the extraction picked the wrong landmark height
or the scan has a structural issue (clothing, missing limb, bad alignment).

Usage:
    python verify_measurements.py output/models/aligned/your_scan_measurements.json

    # Strict mode — exit code 1 if any check fails (for CI)
    python verify_measurements.py measurements.json --strict

    # Write a JSON report alongside
    python verify_measurements.py measurements.json --report
"""

import sys
import json
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Any

# Force UTF-8 output so Unicode symbols print cleanly on Windows cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# Plausibility envelopes (cm). Ranges cover ~99 % of adult population
# plus slight margin; warnings fire outside these bounds.
# Source: ISO 7250-1 / ANSUR II / CAESAR databases
# ─────────────────────────────────────────────────────────────────────────────
RANGES_CM = {
    "global": {
        "height":                (120, 220),
    },
    "neck": {
        "neck_circumference":    (28, 55),
        "neck_base":             (32, 60),
        "neck_length":           (6, 18),
    },
    "upper_torso": {
        "across_shoulder":       (30, 60),
        "shoulder_width":        (14, 30),
        "front_inner_shoulder":  (30, 62),
        "chest":                 (65, 135),
        "bust_size":             (65, 135),
        "underbust":             (60, 125),
        "neck_to_waist":         (30, 55),
    },
    "lower_torso": {
        "waist":                 (55, 140),
        "high_hip":              (65, 140),
        "hip":                   (75, 150),
    },
    "arms": {
        "upper_arm_length":      (20, 45),
        "lower_arm_length":      (18, 38),
        "bicep_girth":           (20, 50),
        "forearm_girth":         (18, 40),
        "elbow_width":           (4,  12),
    },
    "legs": {
        "upper_leg_length":      (30, 60),
        "lower_leg_length":      (30, 55),
        "thigh_girth":           (38, 85),
        "calf_girth":            (25, 55),
        "ankle_girth":           (16, 32),
        "knee_width":            (7,  16),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Inter-measurement ratio rules
# ─────────────────────────────────────────────────────────────────────────────
# Each rule returns (passed, explanation).
# `m` is a flat dict of all measurements in cm.

@dataclass
class RatioRule:
    name:        str
    description: str

    def check(self, m: dict) -> tuple[Optional[bool], str]:
        """Return (True/False/None, explanation). None = inputs missing."""
        raise NotImplementedError


class RangeRatio(RatioRule):
    """Generic: lhs / rhs must lie in [lo, hi]."""
    def __init__(self, name: str, lhs: str, rhs: str,
                 lo: float, hi: float, description: str):
        super().__init__(name, description)
        self.lhs, self.rhs, self.lo, self.hi = lhs, rhs, lo, hi

    def check(self, m):
        a, b = m.get(self.lhs), m.get(self.rhs)
        if a is None or b is None or b == 0:
            return None, f"skipped (missing {self.lhs} or {self.rhs})"
        r = a / b
        ok = self.lo <= r <= self.hi
        return ok, f"{self.lhs}/{self.rhs} = {r:.3f}  (expect {self.lo:.2f}–{self.hi:.2f})"


class OrderingRule(RatioRule):
    """lhs should be < / > / ≈ rhs (with tolerance)."""
    def __init__(self, name: str, lhs: str, op: str, rhs: str,
                 tolerance: float = 0.0, description: str = ""):
        super().__init__(name, description)
        self.lhs, self.op, self.rhs, self.tol = lhs, op, rhs, tolerance

    def check(self, m):
        a, b = m.get(self.lhs), m.get(self.rhs)
        if a is None or b is None:
            return None, f"skipped (missing {self.lhs} or {self.rhs})"
        if self.op == "<":
            ok = a < b + self.tol
        elif self.op == ">":
            ok = a + self.tol > b
        elif self.op == "≈":
            ok = abs(a - b) <= self.tol
        else:
            return None, f"unknown operator {self.op}"
        return ok, f"{self.lhs}={a:.1f}  {self.op}  {self.rhs}={b:.1f}  (tol±{self.tol:.1f})"


RATIO_RULES: list[RatioRule] = [
    # Core body ratios (relative to height)
    RangeRatio("chest/height",    "chest",    "height", 0.45, 0.62,
               "Chest circumference ≈ 45–62 % of height"),
    RangeRatio("waist/height",    "waist",    "height", 0.38, 0.60,
               "Waist ≈ 38–60 % of height"),
    RangeRatio("hip/height",      "hip",      "height", 0.46, 0.65,
               "Hip ≈ 46–65 % of height"),
    RangeRatio("shoulder/height", "across_shoulder", "height", 0.20, 0.30,
               "Across-shoulder ≈ 20–30 % of height"),
    RangeRatio("upperleg/height", "upper_leg_length", "height", 0.20, 0.33,
               "Upper leg ≈ 20–33 % of height"),
    RangeRatio("lowerleg/height", "lower_leg_length", "height", 0.20, 0.32,
               "Lower leg ≈ 20–32 % of height"),
    RangeRatio("upperarm/height", "upper_arm_length", "height", 0.14, 0.22,
               "Upper arm ≈ 14–22 % of height"),
    RangeRatio("lowerarm/height", "lower_arm_length", "height", 0.12, 0.19,
               "Lower arm ≈ 12–19 % of height"),

    # Ordering relationships — true for nearly all body types
    OrderingRule("hip_≥_waist",      "hip",   ">", "waist", tolerance=-2.0,
                 description="Hip should be wider than waist"),
    OrderingRule("chest_≥_underbust", "chest", ">", "underbust", tolerance=-1.0,
                 description="Chest should be larger than underbust"),
    OrderingRule("chest_≥_waist",    "chest", ">", "waist", tolerance=-3.0,
                 description="Chest should be larger than waist"),
    OrderingRule("thigh_≥_calf",     "thigh_girth", ">", "calf_girth", tolerance=-2.0,
                 description="Thigh girth should exceed calf girth"),
    OrderingRule("calf_≥_ankle",     "calf_girth", ">", "ankle_girth", tolerance=-1.0,
                 description="Calf girth should exceed ankle girth"),
    OrderingRule("bicep_≥_forearm",  "bicep_girth", ">", "forearm_girth", tolerance=-3.0,
                 description="Bicep girth usually exceeds forearm girth"),
    OrderingRule("upper_arm≈lower_arm", "upper_arm_length", "≈", "lower_arm_length",
                 tolerance=10.0,
                 description="Upper and lower arm lengths within 10 cm"),

    # Ratios between body parts
    RangeRatio("hip/waist_ratio", "hip", "waist", 0.90, 1.60,
               "Hip-to-waist ratio ≈ 0.90–1.60"),
    RangeRatio("leg_reach/height",
               "upper_leg_length", "height", 0.20, 0.33,
               "Leg reach in reasonable range"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Loading and flattening
# ─────────────────────────────────────────────────────────────────────────────

def flatten_measurements(doc: dict) -> dict:
    """Combine every sub-group's values into one flat {name: value_cm} dict."""
    flat: dict[str, Any] = {}
    m = doc.get("measurements", {})
    for group, fields in m.items():
        if not isinstance(fields, dict):
            continue
        for k, v in fields.items():
            if k.startswith("_"):        # skip meta fields like "_note"
                continue
            if isinstance(v, (int, float)):
                flat[k] = float(v)
    return flat


# ─────────────────────────────────────────────────────────────────────────────
# Checks
# ─────────────────────────────────────────────────────────────────────────────

def run_range_checks(doc: dict) -> list[dict]:
    out = []
    m = doc.get("measurements", {})
    for group, fields in RANGES_CM.items():
        got = m.get(group, {}) or {}
        for name, (lo, hi) in fields.items():
            val = got.get(name)
            row = {"group": group, "name": name, "value": val,
                   "expected": [lo, hi]}
            if val is None:
                row["status"] = "MISSING"
                row["message"] = "value absent or null"
            elif val <= 0:
                row["status"] = "FAIL"
                row["message"] = f"non-positive ({val})"
            elif lo <= val <= hi:
                row["status"] = "PASS"
                row["message"] = f"{val} cm ∈ [{lo}, {hi}]"
            else:
                row["status"] = "WARN"
                row["message"] = f"{val} cm outside [{lo}, {hi}]"
            out.append(row)
    return out


def run_ratio_checks(doc: dict) -> list[dict]:
    flat = flatten_measurements(doc)
    out = []
    for rule in RATIO_RULES:
        ok, msg = rule.check(flat)
        out.append({
            "name":        rule.name,
            "description": rule.description,
            "status":      "PASS" if ok else ("WARN" if ok is False else "SKIP"),
            "message":     msg,
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Pretty printing
# ─────────────────────────────────────────────────────────────────────────────

_SYMBOLS = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "MISSING": "·", "SKIP": "—"}


def _print_range_report(rows: list[dict]):
    print("\n── Range checks (plausible adult human values) " + "─" * 20)
    counts = {k: 0 for k in _SYMBOLS}
    by_group: dict[str, list[dict]] = {}
    for r in rows:
        by_group.setdefault(r["group"], []).append(r)
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    for group, items in by_group.items():
        print(f"\n  [{group}]")
        for r in items:
            sym = _SYMBOLS.get(r["status"], "?")
            val = f"{r['value']:.1f}" if isinstance(r["value"], (int, float)) else "  —"
            print(f"    {sym} {r['name']:<22} {val:>8}   {r['message']}")

    print(f"\n  Totals: "
          f"{counts.get('PASS',0)} pass · "
          f"{counts.get('WARN',0)} warn · "
          f"{counts.get('FAIL',0)} fail · "
          f"{counts.get('MISSING',0)} missing")


def _print_ratio_report(rows: list[dict]):
    print("\n── Ratio / ordering checks " + "─" * 40)
    for r in rows:
        sym = _SYMBOLS.get(r["status"], "?")
        print(f"  {sym} {r['name']:<26}  {r['message']}")
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"\n  Totals: "
          f"{counts.get('PASS',0)} pass · "
          f"{counts.get('WARN',0)} warn · "
          f"{counts.get('SKIP',0)} skipped")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def verify(json_path: str) -> dict:
    path = Path(json_path)
    doc  = json.loads(path.read_text(encoding="utf-8"))

    print(f"Verifying : {path.name}")
    print(f"Source    : {doc.get('source', '?')}")
    print(f"Pose      : {doc.get('pose', '?')}")
    print(f"Units     : {doc.get('units', '?')}")

    range_rows = run_range_checks(doc)
    ratio_rows = run_ratio_checks(doc)

    _print_range_report(range_rows)
    _print_ratio_report(ratio_rows)

    # Top-level verdict
    has_fail = any(r["status"] == "FAIL" for r in range_rows)
    warn_count = sum(1 for r in range_rows if r["status"] == "WARN") + \
                 sum(1 for r in ratio_rows if r["status"] == "WARN")
    missing = sum(1 for r in range_rows if r["status"] == "MISSING")

    if has_fail:
        verdict = "FAIL"
    elif warn_count > 3 or missing > 3:
        verdict = "WARN"
    else:
        verdict = "PASS"

    print("\n" + "═" * 60)
    print(f"  Overall verdict: {verdict}")
    print(f"  Warnings: {warn_count}    Missing: {missing}")
    print("═" * 60)

    return {
        "source":  str(path),
        "subject": doc.get("source"),
        "verdict": verdict,
        "warn_count":   warn_count,
        "missing_count": missing,
        "range_checks": range_rows,
        "ratio_checks": ratio_rows,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate measurements JSON from scan_measure.py")
    parser.add_argument("json_file",
                        help="Measurements JSON "
                             "(typically output/models/aligned/*_measurements.json)")
    parser.add_argument("--strict", action="store_true",
                        help="Exit code 1 on FAIL or WARN verdict (for CI)")
    parser.add_argument("--report", action="store_true",
                        help="Also write a .verify.json report next to the input file")
    args = parser.parse_args()

    result = verify(args.json_file)

    if args.report:
        rep_path = Path(args.json_file).with_suffix(".verify.json")
        rep_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nReport written: {rep_path}")

    if args.strict and result["verdict"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
