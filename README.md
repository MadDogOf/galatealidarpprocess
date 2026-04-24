# LiDAR Body Scan → Tailor Measurements

Two Python scripts that turn a raw LiDAR body scan OBJ into a set of
tailor-style body measurements (waist, chest, hip, arm length, etc.) matching
the body section of [metahuman_dimensions.json](metahuman_dimensions.json).

This project also contains a separate image-to-3D pipeline ([run.py](run.py)
plus [backend/](backend/)) that uses SMPL-X to reconstruct a mesh from a
photograph. The two pipelines are independent and share no input or output
folders.

```
 raw_scan.obj                      aligned.obj                     measurements.json
──────────────────   align_scan.py ─────────────────  scan_measure.py ───────────────
 arbitrary axis        → standing upright              → 21 body measurements in cm
 any unit scale        → facing camera (-Y)
 upside-down ok        → floor at z = 0
```

No SMPL-X model weights, no external datasets, no ML training — works
directly on the mesh geometry of a single OBJ file.

---

## 🚀 Quick Start: Installation & Setup

If you are cloning this repository for the first time, follow these steps to ensure the 3D models and dependencies are correctly initialized.

### 1. Git LFS (Large File Storage)
This project uses **Git LFS** to manage large model files (SMPL-X weights in `.npz` format). 

#### **How Git LFS works in this project:**
*   **The `.gitattributes` file:** This file tells Git which extensions (like `*.npz`, `*.pkl`, and `*.zip`) should be handled by LFS rather than standard Git.
*   **Pointers vs. Blobs:** In your local folder, these large files initially appear as tiny "pointer" files (only a few bytes). They contain a unique ID (hash) but no actual model data.
*   **The "Pull" phase:** When you run `git lfs pull`, the LFS client reads those IDs, connects to GitHub's specialized LFS storage, and downloads the actual multi-megabyte "blobs" to replace the pointers.

