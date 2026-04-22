#!/usr/bin/env bash
# clean_outputs.sh — Remove every generated artefact from output/ and reset
# the folder tree to a clean, empty state.
#
# Does NOT touch input/, source code, SMPL-X weights, or any git state.
#
# Usage:
#   bash clean_outputs.sh           # interactive confirmation
#   bash clean_outputs.sh --yes     # skip confirmation
#   bash clean_outputs.sh --dry-run # list what would be deleted, delete nothing

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$ROOT/output"

# ── Parse flags ──────────────────────────────────────────────────────────────
YES=0
DRY=0
for a in "$@"; do
  case "$a" in
    --yes|-y) YES=1 ;;
    --dry-run|-n) DRY=1 ;;
    *) echo "Unknown flag: $a"; exit 1 ;;
  esac
done

if [ ! -d "$OUTPUT_DIR" ]; then
  echo "No output/ directory found at $OUTPUT_DIR — nothing to clean."
  exit 0
fi

# ── Show what will go ────────────────────────────────────────────────────────
echo
echo "The following files under output/ will be removed:"
echo "────────────────────────────────────────────────────"
FILES=$(find "$OUTPUT_DIR" -type f 2>/dev/null || true)
if [ -z "$FILES" ]; then
  echo "  (already empty)"
  exit 0
fi
echo "$FILES" | sed "s|$ROOT/||" | sort

COUNT=$(echo "$FILES" | grep -c . || echo 0)
SIZE=$(du -sh "$OUTPUT_DIR" 2>/dev/null | cut -f1 || echo "?")
echo "────────────────────────────────────────────────────"
echo "Total: $COUNT file(s), $SIZE"
echo

# ── Dry-run stop ─────────────────────────────────────────────────────────────
if [ $DRY -eq 1 ]; then
  echo "--dry-run: nothing removed."
  exit 0
fi

# ── Confirmation ─────────────────────────────────────────────────────────────
if [ $YES -ne 1 ]; then
  printf "Delete all of the above? [y/N] "
  read -r ANS
  case "$ANS" in
    y|Y|yes|YES) ;;
    *) echo "Aborted."; exit 0 ;;
  esac
fi

# ── Wipe and rebuild the canonical tree ──────────────────────────────────────
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/images"
mkdir -p "$OUTPUT_DIR/models/aligned"
mkdir -p "$OUTPUT_DIR/models/final"

echo
echo "✓ output/ cleaned."
echo "  Rebuilt canonical layout:"
echo "    output/"
echo "    ├── images/"
echo "    └── models/"
echo "        ├── aligned/"
echo "        └── final/"
