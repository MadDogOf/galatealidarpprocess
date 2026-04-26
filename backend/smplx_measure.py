#!/usr/bin/env python3
"""
smplx_measure.py — Fit SMPL-X to an aligned body scan OBJ, then extract
tailor measurements from the fitted statistical body model.

Why this is more accurate than proportion-slicing (scan_measure.py):
  • SMPL-X joint positions are anatomically exact, not ISO averages.
  • The fitted mesh is clean: no clothing, no holes, no noise, no floor.
  • Circumferences come from known vertex rings around the waist / chest /
    hip rather than arbitrary-Z slices that may hit the wrong region.

Pipeline
────────
  1. Load target mesh           — aligned OBJ (output of align_scan.py)
  2. Load SMPL-X model          — smplx_models/models/smplx/SMPLX_{gender}.npz
  3. Initial alignment          — scale + translate SMPL-X onto the target
  4. Fit shape + pose + global  — minimise bidirectional Chamfer distance
  5. Extract measurements       — use joint positions + cross-sections
  6. Save fitted OBJ + JSON     — output/models/final/

Usage:
    python smplx_measure.py output/models/aligned/your_scan_aligned.obj
    python smplx_measure.py <obj> --gender female
    python smplx_measure.py <obj> --iters 600 --fast
    python smplx_measure.py <obj> --no-pose      # fit shape only (faster, less accurate)

Requirements (already in requirements.txt):
    torch, smplx, trimesh, numpy, scipy
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import trimesh
import smplx
from scipy.spatial import cKDTree

# Force UTF-8 output so Unicode symbols print cleanly on Windows cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# Script lives in backend/, so the project root is one level up.
ROOT            = Path(__file__).resolve().parent.parent
SMPLX_MODEL_DIR = ROOT / "smplx_models" / "models"   # contains smplx/SMPLX_*.npz
DEFAULT_OUTDIR  = ROOT / "output" / "models" / "final"


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# FBX Export (ASCII)
# ─────────────────────────────────────────────────────────────────────────────

def save_fbx_ascii(vertices: np.ndarray, faces: np.ndarray, joints: np.ndarray, weights: np.ndarray, output_path: Path):
    """
    Exports the mesh as a RIGGED FBX ASCII file. 
    Includes Skeleton (bones) and Skinning Weights (Deformers).
    """
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # SMPL-X Joint Names (Standard 55 joints)
    JOINT_NAMES = [
        "Pelvis", "L_Hip", "R_Hip", "Spine1", "L_Knee", "R_Knee", "Spine2", "L_Ankle", "R_Ankle", "Spine3",
        "L_Foot", "R_Foot", "Neck", "L_Collar", "R_Collar", "Head", "L_Shoulder", "R_Shoulder", "L_Elbow", "R_Elbow",
        "L_Wrist", "R_Wrist", "Jaw", "L_Eye_Irr", "R_Eye_Irr", "L_Index1", "L_Index2", "L_Index3", "L_Middle1", "L_Middle2",
        "L_Middle3", "L_Pinky1", "L_Pinky2", "L_Pinky3", "L_Ring1", "L_Ring2", "L_Ring3", "L_Thumb1", "L_Thumb2", "L_Thumb3",
        "R_Index1", "R_Index2", "R_Index3", "R_Middle1", "R_Middle2", "R_Middle3", "R_Pinky1", "R_Pinky2", "R_Pinky3", "R_Ring1",
        "R_Ring2", "R_Ring3", "R_Thumb1", "R_Thumb2", "R_Thumb3"
    ]

    # Joint Hierarchy (SMPL-X parents)
    PARENTS = [-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19, 15, 15, 15, 20, 25, 26, 20, 28, 29, 20, 31, 32, 20, 34, 35, 20, 37, 38, 21, 40, 41, 21, 43, 44, 21, 46, 47, 21, 49, 50, 21, 52, 53]

    # Flatten vertices and faces
    v_flat = vertices.flatten()
    f_fbx = []
    for f in faces:
        f_fbx.extend([int(f[0]), int(f[1]), int(-f[2] - 1)])

    v_str = ",".join(map(lambda x: f"{x:.6f}", v_flat))
    f_str = ",".join(map(str, f_fbx))

    # Generate Model nodes for joints
    joint_models = ""
    joint_connections = ""
    for i, name in enumerate(JOINT_NAMES):
        id = 1000000 + i
        joint_models += f"""
    Model: {id}, "Model::{name}", "LimbNode" {{
        Version: 232
        Properties70:  {{
            P: "Lcl Translation", "Lcl Translation", "", "A", {joints[i][0]*100}, {joints[i][1]*100}, {joints[i][2]*100}
        }}
    }}"""
        parent_id = 1000000 + PARENTS[i] if PARENTS[i] != -1 else 0
        joint_connections += f"\n    C: \"OO\", {id}, {parent_id}"

    # Generate Deformers (Clusters)
    # This is where skinning weights are mapped
    clusters = ""
    cluster_connections = ""
    for i, name in enumerate(JOINT_NAMES):
        c_id = 3000000 + i
        # Find vertices influenced by this joint (weight > 0.001)
        v_indices = np.where(weights[:, i] > 0.001)[0]
        if len(v_indices) == 0: continue
        
        idx_str = ",".join(map(str, v_indices))
        w_str = ",".join(map(lambda x: f"{x:.4f}", weights[v_indices, i]))
        
        clusters += f"""
    SubDeformer: {c_id}, "SubDeformer::Cluster", "Cluster" {{
        Version: 100
        Indexes: *{len(v_indices)} {{
            a: {idx_str}
        }}
        Weights: *{len(v_indices)} {{
            a: {w_str}
        }}
        Transform: *16 {{
            a: 1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1
        }}
        TransformLink: *16 {{
            a: 1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1
        }}
    }}"""
        cluster_connections += f"\n    C: \"OO\", {c_id}, 2500000" # Connect to Skin Deformer
        cluster_connections += f"\n    C: \"OO\", 1000000{i}, {c_id}" # Connect Joint to Cluster

    fbx_content = f"""FBX 7.4.0 project file