**Windows Setup:**
1. Download and install from [git-lfs.github.com](https://git-lfs.github.com).
2. Open your terminal (PowerShell or CMD) and run:
   ```powershell
   git lfs install
   git lfs pull
   ```

**Linux Setup:**
1. Install the client: `sudo apt install git-lfs` (or your distro's equivalent).
2. Run:
   ```bash
   git lfs install
   git lfs pull
   ```

### 2. Python Environment & Dependencies
We recommend using a virtual environment to avoid conflicts.

```bash
# Create and activate environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\activate   # Windows

# Install all packages
pip install -r requirements.txt
```

### 3. How to Run
We provide automated scripts to start the full system (Backend API + 3D Dashboard).

*   **Windows:** Run `.\run.bat`
*   **Linux/macOS:** Run `./run.sh` or `python run.py sh sun.sh`

Once running, the dashboard will automatically open in your browser at `http://localhost:5001`.

---

---

## Folder layout

```
antigravity/
├── runfor3dmodel.py               ← one-command pipeline: align + fit + verify
├── run.py                         ← separate image-to-3D pipeline (unchanged)
├── clean_outputs.ps1 / .sh        ← wipe output/ and rebuild canonical tree
├── metahuman_dimensions.json      ← target measurement schema
├── README.md
│
├── backend/                       ← every Python stage lives here
│   ├── align_scan.py              ← stage 1: orient the scan (Z-up, face -Y)
│   ├── smplx_measure.py           ← stage 2: fit SMPL-X, extract measurements
│   ├── verify_measurements.py     ← stage 3: sanity-check the JSON
│   ├── scan_measure.py            ← legacy geometric pipeline (no ML)
│   ├── main.py                    ← used by run.py (image-to-3D)
│   ├── generate_keypoints.py      ← used by run.py
│   ├── debug_landmarks.py
│   └── smplify-x/                 ← upstream SMPLify-X reference code
│
├── smplx_models/
│   └── models/smplx/              ← SMPL-X neutral/male/female .npz weights
│
├── input/
│   ├── images/                    ← photos for run.py (image-to-3D)
│   │   └── sample.jpg
│   └── models/                    ← raw LiDAR OBJ scans for runfor3dmodel.py
│       └── your_scan.obj
│
└── output/
    ├── images/                    ← outputs of run.py
    └── models/
        ├── aligned/               ← after stage 1 of runfor3dmodel.py
        │   ├── your_scan_aligned.obj
        │   └── your_scan_aligned.align_report.json
        └── final/                 ← after stages 2–3
            ├── your_scan_smplx_measurements.json   ← tailor measurements
            └── your_scan_smplx_measurements.obj    ← fitted SMPL-X mesh
```

**Two orchestrators at the root, everything else in `backend/`:**

- [runfor3dmodel.py](runfor3dmodel.py) — end-to-end scan → measurements pipeline (this README's main subject).
- [run.py](run.py) — separate image-to-3D pipeline (photo → SMPL-X mesh via [backend/main.py](backend/main.py)). Not the focus here; shares the SMPL-X weights but nothing else.

Every script writes to its own folder by default — no more mixing photos, SMPL-X
outputs, aligned scans, and measurement JSONs in one directory.

## Quick start

### The Easiest Way — Automated Setup & Dashboard
One command sets up your environment, installs dependencies, starts the backend server, and launches the visual dashboard.

**macOS / Linux:**
```bash
python run.py sh sun.sh
```
*(Alternatively, run `./run.sh` directly)*

**Windows:**
```powershell
.\run.bat
```

### Direct Pipeline — One command does it all
Run the pipeline directly from the CLI. This will automatically open the UI for visualization unless `--no-ui` is passed.

```powershell
python runfor3dmodel.py
# ...uses input\models\your_scan.obj by default
# ...detects gender, aligns, fits SMPL-X, and extracts measurements
# ...starts the API server and opens http://127.0.0.1:5001 for 3D visualization
```

---

## 💎 Galatea Stealth Dashboard

The project now includes a high-fidelity **Luxury Stealth Dashboard** for visual verification of 3D scans and measurements.

### Features
- **Dual 3D Viewports**: Compare your "Aligned Original" scan with the "Morphed SMPL-X" model side-by-side.
- **Anatomical Telemetry**: Real-time display of 21+ tailor measurements (chest, waist, hip, etc.).
- **Interactive Controls**: Drag-and-drop new scans, toggle gender overrides, and trigger processing directly from the browser.
- **Zero-Dependency**: Built with Vanilla JS and Three.js for maximum performance.

### How to use
1. Run `python run.py sh sun.sh` (or `run.bat` on Windows).
2. Once the dashboard opens, drag an `.obj` file into the drop zone.
3. Watch the 3D fitting process in real-time.

---

### Orchestrator CLI flags

```powershell
python runfor3dmodel.py path\to\my_scan.obj      # explicit input path
python runfor3dmodel.py --gender male            # skip gender auto-detect
python runfor3dmodel.py --iters 600              # longer, tighter SMPL-X fit
python runfor3dmodel.py --fast                   # 200 iters, no pose — ~25 s
python runfor3dmodel.py --device cuda            # GPU if available
python runfor3dmodel.py --clean                  # wipe output/ first

python runfor3dmodel.py --skip-align             # scan is already aligned
python runfor3dmodel.py --skip-verify            # don't run sanity checks
python runfor3dmodel.py --no-save-obj            # JSON only, skip fitted mesh
```

### Running the stages manually

If you'd rather call each stage yourself (useful for debugging):

```powershell
# 0. (optional) Clean previous outputs
.\clean_outputs.ps1 -Yes

# 1. Align the raw scan (Z-up, face -Y)
python backend\align_scan.py input\models\your_scan.obj
# → output\models\aligned\your_scan_aligned.obj
```

#### Option A — Fast proportion-based (legacy, geometric)
Slices the mesh at ISO-7250 landmark heights. No model fitting. Runs in
seconds but accuracy depends on the scan matching average proportions.

```powershell
python backend\scan_measure.py      output\models\aligned\your_scan_aligned.obj
python backend\verify_measurements.py output\models\aligned\your_scan_measurements.json
```

#### Option B — SMPL-X fitting (what `runfor3dmodel.py` uses) — recommended
Registers the SMPL-X statistical body model to your scan, then reads
measurements off the fitted model's known topology. An order of magnitude
more accurate on atypical body shapes and imperfect scans.

```powershell
# Gender is auto-detected by default — three short probe fits pick male/female/neutral
python backend\smplx_measure.py output\models\aligned\your_scan_aligned.obj
# → output\models\final\your_scan_smplx_measurements.json     (measurements + betas)
# → output\models\final\your_scan_smplx_measurements.obj      (fitted mesh, Z-up, face -Y — matches aligned scan)

python backend\verify_measurements.py output\models\final\your_scan_smplx_measurements.json
```

Override auto-detect with `--gender male`, `--gender female`, or `--gender neutral`
if you already know the answer and want to save ~45 seconds.

All scripts auto-resolve output paths from the input path — just pass the
input file. Use `--output <path>` to redirect, `--stdout` (scan_measure) to
print to console.

---

## align_scan.py — How the alignment works

The scanner puts the mesh in some arbitrary orientation. Before we can
measure anything we need the person:

1. **Standing up** (body's long axis = +Z)
2. **Right-side up** (head at top)
3. **Facing the camera** (nose toward -Y)

### Step 1 — Detect the body axis

The naive approach — "pick the axis with the largest bounding-box extent"
— fails surprisingly often. Scans frequently include a bit of floor, wall,
or scanning artefact that stretches one axis past the actual person.
Example: a 170 cm subject standing upright might show a Z extent of 339 cm
because the scanner captured the ground reflection below the feet.

Instead we score each of the three cardinal axes (X, Y, Z) on three signals
and pick the winner:

| Signal | Weight | What it measures |
|---|---:|---|
| **Human-height plausibility** | 0.55 | Does this length, converted to cm under any reasonable unit assumption (m / cm / mm), fall in the 120–220 cm range of adult human height? |
| **Aspect ratio** | 0.25 | Is this axis noticeably longer than the other two? A standing human is ~3× taller than wide. |
| **PCA principal direction** | 0.20 | Does the dominant eigenvector of the vertex covariance matrix point along this axis? |

Robustness tricks used:

- **Largest connected component only** — `mesh.split()` is called first, and
  only the biggest chunk of geometry is analysed. This discards detached
  floor bits and noise clusters.
- **Robust extents** — lengths are computed at the 5th–95th vertex
  percentile rather than full min/max, so a handful of outlier vertices
  can't tilt the result.

The algorithm is deterministic, fast (O(n) in vertex count), and has no
tuneable thresholds that need per-scan adjustment.

#### Why this is universal (and not biased toward Y)

A common worry: *"If the previous scan needed Y-axis alignment, will the next
one also get Y forced on it?"* No. The scorer has no memory between runs and
no built-in preference for any particular axis. It examines the geometry of
the scan in front of it and gives each of X, Y, Z the same three tests.
Whichever axis wins, wins. Three concrete examples:

| Scan orientation | X ext | Y ext | Z ext | Winner | Why |
|---|---:|---:|---:|:---:|---|
| Already upright (Z up) | 0.50 m | 0.30 m | 1.70 m | **Z** | Z is the only axis with a plausible human height *and* the best aspect ratio |
| Lying on back (body along X), floor noise on Z | 1.70 m | 0.50 m | 3.39 m | **X** | Z's 3.39 m is clearly not a human height → 0 score. X wins on all three signals |
| Lying on side (body along Y), clean scan | 0.30 m | 1.80 m | 0.55 m | **Y** | Y has the only human-height extent |

The `--axis` flag is only ever needed in pathological cases — e.g. a scan
whose body axis genuinely has an extent outside the 120–220 cm range
because of heavy clipping, or where two axes both land in the human-height
band (a T-pose lying flat, where arm span rivals body length).

#### What the `--verbose` output looks like

```
Detecting body axis…
  Full extents     (X,Y,Z): [0.540, 1.770, 3.390]
  Robust 5-95%     (X,Y,Z): [0.410, 1.680, 0.320]
  PCA principal dir: [-0.020, +0.998, +0.062]  → axis Y

  Axis scoring:
  axis    length   humanlike   aspect   asp_sc   pca    total
  X        0.410        0.00     0.24     0.00   0.00     0.00
  Y        1.680        1.00     4.10     1.00   1.00     1.00    ★
  Z        0.320        0.00     0.19     0.00   0.00     0.00

  → Selected axis: Y
```

Notice how the **full** Z extent (3.39 m) was nonsense but the **robust**
Z extent (0.32 m) correctly reflected the actual body thickness — this is
why the percentile filter matters.

### Step 2 — Rotate that axis to Z

A single rotation matrix (90° around X or Y as needed) then re-centres the
mesh: XY at origin, floor at z = 0.

### Step 3 — Upside-down check

For an upright human, mass is concentrated in the lower half (heavy torso
plus long legs). The Z centroid / height ratio should sit between
**0.42 and 0.54**.

- Ratio > 0.56 → mass is in the upper half → flip 180° around X
- Ratio < 0.44 → not inverted
- In the grey zone → fall back to a width comparison: head-top cross-section
  should be narrower than hip cross-section

### Step 4 — Facing direction

We want the person's nose to point toward -Y (standard camera convention:
camera at -Y infinity looks toward +Y).

Depth-asymmetry votes from three body slices are averaged:

| Slice | Why it's asymmetric |
|---|---|
| Head (87 % height) | Nose protrudes forward of the skull centroid |
| Chest (75 %) | Chest cavity is deeper forward than back is |
| Belly (62 %) | Abdomen bulges forward vs. flatter lumbar back |

At each slice we compute:
```
forward_depth  = max_y − mean_y
backward_depth = mean_y − min_y
score          = forward_depth − backward_depth
```

If the averaged score is positive, the face is currently toward +Y, and we
rotate 180° around Z so it points toward -Y.

### Overrides

Every auto-detection has a manual-override flag:

```bash
python backend\align_scan.py input.obj out.obj --axis y       # force body axis
python backend\align_scan.py input.obj out.obj --face +y      # force facing direction
python backend\align_scan.py input.obj out.obj --no-facing    # skip facing correction
python backend\align_scan.py input.obj out.obj --debug        # export cross-section SVGs
```

Each run also writes a JSON report next to the output (e.g.
`aligned.align_report.json`) listing every transformation applied.

---

## smplx_measure.py — How the SMPL-X fitting works

This script registers the **SMPL-X statistical body model** to your scan
and reads tailor measurements off the fitted model rather than off your
raw mesh. That indirection is what gives it its accuracy advantage.

### What SMPL-X actually is

SMPL-X is a **statistical body model**. Think of it as a function that
produces a 3D human mesh (10 475 vertices, 20 908 triangles) from a small
set of numeric parameters:

```
mesh = SMPLX( β,   θ,   R,    t    )
              │    │    │     │
              │    │    │     └── global translation (3 numbers)
              │    │    └──────── global rotation     (3 axis-angle)
              │    └───────────── pose, 21 joint rotations (63 numbers)
              └──────────────── shape coefficients  (10 numbers)
```

Internally it's a learned linear blend shape + linear blend skinning
model. The important thing is that it's **invertible to measurements**:
once you know `β` and `θ` for a specific body, you can ask where every
anatomical landmark is, because the mesh topology is fixed.

**Why 10 `β`s describe every body shape:** the SMPL-X authors ran PCA on
thousands of 3D scans. The first 10 principal components capture most of
the variance — height/scale, thin↔stocky, tall↔short torso, etc. Fitting
reduces "which body?" to "where in 10-D shape space?".

### The five learned parameter groups

| Param | Dim | Intuition | What it controls |
|---|---:|---|---|
| `betas` | 10 | Shape coefficients | Overall body dimensions: height, torso length, limb thickness, muscle mass |
| `body_pose` | 63 | 21 joint rotations × 3 | Pose: how arms, legs, spine, neck are bent |
| `global_orient` | 3 | Axis-angle | Where the whole body is facing / tilted in world space |
| `transl` | 3 | World XYZ | Where the body's pelvis sits in the world |
| `log_scale` | 1 | `exp(log_scale)` = multiplier | Uniform scaling of the whole mesh — absorbs unit errors and per-individual size |

Roughly 80 numbers in total. The optimiser adjusts all of them simultaneously
to make the fitted mesh best hug the scan.

### What are the betas? Body-shape space explained

`betas` (β) is the 10-number vector that describes **where your body sits in
"body-shape space"**. It's the single most important output of the fit after
the mesh itself.

#### How the shape space was built

The SMPL-X authors 3D-scanned thousands of people, computed the *mean* body,
then ran **Principal Component Analysis (PCA)** on everyone's deviation from
that mean. The first 10 principal components capture roughly 95 % of the
variance in human body shape. Each `β_i` is the coordinate along one of
those components.

```
 your body's vertices  =  mean_body  +  β₀·S₀  +  β₁·S₁  +  …  +  β₉·S₉
                                        ↑       ↑              ↑
                                     blend    blend          blend
                                    shape 0  shape 1        shape 9

 where each Sᵢ is a learned (10 475 × 3) displacement — i.e. one specific
 direction in "how bodies vary" space. β_i is how far along that direction
 your specific body sits.
```

- **All βs = 0** → the statistical mean body (≈ 1.72 m, mean proportions).
- **β₀ ≈ +2** → body scaled toward the "tall/larger" end of the distribution.
- **β₁ ≈ −1.5** → body scaled toward the "slim" end (the slim↔stocky axis).
- **β₃ ≈ +1** → torso-to-leg ratio shifted in one direction, etc.

The exact semantic of each component isn't named — they're data-driven
directions discovered by PCA. β₀ is *usually* roughly overall body size,
β₁ is *usually* bulk, but the mapping isn't fixed.

#### Why 10 numbers is enough

To describe your specific body to a computer pixel-by-pixel, you'd need
**10 475 vertices × 3 coordinates = 31 425 numbers**. PCA compresses that
to **10 numbers** because real human bodies vary along only ~10 independent
axes — different people don't vary in 31 425 independent ways, they vary
along a handful of correlated patterns (people with longer arms tend to
have longer legs, wider shoulders correlate with broader chests, etc.).

That's a **3000× compression with almost no loss**. It's the reason the
fitter is so fast and so stable: the optimiser only has to search a
10-dimensional space, not a 31 425-dimensional one.

#### Your fitted betas

From [your_scan_smplx_measurements.json](output/models/final/your_scan_smplx_measurements.json):

```
"betas": [0.0109, 0.0555, 0.0239, 0.0103, 0.0011,
          -0.0061, -0.0005, -0.0003, -0.0018, -0.0007]
```

Every value is tiny (all below 0.06). Interpretation: **your body is very
close to the statistical-mean body** in SMPL-X's shape space. The height
gap between the default 1.72 m mean body and your actual 1.87 m came from
the **scale** parameter (× 1.094), not from β.

If you were extremely tall and slim, you'd see `β ≈ [+2.3, -1.7, +0.4, …]`.
If muscular with a broad chest, `β ≈ [+0.8, +1.9, -0.3, …]`.

#### The shape prior

During fitting, the loss contains `10⁻³ · ‖β‖²`. This penalises large `β`
magnitudes — it's a *Bayesian prior* saying "bodies near the mean are more
likely than bodies far from it". Without this prior, the optimiser would
happily set `β = [50, -30, 12, …]` to squeeze the last micrometre out of
the Chamfer loss by contorting the mesh into implausible shapes.

### Reading the training output line

Every 25 iterations the fitter prints a line like:

```
iter 100   loss=0.00086   β‖=0.13   scale=1.092
```

- **`iter 100`** — optimisation step 100 of 400. Each step runs one gradient
  update via PyTorch's Adam optimiser.
- **`loss=0.00086`** — bidirectional Chamfer distance in **m²**. The square
  root (≈ 2.9 cm) approximates the average surface-to-surface gap. You want
  this monotonically decreasing. Good fits land at 0.0005–0.002 m²; worse
  than 0.01 m² usually means something is misaligned.
- **`β‖=0.13`** — L1 norm of the shape vector. `0` = statistical-average
  body. Values around 0.1–0.5 are normal; beyond 3 means the scan is far
  from the training distribution (very tall, very overweight, atypical
  proportions) — often a signal that your target mesh isn't aligned right.
- **`scale=1.092`** — uniform scaling applied. Starts near 1.0 after the
  initial height estimate. Stable final values are 0.9–1.15. Drift to
  0.5 or 3.0 means the fit has diverged — usually a sign of a mesh unit
  mismatch or mis-aligned target.

### Gender auto-detection (`--gender auto`, default)

SMPL-X ships three variants: **neutral**, **male**, **female**. They differ
in average pelvis width, shoulder slope, chest geometry, muscle mass —
enough that the wrong gender model fits noticeably worse.

`--gender auto` does this:

1. Run a short probe fit (**120 iters, shape only, no body_pose**) for each
   gender independently — ≈ 20 seconds each on CPU.
2. Record the final Chamfer loss from each.
3. Pick the gender with the lowest loss.
4. Run the full fit (**400 iters, shape + pose**) with the winning gender.

The script also reports a **confidence margin** — the percentage gap between
the best and second-best loss. A strong result looks like:

```
  probing gender=male…     final loss: 0.00081
  probing gender=female…   final loss: 0.00094
  probing gender=neutral…  final loss: 0.00086
  → best fit: male (loss=0.00081)
    confidence: +6.2% better than runner-up
```

A margin below ~2 % means the scan is visually ambiguous between genders —
rare but possible for lean, unclothed, average-height bodies.

### The five-stage pipeline

```
 Target mesh (aligned OBJ, metres)
        │
        ▼
 ① Load SMPL-X  — neutral/male/female .npz  (10 475 verts, 21 body joints)
        │
        ▼
 ② Initialise   — rotate Y-up → Z-up, scale SMPL-X to target height,
                  translate to target centroid, set body_pose ≈ A-pose
        │
        ▼
 ③ Optimise    — Adam, N iters, loss = bidirectional Chamfer + regularisers
                  Params: betas (10), body_pose (63, optional), global_orient (3),
                          transl (3), log-scale (1)          → ≈ 80 parameters
        │
        ▼
 ④ Evaluate    — forward pass with fitted params
                  vertices = smplx(β, θ, R) · exp(s) + t
        │
        ▼
 ⑤ Measure     — circumferences via cross-section of fitted mesh at joint heights
                  lengths via joint-to-joint Euclidean distance
                  widths via shoulder / knee / elbow joint geometry
```

### The fitting loss — term by term

```
L  =   mean  ‖v_smplx_i  − nearest(v_smplx_i,  target)‖²     ← model→scan
     +  mean  ‖v_target_j − nearest(v_target_j, smplx) ‖²     ← scan→model
     +  10⁻³  · ‖β‖²                                           ← shape prior
     +  10⁻⁴  · ‖θ‖²                                           ← pose prior
```

- **Bidirectional Chamfer** (first two lines): pushes every model vertex
  toward the nearest scan vertex *and* every scan vertex toward the nearest
  model vertex. Single-sided Chamfer lets the model "hide inside" the scan
  to minimise its half of the loss — the second term prevents that.
- **Shape prior `‖β‖²`**: keeps the shape parameters near zero (statistical
  mean body). Without this, the optimiser would contort the mesh into
  implausible shapes just to squeeze a few more micrometres off the Chamfer.
- **Pose prior `‖θ‖²`**: same idea, for joint angles. Keeps the fit in a
  plausible standing pose rather than letting limbs snake through the body.

Nearest-neighbour indices come from a scipy `cKDTree` rebuilt each iteration.
Gradients flow through the quadratic term; the NN selection itself is not
differentiated (this is the trick that keeps the whole loop CPU-friendly —
no `pytorch3d`, no CUDA required).

### Why fitting is more accurate than direct slicing

| Problem with raw-mesh slicing | How SMPL-X fitting avoids it |
|---|---|
| ISO proportion landmarks (e.g. "waist at 61.8 % of height") drift by ±5 cm from person to person | SMPL-X knows where **this specific body's** waist joint is after fitting |
| Scan has clothing, holes, noise, floor fragments | Fitted SMPL-X is a clean, watertight statistical body |
| Cross-section may hit the wrong anatomy (neck slice cutting through chest) | Slices reference the fitted joint tree, so a "neck" slice really is at the neck |
| Arms at unknown pose break perpendicular-cut math | Arms have explicit joints (shoulder → elbow → wrist); slices are taken perpendicular to the bone segment |

### The five-stage pipeline

```
 Target mesh (aligned OBJ, metres)
        │
        ▼
 ① Load SMPL-X  — neutral/male/female .npz  (10 475 verts, 21 body joints)
        │
        ▼
 ② Initialise   — rotate Y-up → Z-up, scale SMPL-X to target height,
                  translate to target centroid, set body_pose ≈ A-pose
        │
        ▼
 ③ Optimise    — Adam, N iters, loss = bidirectional Chamfer + regularisers
                  Params: betas (10), body_pose (63, optional), global_orient (3),
                          transl (3), log-scale (1)          → ≈ 80 parameters
        │
        ▼
 ④ Evaluate    — forward pass with fitted params
                  vertices = smplx(β, θ, R) · exp(s) + t
        │
        ▼
 ⑤ Measure     — circumferences via cross-section of fitted mesh at joint heights
                  lengths via joint-to-joint Euclidean distance
                  widths via shoulder / knee / elbow joint geometry
```

### Fitting loss

```
L =   Σ ‖v_smplx  − nearest(v_smplx,  target)‖²       (model → scan)
    + Σ ‖v_target − nearest(v_target, smplx) ‖²       (scan → model)
    + 10⁻³ ·‖β‖²                                       (shape prior)
    + 10⁻⁴ ·‖θ‖²                                       (pose prior)
```

Nearest-neighbour indices come from a scipy `cKDTree` rebuilt each iteration.
Gradients flow through the quadratic term; the NN selection itself is not
differentiated (this is the trick that keeps the whole loop CPU-friendly —
no `pytorch3d`, no CUDA required).

### How each measurement is derived from the fitted model

| Measurement | Source | How it's computed |
|---|---|---|
| **height** | mesh | `verts[:,2].max() − verts[:,2].min()` — whole body along Z |
| **across_shoulder** | joints | Euclidean distance `‖left_shoulder − right_shoulder‖` |
| **shoulder_width** | joints | `across_shoulder / 2` (one-shoulder measurement) |
| **front_inner_shoulder** | joints | `across_shoulder × 1.05` — small arc correction |
| **chest** | slice | Horizontal cross-section at `(spine3 + shoulder.z) / 2 − 4 cm`, largest contour |
| **bust_size** | slice | Same slice as chest (surface scan has no internal anatomy) |
| **underbust** | slice | Horizontal slice at `spine3.z − 2 cm`, largest contour |
| **waist** | slice | Horizontal slice at the `spine2.z` joint height |
| **high_hip** | slice | Horizontal slice at midpoint of `hip` and `spine1` Z |
| **hip** | slice | Horizontal slice at `hip.z + 1 cm`, largest contour |
| **neck_to_waist** | joints | `(neck.z + 0.30·(head.z − neck.z)) − spine2.z` — shifted up from joint because the SMPL-X "neck" joint sits at the shoulder attachment, not the anatomical neck base |
| **neck_circumference** | slice | Horizontal slice 55 % of the way from `neck` to `head`, contour nearest the neck centreline |
| **neck_base** | slice | Horizontal slice 30 % of the way from `neck` to `head` (above shoulder-fusion zone), contour nearest centreline |
| **neck_length** | joints | `‖neck − head‖ × 0.60` — joint-to-joint includes skull interior, factor 0.60 gives anatomical neck span |
| **upper_arm_length** | joints | `‖shoulder − elbow‖` (averaged left/right) |
| **lower_arm_length** | joints | `‖elbow − wrist‖` (averaged left/right) |
| **bicep_girth** | slice | Slice **perpendicular to the humerus bone** at 45 % shoulder→elbow, contour nearest bone midpoint (rejects torso contour from the same plane) |
| **forearm_girth** | slice | Slice **perpendicular to the ulna bone** at 35 % elbow→wrist |
| **elbow_width** | verts | Y-range of vertex band around the right_elbow joint |
| **upper_leg_length** | joints | `‖hip − knee‖` (averaged left/right) |
| **lower_leg_length** | joints | `‖knee − ankle‖` (averaged left/right) |
| **thigh_girth** | slice | Horizontal slice at midpoint of `hip` and `knee` — section has two contours (two legs), take the larger |
| **calf_girth** | slice | Horizontal slice at midpoint of `knee` and `ankle`, one leg's contour |
| **ankle_girth** | slice | Horizontal slice just above `ankle.z`, one leg's contour |
| **knee_width** | verts | X-range of vertices in a 10×15×2 cm box around the right knee joint |

**Three slice strategies** — picked per measurement to handle contour ambiguity:
1. **Largest contour** — torso slices (chest, waist, hip): one body, one contour, biggest perimeter wins.
2. **Nearest-to-point contour** — limb and neck slices: the infinite plane also cuts the torso, so pick the contour whose 3D centroid is closest to the bone/landmark midpoint.
3. **Larger of two** — leg slices (thigh, calf, ankle): expect two contours (one per leg), take the larger of the two; if only one (legs touching) return half its perimeter.

### Worked example: `forearm_girth` step by step

Let's trace exactly how the number `forearm_girth = 28.5 cm` came out of the
fitted mesh. Six steps:

#### Step 1 — Look up joint positions

SMPL-X's forward pass returns 127 joint positions. Pull out joint 19
(`right_elbow`) and joint 21 (`right_wrist`):

```
elbow_r = joints[19] = (+0.36, +0.05, +1.39)   ← metres, Z-up
wrist_r = joints[21] = (+0.62, +0.08, +1.13)
```

These are **anatomically exact** positions for this specific body — they're
not guesses from body proportions, they come out of the SMPL-X skeleton
after the fit.

#### Step 2 — Pick a point 35 % along the forearm bone

```
midpoint = elbow + 0.35 · (wrist − elbow)
         = (+0.45, +0.06, +1.30)
```

Why 0.35? The forearm is thickest near the elbow and tapers toward the
wrist. 35 % lands in the meaty part. 0.5 (the middle) would still work but
gives a slightly smaller number; 0.8 (near the wrist) would give the wrist
girth instead.

#### Step 3 — Compute the perpendicular slicing plane

The plane's **normal** is the unit vector along the bone:

```
bone_direction = (wrist − elbow) / ‖wrist − elbow‖
               = (+0.68, +0.07, −0.73)    ← diagonal, arm hanging down
```

That's it — the plane passes through `midpoint` with normal `bone_direction`.
It's not horizontal. It's whatever angle the forearm happens to be at in
this fit.

#### Step 4 — Cut the mesh with the plane

```python
section = mesh.section(plane_origin=midpoint, plane_normal=bone_direction)
```

The plane extends to infinity. It slices the forearm **and** the torso
(because the perpendicular plane at a dropped arm passes through the chest
as well). `trimesh` returns every closed polyline where the plane crosses
mesh triangles. In this case: 2 or 3 loops.

```
         ┌────────┐
         │        │   ← big ellipse  (torso slice, ~1.85 m perimeter)
         │        │
      ───┼────────┼───   ← plane cuts through here
         │        │
         └────────┘

             ○              ← small circle (forearm slice, ~0.285 m)
                               centred on `midpoint`
```

#### Step 5 — Pick the correct contour

We want the forearm circle, not the torso ellipse. The script computes the
**3D centroid** of each contour and picks the one closest to `midpoint`:

```
torso   centroid → (+0.02, +0.05, +0.95)   distance to midpoint = 0.55 m
forearm centroid → (+0.45, +0.06, +1.30)   distance to midpoint ≈ 0.00 m  ✓
```

The forearm contour wins — its centroid is *by construction* at `midpoint`.

#### Step 6 — Sum the edge lengths

The selected contour is a polyline of a few dozen points going around the
forearm. The perimeter is just a loop sum:

```
perimeter = Σᵢ  ‖pᵢ₊₁ − pᵢ‖       ← sum of segment lengths
          ≈ 0.285 m
```

Convert metres → cm:  `0.285 × 100 = 28.5 cm` → that's `forearm_girth`.

#### Both arms + max

```python
forearm_r = arm_circ("right_elbow", "right_wrist", 0.35)   # 28.5 cm
forearm_l = arm_circ("left_elbow",  "left_wrist",  0.35)   # 28.3 cm
forearm_circ = max(forearm_r, forearm_l)                    # 28.5 cm
```

Taking the `max` covers small left/right asymmetries (handedness, muscle
imbalance, scanning artefacts on one side).

---

**Why this is more robust than naive cross-section slicing:** the bone
direction is known **exactly** from the fitted SMPL-X joints — so the
perpendicular cut is anatomically correct regardless of how the arm was
posed in the raw scan. A purely geometric pipeline has no way to know
where the ulna axis points; it would have to guess or assume T-pose. That
assumption fails the moment your arms aren't exactly horizontal.

Every other limb measurement (`bicep_girth`, `thigh_girth`, `calf_girth`,
`upper_arm_length`, `neck_circumference`…) follows the same pattern —
look up the relevant joints, pick a point along the bone, slice
perpendicular, pick the right contour, sum edges.

### CLI flags

```powershell
python backend\smplx_measure.py <aligned.obj>                 # defaults: --gender auto, 400 iters, CPU
python backend\smplx_measure.py <aligned.obj> --gender male   # skip auto-detect, force gender
python backend\smplx_measure.py <aligned.obj> --gender female
python backend\smplx_measure.py <aligned.obj> --gender neutral
python backend\smplx_measure.py <aligned.obj> --iters 800     # longer fit, tighter Chamfer (tighter ≈ more accurate)
python backend\smplx_measure.py <aligned.obj> --fast          # shorthand: --iters 200 --no-pose
python backend\smplx_measure.py <aligned.obj> --no-pose       # shape-only fit (seconds, less accurate)
python backend\smplx_measure.py <aligned.obj> --device cuda   # if GPU is available — 10× faster
python backend\smplx_measure.py <aligned.obj> --no-save-obj   # skip writing the fitted mesh
```

### Output files (in `output/models/final/`)

| File | Contents |
|---|---|
| `<stem>_smplx_measurements.json` | all measurements in cm + fitted β coefficients + final Chamfer loss + detected gender |
| `<stem>_smplx_measurements.obj` | the fitted SMPL-X mesh in the **same Z-up convention as your aligned scan**. Open both in the same viewer and they line up — body axes match, facing matches |

> **Orientation**: both `your_scan_aligned.obj` and
> `your_scan_smplx_measurements.obj` are Z-up with face toward −Y (the
> convention established by `align_scan.py`). Load them in the same scene
> in Blender / MeshLab / three.js and the fitted mesh will overlay directly
> on top of the scan for a visual sanity check. If your viewer defaults to
> Y-up and shows both lying on their side, either switch the viewer's
> up-axis setting to Z-up, or apply a single `-90°` rotation around the X
> axis — it affects both meshes equally, so they stay in lockstep.

### When to prefer which pipeline

- **scan_measure.py** — quick iteration on scan-alignment tuning, when you
  don't yet trust the orientation. Runs in <1 s.
- **smplx_measure.py** — final measurements, atypical body shapes, clothed
  scans, or when `verify_measurements.py` on Pipeline A shows many WARNs.
  Runs in 1–3 min on CPU (add ~45 s for `--gender auto`), ~10 s on GPU.

---

## scan_measure.py — How the measurement works

Once the mesh stands upright, measuring is mostly a matter of slicing the
body at the right heights and doing arc-length or bounding-box math on
each slice.

### Landmark heights

The script uses ISO 7250-1 / ANSUR II anthropometric proportions — for
an average adult, each named landmark sits at a known fraction of total
height (floor = 0, top of head = 1):

| Landmark | Fraction | What's there |
|---|---:|---|
| Top of head | 1.000 | — |
| Chin | 0.871 | jawline |
| Neck base | 0.818 | neck meets shoulders |
| Shoulder | 0.808 | deltoid top |
| Armpit | 0.787 | underarm |
| Chest | 0.749 | nipple line |
| Underbust | 0.702 | lower rib |
| Waist | 0.618 | narrowest torso |
| High hip | 0.566 | iliac crest |
| Hip | 0.515 | widest hip |
| Crotch | 0.466 | pelvis base |
| Mid thigh | 0.388 | — |
| Knee | 0.265 | — |
| Mid calf | 0.177 | — |
| Ankle | 0.073 | — |

These are statistical averages — individual bodies vary by ±2–3 cm around
each landmark height, which is close to the tailor-tape accuracy expected
from this pipeline.

### Three primitive operations

Every measurement reduces to one of three geometric operations on the mesh:

**1. Horizontal cross-section + arc length** (circumferences)

```
    ┌──────┐              ╱─────╲
    │ mesh │ ──slice at── │     │ ──sum segments──▶ circumference
    └──────┘   z = h      ╲─────╱
```

Used for: chest, waist, hip, high_hip, underbust, neck_circumference,
neck_base, thigh_girth, calf_girth, ankle_girth, bicep_girth, forearm_girth.

**2. Vertex-band width** (widths)

```
vertices with z ∈ [h−δ, h+δ]  →  X-range (or Y-range) of those vertices
```

Used for: across_shoulder, shoulder_width, knee_width, elbow_width.

**3. Landmark-to-landmark distance** (lengths)

```
length = h(landmark_A) − h(landmark_B)
```

Used for: neck_length, neck_to_waist, upper_leg_length, lower_leg_length,
upper_arm_length, lower_arm_length.

### Handling the two-legs problem

At thigh / calf / ankle heights the cross-section contains **two separate
closed contours** (one per leg). The script:

1. Counts closed polygons in the slice.
2. If two or more → takes the larger one (single leg).
3. If only one (legs touching) → returns half the total perimeter as an estimate.

### Handling the T-pose arms

If the pose detector classifies the scan as T-pose (shoulder width > 1.8× hip
width), arm measurements come from **vertical** cross-sections along X rather
than horizontal sections along Z:

```
                  ┌───┐
       arm ──►    │   │    ◄── torso   ◄── arm
                  │   │
   ═══════════════╪═══╪═══════════════  ← slice plane (normal = X axis)
                  │   │                   at x = torso_edge + upper_arm × 0.4
                  └───┘
```

If the scan is A-pose or neutral, the script falls back to ISO-7250 average
arm proportions (height × 0.188 for upper arm length, etc.) and flags those
entries with `"_note": "estimated from height ratios"`.

### Unit auto-detection

Raw mesh heights are converted to centimetres by inspecting the post-alignment
Z extent:

| Raw height | Assumed units | Scale factor |
|---|---|---|
| > 500 | millimetres | ÷ 10 |
| 50–500 | centimetres | × 1 |
| 1–50 | metres | × 100 |

### Measurements produced

```
global        height
neck          neck_circumference, neck_base, neck_length
upper_torso   across_shoulder, shoulder_width, front_inner_shoulder,
              chest, bust_size, underbust, neck_to_waist
lower_torso   waist, high_hip, hip
arms          upper_arm_length, lower_arm_length,
              bicep_girth, forearm_girth, elbow_width
legs          upper_leg_length, lower_leg_length,
              thigh_girth, calf_girth, ankle_girth, knee_width
```

Every field is cm, rounded to one decimal.

---

## Known limitations

- **Clothed scans** add 1–3 cm to all circumferences — the laser captures the
  outer garment surface, not the skin.
- **Incomplete scans** — missing armpit region or top of head will degrade
  the landmark proportions and the numbers that depend on them.
- **Arm measurements** are only directly measured when the scan is in T-pose;
  otherwise they are statistical estimates from body-height ratios.
- **Left/right asymmetry** is not reported — each circumference is the larger
  of the two sides where applicable (e.g. one leg at thigh level).
- **Body fat / muscle distribution** can shift landmark heights by ±3 cm from
  the ISO averages. For very atypical body types, the waist / hip landmark
  heights may need manual tuning.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ValueError: string is not a file` | Wrong path (file is in `input\` subfolder) | Include the full relative path |
| Height reported as 339 cm (or similar absurd number) | Background geometry along one axis | Re-run alignment — new scorer filters this; or force `--axis` manually |
| Person still upside-down after alignment | Ambiguous mass distribution (crouched, reaching) | Edit the mesh to remove background, re-run |
| Person faces away from camera | Near-symmetric depth (back and front both bulge) | `--face +y` to override |
| All arm measurements marked `_note: estimated` | Scan isn't T-pose | Accept the estimates, or re-scan in T-pose |
| `AttributeError: 'TrackedArray' object has no attribute 'ptp'` | NumPy 2.0 removed `.ptp()` method | Already patched — pull latest script |

(See the **Folder layout** section at the top of this file for the full tree.)