; Created by Galatea Vision System

FBXHeaderExtension:  {{
    FBXHeaderVersion: 1003
    FBXVersion: 7400
}}

Definitions:  {{
    Count: {2 + len(JOINT_NAMES) * 2}
    ObjectType: "Model" {{ Count: {1 + len(JOINT_NAMES)} }}
    ObjectType: "Geometry" {{ Count: 1 }}
    ObjectType: "Deformer" {{ Count: {1 + len(JOINT_NAMES)} }}
}}

Objects:  {{
    Geometry: 2000000, "Geometry::Mesh", "Mesh" {{
        Vertices: *{len(v_flat)} {{ a: {v_str} }} 
        PolygonVertexIndex: *{len(f_fbx)} {{ a: {f_str} }} 
    }}

    Model: 5000000, "Model::SMPLX_Mesh", "Mesh" {{
        Version: 232
        Properties70: {{ P: "Lcl Translation", "Lcl Translation", "", "A", 0,0,0 }}
    }}
    {joint_models}

    Deformer: 2500000, "Deformer::Skin", "Skin" {{
        Version: 101
    }}
    {clusters}
}}

Connections:  {{
    C: "OO", 2000000, 5000000
    C: "OO", 5000000, 0
    C: "OO", 2500000, 2000000
    {joint_connections}
    {cluster_connections}
}}
"""
    output_path.write_text(fbx_content, encoding="utf-8")


# SMPL-X joint indices (body joints, first 22)
# ─────────────────────────────────────────────────────────────────────────────
J = {
    "pelvis": 0,  "left_hip": 1,  "right_hip": 2,  "spine1": 3,
    "left_knee": 4, "right_knee": 5, "spine2": 6,
    "left_ankle": 7, "right_ankle": 8, "spine3": 9,
    "left_foot": 10, "right_foot": 11, "neck": 12,
    "left_collar": 13, "right_collar": 14, "head": 15,
    "left_shoulder": 16, "right_shoulder": 17,
    "left_elbow": 18, "right_elbow": 19,
    "left_wrist": 20, "right_wrist": 21,
}


# ─────────────────────────────────────────────────────────────────────────────
# Target mesh loading
# ─────────────────────────────────────────────────────────────────────────────

def load_target(obj_path: str) -> trimesh.Trimesh:
    """
    Load the aligned scan and merge into one mesh.

    Previously this dropped all but the largest connected component — that
    was wrong. Body scans are typically split into multiple disconnected
    shells (torso, head, each limb), and keeping only the largest would
    throw away most of the body. We trust align_scan.py to have stripped
    any floor/noise already.
    """
    raw = trimesh.load(obj_path, force="mesh", process=True)
    if isinstance(raw, trimesh.Scene):
        raw = trimesh.util.concatenate(list(raw.geometry.values()))
    return raw


def auto_scale_to_metres(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """SMPL-X lives in metres. Rescale the target if it's in cm or mm."""
    h = float(mesh.bounds[1][2] - mesh.bounds[0][2])
    if h > 500:
        mesh.apply_scale(0.001)  # mm → m
    elif h > 50:
        mesh.apply_scale(0.01)   # cm → m
    # else assumed metres
    return mesh


# ─────────────────────────────────────────────────────────────────────────────
# Fitting
# ─────────────────────────────────────────────────────────────────────────────

def make_smplx_model(gender: str, device: str) -> smplx.SMPLX:
    model = smplx.create(
        model_path=str(SMPLX_MODEL_DIR),
        model_type="smplx",
        gender=gender,
        num_betas=10,
        use_pca=False,
        flat_hand_mean=True,
        ext="npz",
    ).to(device)
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model


def default_apose(device: str) -> torch.Tensor:
    """
    Initial body pose ≈ A-pose: arms slightly down instead of SMPL-X default T-pose.
    21 body joints × 3 axis-angle params = 63 dims.
    """
    pose = torch.zeros(1, 63, device=device)
    # left_shoulder (idx 16 → body pose index 15 since pelvis is root)
    # body_pose is flattened joints 1..21 (pelvis=0 is the root orient, separate)
    # SMPL-X body_pose order starts at left_hip (joint 1). So body joint k → index (k-1)*3.
    def body_idx(joint_name): return (J[joint_name] - 1) * 3
    # Drop arms by ~60 deg around Z axis (roll the shoulder down)
    pose[0, body_idx("left_shoulder")  + 2] = -1.05   # ~60°
    pose[0, body_idx("right_shoulder") + 2] = +1.05
    return pose


def fit_smplx(
    target_verts_np: np.ndarray,
    gender: str = "neutral",
    iters: int = 400,
    lr_shape: float = 0.03,
    lr_pose:  float = 0.005,
    optimise_pose: bool = True,
    device: str = "cpu",
    verbose: bool = True,
) -> dict:
    """
    Fit SMPL-X to `target_verts_np` (N×3 points, in metres).
    Returns a dict with fitted parameters + final vertices + joints.
    """
    model = make_smplx_model(gender, device)

    # ── Learnable parameters ────────────────────────────────────────────────
    betas         = torch.zeros(1, 10, device=device, requires_grad=True)
    global_orient = torch.zeros(1, 3,  device=device, requires_grad=True)
    transl        = torch.zeros(1, 3,  device=device, requires_grad=True)
    scale_log     = torch.zeros(1,     device=device, requires_grad=True)  # exp(0) = 1
    body_pose     = default_apose(device).clone().detach().requires_grad_(optimise_pose)

    # ── Initial scale + translation so SMPL-X lines up with target ──────────
    with torch.no_grad():
        init_out = model(betas=betas, body_pose=body_pose)
        init_v   = init_out.vertices[0]
        init_h   = float(init_v[:, 1].max() - init_v[:, 1].min())  # SMPL-X y = up
        # SMPL-X rest pose is Y-up; target is Z-up after alignment.
        # Rotate +90° around X so the head (originally at +Y) ends up at +Z.
        #   (0, 1, 0) · R_X(+π/2) = (0, 0, +1)  ← correct
        #   (0, 1, 0) · R_X(-π/2) = (0, 0, -1)  ← would be upside-down
        global_orient_init = torch.tensor([[np.pi / 2, 0.0, 0.0]], device=device)
        global_orient.data.copy_(global_orient_init)

    target_t   = torch.from_numpy(target_verts_np).float().to(device)
    target_h   = float(target_verts_np[:, 2].max() - target_verts_np[:, 2].min())
    target_c   = torch.from_numpy(target_verts_np.mean(axis=0)).float().to(device)

    # Scale initial guess (apply manually — never pass transl into forward)
    with torch.no_grad():
        scale_log.data.fill_(float(np.log(max(target_h / max(init_h, 1e-3), 1e-3))))
        out_init = model(betas=betas, body_pose=body_pose, global_orient=global_orient)
        v0 = out_init.vertices[0] * torch.exp(scale_log)
        transl.data.copy_(target_c - v0.mean(dim=0))

    # ── Optimiser ────────────────────────────────────────────────────────────
    params = [
        {"params": [betas],         "lr": lr_shape},
        {"params": [global_orient], "lr": lr_pose},
        {"params": [transl],        "lr": lr_shape},
        {"params": [scale_log],     "lr": lr_shape / 3},
    ]
    if optimise_pose:
        params.append({"params": [body_pose], "lr": lr_pose})

    opt = torch.optim.Adam(params)

    target_np = target_verts_np.astype(np.float32)
    target_tree = cKDTree(target_np)

    t0 = time.time()
    losses = []

    for i in range(iters):
        # Never pass transl to the SMPL-X forward — apply it manually after scaling
        out = model(
            betas=betas, body_pose=body_pose,
            global_orient=global_orient,
        )
        verts = out.vertices[0] * torch.exp(scale_log) + transl

        # Bidirectional Chamfer via KDTree (nn indices are held constant per step)
        v_np = verts.detach().cpu().numpy()
        _, idx_s2t = target_tree.query(v_np, k=1)
        nn_t = torch.from_numpy(target_np[idx_s2t]).to(device)
        loss_s2t = ((verts - nn_t) ** 2).sum(-1).mean()

        smplx_tree = cKDTree(v_np)
        _, idx_t2s = smplx_tree.query(target_np, k=1)
        nn_s = verts[idx_t2s]
        loss_t2s = ((target_t - nn_s) ** 2).sum(-1).mean()

        reg_beta = (betas ** 2).sum() * 1e-3
        reg_pose = (body_pose ** 2).sum() * 1e-4 if optimise_pose else 0.0

        loss = loss_s2t + loss_t2s + reg_beta + reg_pose

        opt.zero_grad()
        loss.backward()
        opt.step()

        losses.append(float(loss.detach()))
        if verbose and (i % 25 == 0 or i == iters - 1):
            print(f"  iter {i:4d}   loss={losses[-1]:.5f}   "
                  f"β‖={float(betas.detach().abs().sum()):.2f}   "
                  f"scale={float(torch.exp(scale_log).detach()):.3f}")

    dt = time.time() - t0
    if verbose:
        print(f"  Fit complete in {dt:.1f}s   final loss = {losses[-1]:.5f}")

    # ── Final forward pass ───────────────────────────────────────────────────
    with torch.no_grad():
        out = model(
            betas=betas, body_pose=body_pose,
            global_orient=global_orient,
        )
        s = float(torch.exp(scale_log))
        verts_final  = (out.vertices[0] * s + transl).cpu().numpy()
        joints_final = (out.joints[0]   * s + transl).cpu().numpy()

    return {
        "vertices":       verts_final,
        "joints":         joints_final,
        "faces":          model.faces.copy(),
        "weights":        model.lbs_weights.detach().cpu().numpy(), # ADDED WEIGHTS
        "betas":          betas.detach().cpu().numpy().flatten().tolist(),
        "body_pose":      body_pose.detach().cpu().numpy().flatten().tolist(),
        "global_orient":  global_orient.detach().cpu().numpy().flatten().tolist(),
        "transl":         transl.detach().cpu().numpy().flatten().tolist(),
        "scale":          float(torch.exp(scale_log).detach()),
        "final_loss":     float(losses[-1]),
        "iterations":     iters,
        "gender":         gender,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Measurement extraction from fitted SMPL-X
# ─────────────────────────────────────────────────────────────────────────────

def _contour_perimeters(mesh: trimesh.Trimesh,
                        origin: np.ndarray,
                        normal: np.ndarray) -> list:
    """
    Perimeters (arc lengths) of every closed polyline in a plane cut.
    Uses `p2.discrete` so we never depend on shapely — earlier versions of
    this code silently returned None when shapely was missing because
    `p2.polygons_closed` raised ModuleNotFoundError inside a bare except.
    """
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    if sec is None or len(sec.entities) == 0:
        return []
    try:
        # Use to_2D() instead of deprecated to_planar()
        p2, _ = sec.to_2D()
    except Exception:
        return []
    if p2 is None:
        return []

    lengths = []
    for polyline in p2.discrete:            # list of N_i × 2 arrays
        coords = np.asarray(polyline)
        if len(coords) < 2:
            continue
        d = np.diff(coords, axis=0)
        lengths.append(float(np.linalg.norm(d, axis=1).sum()))
    return lengths


def _slice_perimeter(mesh: trimesh.Trimesh, origin: np.ndarray,
                     normal: np.ndarray) -> Optional[float]:
    """Arc length of the largest closed contour of a plane cut."""
    lens = _contour_perimeters(mesh, origin, normal)
    return max(lens) if lens else None


def _slice_single_of_two(mesh, origin, normal):
    """For leg slices where the section shows two contours (two legs)."""
    lens = sorted(_contour_perimeters(mesh, origin, normal), reverse=True)
    if not lens:
        return None
    if len(lens) == 1:
        return lens[0] / 2.0        # legs touching — halve total perimeter
    return lens[0]                   # one leg (the larger of the two contours)


def _slice_nearest_to_point(mesh: trimesh.Trimesh,
                            origin: np.ndarray,
                            normal: np.ndarray,
                            target_xyz: np.ndarray) -> Optional[float]:
    """
    Perimeter of the closed contour whose 3D centroid is closest to
    `target_xyz`. Used for arms and neck, where the slicing plane extends
    through the torso too — taking the largest contour would grab the
    torso. Taking the contour nearest the bone midpoint gets the correct
    limb / neck contour.
    """
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    if sec is None or len(sec.entities) == 0:
        return None
    polylines_3d = sec.discrete   # list of N_i×3 arrays in world space
    if not polylines_3d:
        return None

    best_len  = None
    best_dist = float("inf")
    tgt = np.asarray(target_xyz, dtype=float)
    for polyline in polylines_3d:
        coords = np.asarray(polyline)
        if len(coords) < 3:
            continue
        centroid = coords.mean(axis=0)
        dist = float(np.linalg.norm(centroid - tgt))
        if dist < best_dist:
            d = np.diff(coords, axis=0)
            best_len  = float(np.linalg.norm(d, axis=1).sum())
            best_dist = dist
    return best_len


def extract_measurements(fit: dict) -> dict:
    """Derive tailor measurements from the fitted SMPL-X mesh + joints."""
    verts  = fit["vertices"]
    joints = fit["joints"]
    faces  = fit["faces"]
    mesh   = trimesh.Trimesh(vertices=verts, faces=faces, process=False)

    def j(name):   return joints[J[name]]
    def dist(a, b): return float(np.linalg.norm(a - b))

    # ── Height ──────────────────────────────────────────────────────────────
    height_m = float(verts[:, 2].max() - verts[:, 2].min())

    # ── Landmark Z heights (average of left/right where relevant) ───────────
    z_hip   = (j("left_hip")[2]   + j("right_hip")[2])   / 2
    z_knee  = (j("left_knee")[2]  + j("right_knee")[2])  / 2
    z_ankle = (j("left_ankle")[2] + j("right_ankle")[2]) / 2
    z_spine1 = j("spine1")[2]
    z_spine2 = j("spine2")[2]
    z_spine3 = j("spine3")[2]
    z_neck   = j("neck")[2]
    z_head   = j("head")[2]

    # ── Circumferences (horizontal slices) ──────────────────────────────────
    z_up = np.array([0.0, 0.0, 1.0])

    def circ(z):
        return _slice_perimeter(mesh, np.array([0.0, 0.0, z]), z_up)

    waist_circ     = circ(z_spine2)                              # narrowest torso
    chest_circ     = circ((z_spine3 + j("left_shoulder")[2]) / 2 - 0.04)
    underbust_circ = circ(z_spine3 - 0.02)
    hip_circ       = circ(z_hip + 0.01)
    high_hip_circ  = circ((z_hip + z_spine1) / 2)

    # Neck slices — "neck" SMPL-X joint sits at the shoulder attachment, NOT
    # at the base of the anatomical neck. Sample between z_neck and z_head.
    # 0.15 is still in the shoulder fusion zone → use 0.30 to clear shoulders.
    z_neck_base = z_neck + (z_head - z_neck) * 0.30   # base of anatomical neck
    z_neck_mid  = z_neck + (z_head - z_neck) * 0.55   # middle of the neck
    # Pick the contour nearest the neck centreline so we don't catch the
    # shoulders / chin when the slice passes through them.
    neck_ref_pos = np.array([0.0, j("neck")[1], z_neck_mid])
    neck_circ    = _slice_nearest_to_point(
        mesh, np.array([0.0, 0.0, z_neck_mid]), z_up, neck_ref_pos)
    neck_ref_base = np.array([0.0, j("neck")[1], z_neck_base])
    neck_base_circ = _slice_nearest_to_point(
        mesh, np.array([0.0, 0.0, z_neck_base]), z_up, neck_ref_base)

    # ── Leg slices (two contours expected) ──────────────────────────────────
    z_mid_thigh = (z_hip + z_knee) / 2
    z_mid_calf  = (z_knee + z_ankle) / 2
    thigh_circ  = _slice_single_of_two(mesh, np.array([0.0, 0.0, z_mid_thigh]), z_up)
    calf_circ   = _slice_single_of_two(mesh, np.array([0.0, 0.0, z_mid_calf]),  z_up)
    ankle_circ  = _slice_single_of_two(mesh, np.array([0.0, 0.0, z_ankle + 0.01]), z_up)

    # ── Arm slices (perpendicular to arm axis) ──────────────────────────────
    # The slicing plane is infinite — it extends through the torso too, so we
    # must pick the contour whose centroid is nearest the bone midpoint rather
    # than the largest contour (which would be the torso).
    def arm_circ(a_joint, b_joint, t: float):
        a, b = j(a_joint), j(b_joint)
        midpoint = a + (b - a) * t
        normal = (b - a) / (np.linalg.norm(b - a) + 1e-9)
        return _slice_nearest_to_point(mesh, midpoint, normal, midpoint)

    bicep_r = arm_circ("right_shoulder", "right_elbow", 0.45)
    bicep_l = arm_circ("left_shoulder",  "left_elbow",  0.45)
    candidates = [v for v in (bicep_r, bicep_l) if v is not None]
    bicep_circ = max(candidates) if candidates else None

    forearm_r = arm_circ("right_elbow", "right_wrist", 0.35)
    forearm_l = arm_circ("left_elbow",  "left_wrist",  0.35)
    candidates = [v for v in (forearm_r, forearm_l) if v is not None]
    forearm_circ = max(candidates) if candidates else None

    # ── Widths ──────────────────────────────────────────────────────────────
    across_shoulder = dist(j("left_shoulder"), j("right_shoulder"))
    elbow_width = abs(j("right_elbow")[1] - j("right_elbow")[1])  # front-back thickness (approx)
    # Better: local vertex band in Y around elbow joint
    e = j("right_elbow")
    band = 0.02
    local = verts[
        (np.abs(verts[:, 2] - e[2]) < band) &
        (np.abs(verts[:, 0] - e[0]) < band)
    ]
    elbow_width = float(np.ptp(local[:, 1])) if len(local) > 1 else None

    # Knee width: take vertices in a small XYZ box around the *right* knee
    # joint so we isolate a single knee (previous "total width / 2" gave
    # half the knee-to-knee span, not one knee).
    k = j("right_knee")
    local_k = verts[
        (np.abs(verts[:, 2] - k[2]) < 0.02) &
        (np.abs(verts[:, 0] - k[0]) < 0.10) &   # within 10 cm of that knee's X
        (np.abs(verts[:, 1] - k[1]) < 0.15)
    ]
    knee_width = float(np.ptp(local_k[:, 0])) if len(local_k) > 1 else None

    # ── Lengths ─────────────────────────────────────────────────────────────
    upper_arm_length = (dist(j("left_shoulder"),  j("left_elbow")) +
                        dist(j("right_shoulder"), j("right_elbow"))) / 2
    lower_arm_length = (dist(j("left_elbow"),  j("left_wrist")) +
                        dist(j("right_elbow"), j("right_wrist"))) / 2
    upper_leg_length = (dist(j("left_hip"),  j("left_knee")) +
                        dist(j("right_hip"), j("right_knee"))) / 2
    lower_leg_length = (dist(j("left_knee"),  j("left_ankle")) +
                        dist(j("right_knee"), j("right_ankle"))) / 2
    # Neck length: joint-to-joint spans from shoulder attachment up into the
    # middle of the head — too long. Empirically the actual anatomical neck
    # is ~60 % of that span (base of neck to jaw).
    neck_length   = dist(j("neck"), j("head")) * 0.60
    # Neck-to-waist: tailors measure from base-of-neck (top of shoulders) down
    # to the waist. The SMPL-X "neck" joint sits slightly below that, so shift
    # up by the same 0.30 factor used for neck_base.
    z_neck_anat = z_neck + (z_head - z_neck) * 0.30
    neck_to_waist = z_neck_anat - z_spine2

    # ── Convert metres → cm and round (force Python float — avoids numpy.float32
    #    JSON serialization errors when values come from the joints array)
    def cm(x): return round(float(x) * 100.0, 1) if x is not None else None

    def flt(x): return round(float(x), 5)

    return {
        "global": {
            "height": cm(height_m),
        },
        "upper_torso": {
            "across_shoulder":      cm(across_shoulder),
            "shoulder_width":       cm(across_shoulder / 2),
            "front_inner_shoulder": cm(across_shoulder * 1.05),
            "chest":                cm(chest_circ),
            "bust_size":            cm(chest_circ),
            "underbust":            cm(underbust_circ),
            "neck_to_waist":        cm(neck_to_waist),
        },
        "lower_torso": {
            "waist":    cm(waist_circ),
            "high_hip": cm(high_hip_circ),
            "hip":      cm(hip_circ),
        },
        "neck": {
            "neck_circumference": cm(neck_circ),
            "neck_base":          cm(neck_base_circ),
            "neck_length":        cm(neck_length),
        },
        "arms": {
            "upper_arm_length": cm(upper_arm_length),
            "lower_arm_length": cm(lower_arm_length),
            "bicep_girth":      cm(bicep_circ),
            "forearm_girth":    cm(forearm_circ),
            "elbow_width":      cm(elbow_width),
        },
        "legs": {
            "upper_leg_length": cm(upper_leg_length),
            "lower_leg_length": cm(lower_leg_length),
            "thigh_girth":      cm(thigh_circ),
            "calf_girth":       cm(calf_circ),
            "ankle_girth":      cm(ankle_circ),
            "knee_width":       cm(knee_width),
        },
        # ── Slice Z heights in metres (world space, Z-up) ─────────────────
        # Consumed by annotate_measurements.py to build the exploded view.
        # Stored as a private key so it doesn't appear inside "measurements".
        "_slice_z_m": {
            "ankle":     flt(z_ankle + 0.01),
            "calf":      flt(z_mid_calf),
            "thigh":     flt(z_mid_thigh),
            "high_hip":  flt((z_hip + z_spine1) / 2),
            "hip":       flt(z_hip + 0.01),
            "waist":     flt(z_spine2),
            "underbust": flt(z_spine3 - 0.02),
            "chest":     flt((z_spine3 + j("left_shoulder")[2]) / 2 - 0.04),
            "neck":      flt(z_neck_mid),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Gender auto-detection
# ─────────────────────────────────────────────────────────────────────────────
# Quick-fit SMPL-X three times (male / female / neutral) with a reduced iter
# count and no body-pose optimisation, then pick whichever gender model
# achieved the lowest Chamfer loss. Male and female SMPL-X models differ in
# average pelvic width, shoulder slope, chest geometry, muscle distribution
# — so the correct gender fits the scan noticeably better.

def detect_gender(target_verts: np.ndarray,
                  probe_iters: int = 220,
                  device: str = "cpu",
                  verbose: bool = True) -> str:
    """
    Probe-fit each gender model with pose + shape optimisation and pick the
    one with the lowest Chamfer loss.

    Why include body_pose in the probe: male SMPL-X has broader shoulders
    than female. A scan with arms relaxed at the sides needs pose tuning
    to let the male model bring its arms down — otherwise the extra shoulder
    width inflates the probe loss and the scorer picks female even when
    male is objectively the better fit at full convergence.
    """
    genders = ["male", "female", "neutral"]
    results = {}
    for g in genders:
        if verbose:
            print(f"  probing gender={g} ({probe_iters} iters, pose+shape)…")
        fit = fit_smplx(
            target_verts, gender=g, iters=probe_iters,
            optimise_pose=True, device=device, verbose=False,
        )
        results[g] = fit["final_loss"]
        if verbose:
            print(f"    final loss: {fit['final_loss']:.5f}")

    winner = min(results, key=results.get)
    if verbose:
        print(f"  → best fit: {winner} (loss={results[winner]:.5f})")
        sorted_losses = sorted(results.values())
        margin = (sorted_losses[1] - sorted_losses[0]) / sorted_losses[0] * 100
        print(f"    confidence: +{margin:.1f}% better than runner-up")
        if margin < 2.0:
            print(f"    [note] margin is small — scan shape is visually ambiguous")
            print(f"           override with --gender <male|female|neutral> if you know better")
    return winner


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run(obj_path: str,
        gender: str = "auto",
        iters: int = 400,
        optimise_pose: bool = True,
        output_path: Optional[str] = None,
        device: str = "cpu",
        save_fitted_obj: bool = True) -> dict:

    src = Path(obj_path)
    if output_path:
        out_json = Path(output_path)
    else:
        DEFAULT_OUTDIR.mkdir(parents=True, exist_ok=True)
        stem = src.stem.removesuffix("_aligned")
        out_json = DEFAULT_OUTDIR / f"{stem}_smplx_measurements.json"

    print(f"Loading target : {src}")
    target = load_target(str(src))
    target = auto_scale_to_metres(target)
    print(f"  vertices   : {len(target.vertices):,}")
    print(f"  height     : {target.extents[2]:.3f} m")

    # Gender auto-detect: quick probe fit for each gender model, pick best
    if gender == "auto":
        print("\nAuto-detecting gender by probe-fit…")
        gender = detect_gender(target.vertices, probe_iters=220, device=device)
        print(f"  → classified as: {gender}")

    print(f"\nFitting SMPL-X [{gender}, {iters} iters, pose={'on' if optimise_pose else 'off'}]")
    fit = fit_smplx(
        target.vertices, gender=gender, iters=iters,
        optimise_pose=optimise_pose, device=device, verbose=True,
    )

    print("\nExtracting measurements from fitted SMPL-X…")
    measurements = extract_measurements(fit)
    # Pull the internal slice-height block out before writing to JSON so it
    # lives at the top level (not nested inside "measurements").
    slice_z_m = measurements.pop("_slice_z_m", {})

    doc = {
        "source":        src.name,
        "method":        "smplx_fit",
        "gender":        gender,
        "units":         "cm",
        "final_loss":    fit["final_loss"],
        "iterations":    fit["iterations"],
        "betas":         [round(b, 4) for b in fit["betas"]],
        "scale":         round(fit["scale"], 4),
        "measurements":  measurements,
        "slice_z_m":     slice_z_m,   # exact cut Z heights for exploded-view annotator
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"\nMeasurements saved : {out_json}")

    if save_fitted_obj:
        out_obj = out_json.with_suffix(".obj")
        # Export the fitted mesh in the SAME coordinate convention as the
        # aligned scan (Z-up, face -Y). This way when you open both OBJs in
        # the same viewer they line up — body axis matches, facing matches.
        # Measurements were computed from these Z-up coordinates too, so the
        # JSON and the OBJ are fully consistent.
        fitted_mesh = trimesh.Trimesh(
            vertices=fit["vertices"], faces=fit["faces"], process=False
        )
        # Clean OBJ — no placeholder material.mtl / material_0.png
        obj_text = trimesh.exchange.obj.export_obj(
            fitted_mesh,
            include_color=False,
            include_normals=True,
            include_texture=False,
            write_texture=False,
        )
        out_obj.write_text(obj_text, encoding="utf-8")
        print(f"Fitted SMPL-X OBJ  : {out_obj}  (Z-up, matches aligned scan)")

        # Export FBX
        out_fbx = out_json.with_suffix(".fbx")
        try:
            save_fbx_ascii(fit["vertices"], fit["faces"], fit["joints"], fit["weights"], out_fbx)
            print(f"Fitted SMPL-X FBX  : {out_fbx}  (Rigged ASCII, Z-up)")
        except Exception as e:
            print(f"[WARN] FBX export failed: {e}")

    return doc


def main():
    ap = argparse.ArgumentParser(
        description="Fit SMPL-X to an aligned body scan OBJ and extract measurements"
    )
    ap.add_argument("obj", help="Aligned body scan .obj "
                                "(typically output/models/aligned/*_aligned.obj)")
    ap.add_argument("--output", "-o", default=None,
                    help="Output JSON path "
                         "(default: output/models/final/<stem>_smplx_measurements.json)")
    ap.add_argument("--gender", choices=["auto", "neutral", "male", "female"], default="auto",
                    help="SMPL-X gender model to fit (default: auto — runs quick "
                         "probe fits for male/female/neutral and picks the one "
                         "with the lowest Chamfer loss)")
    ap.add_argument("--iters", type=int, default=400,
                    help="Optimisation iterations (default: 400)")
    ap.add_argument("--no-pose", action="store_true",
                    help="Fit shape only, skip body-pose optimisation (faster, less accurate)")
    ap.add_argument("--fast", action="store_true",
                    help="Shorthand for --iters 200 --no-pose")
    ap.add_argument("--device", default="cpu",
                    help="Torch device: cpu or cuda (default: cpu)")
    ap.add_argument("--no-save-obj", action="store_true",
                    help="Don't write the fitted SMPL-X OBJ, only the JSON")
    args = ap.parse_args()

    if args.fast:
        args.iters = 200
        args.no_pose = True

    if not Path(args.obj).exists():
        print(f"[error] file not found: {args.obj}", file=sys.stderr)
        sys.exit(1)

    # Validate the requested gender model file(s) exist
    if args.gender == "auto":
        needed = ["NEUTRAL", "MALE", "FEMALE"]
    else:
        needed = [args.gender.upper()]
    for g in needed:
        fp = SMPLX_MODEL_DIR / "smplx" / f"SMPLX_{g}.npz"
        if not fp.exists():
            print(f"[error] SMPL-X model not found at {fp}", file=sys.stderr)
            sys.exit(1)

    run(
        args.obj,
        gender=args.gender,
        iters=args.iters,
        optimise_pose=not args.no_pose,
        output_path=args.output,
        device=args.device,
        save_fitted_obj=not args.no_save_obj,
    )


if __name__ == "__main__":
    main()
