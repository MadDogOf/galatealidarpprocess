"""
Galatea Backend - SMPLify-X Inspired Fitting Engine
=====================================================
Ports the key techniques from the official SMPLify-X paper into a clean,
modern pipeline that works on CPU with Python 3.14.

Key techniques from SMPLify-X:
  - Perspective camera model with estimated focal length
  - Multi-stage optimization (camera init → body fitting)
  - Angle prior (prevents extreme elbow/knee bending) 
  - L2 shape prior (keeps body proportions reasonable)
  - GMoF robust loss (reduces impact of noisy detections)
  - LBFGS optimizer (same as the paper)
  - Camera translation initialization via limb-length ratio

Reference: "Expressive Body Capture: 3D Hands, Face, and Body from a Single Image"
           Pavlakos et al., CVPR 2019
"""
import os
import sys
import argparse
import json
import numpy as np
import torch
import torch.nn as nn
import smplx
import trimesh
from tqdm import tqdm
from datetime import datetime


# ─── SMPLify-X Angle Prior ──────────────────────────────────────
# Directly ported from smplify-x/smplifyx/prior.py
# Prevents extreme rotation of elbows and knees
class SMPLifyAnglePrior(nn.Module):
    def __init__(self, dtype=torch.float32):
        super().__init__()
        # Joint indices for: left elbow(55), right elbow(58), left knee(12), right knee(15)
        angle_prior_idxs = torch.tensor([55, 58, 12, 15], dtype=torch.long)
        self.register_buffer('angle_prior_idxs', angle_prior_idxs)
        angle_prior_signs = torch.tensor([1, -1, -1, -1], dtype=dtype)
        self.register_buffer('angle_prior_signs', angle_prior_signs)

    def forward(self, pose, with_global_pose=False):
        angle_prior_idxs = self.angle_prior_idxs - (not with_global_pose) * 3
        return torch.exp(pose[:, angle_prior_idxs] * self.angle_prior_signs).pow(2)


# ─── GMoF Robust Error Function ─────────────────────────────────
# From smplify-x/smplifyx/utils.py
# Reduces the influence of outlier keypoints
class GMoF(nn.Module):
    def __init__(self, rho=100):
        super().__init__()
        self.rho2 = rho ** 2

    def forward(self, residual):
        squared_res = residual ** 2
        return (self.rho2 * squared_res) / (squared_res + self.rho2)


# ─── Perspective Camera ─────────────────────────────────────────
# From smplify-x/smplifyx/camera.py
class PerspectiveCamera(nn.Module):
    def __init__(self, focal_length=5000.0, center=None, dtype=torch.float32):
        super().__init__()
        self.focal_length = focal_length
        self.register_buffer('center', torch.zeros(2, dtype=dtype) if center is None else center)
        self.translation = nn.Parameter(torch.zeros(1, 3, dtype=dtype))

    def forward(self, points):
        """Project 3D points to 2D using a perspective camera."""
        # points: [B, N, 3]
        # Apply camera translation
        translated = points + self.translation.unsqueeze(1)
        # Perspective projection
        proj = translated[:, :, :2] / translated[:, :, 2:3]
        proj = self.focal_length * proj + self.center
        return proj


# ─── OpenPose BODY_25 to SMPL-X Joint Mapping ───────────────────
# From smplify-x/smplifyx/utils.py (smpl_to_openpose function)
# Maps OpenPose BODY_25 indices to SMPL-X joint indices
OPENPOSE_TO_SMPLX = np.array([
    55,  # 0:  Nose        -> SMPLX nose
    12,  # 1:  Neck        -> SMPLX neck
    17,  # 2:  RShoulder   -> SMPLX right_shoulder
    19,  # 3:  RElbow      -> SMPLX right_elbow
    21,  # 4:  RWrist      -> SMPLX right_wrist
    16,  # 5:  LShoulder   -> SMPLX left_shoulder
    18,  # 6:  LElbow      -> SMPLX left_elbow
    20,  # 7:  LWrist      -> SMPLX left_wrist
     0,  # 8:  MidHip      -> SMPLX pelvis
     2,  # 9:  RHip        -> SMPLX right_hip
     5,  # 10: RKnee       -> SMPLX right_knee
     8,  # 11: RAnkle      -> SMPLX right_ankle
     1,  # 12: LHip        -> SMPLX left_hip
     4,  # 13: LKnee       -> SMPLX left_knee
     7,  # 14: LAnkle      -> SMPLX left_ankle
    57,  # 15: REye        -> SMPLX reye
    56,  # 16: LEye        -> SMPLX leye
    59,  # 17: REar        -> SMPLX right_ear
    58,  # 18: LEar        -> SMPLX left_ear
    -1,  # 19: LBigToe     -> (not mapped)
    -1,  # 20: LSmallToe   -> (not mapped)
    -1,  # 21: LHeel       -> (not mapped)
    -1,  # 22: RBigToe     -> (not mapped)
    -1,  # 23: RSmallToe   -> (not mapped)
    -1,  # 24: RHeel       -> (not mapped)
], dtype=np.int32)

# Body limb edges for camera translation initialization.
# Tuple: (OpenPose_idx_A, OpenPose_idx_B, SMPLX_idx_A, SMPLX_idx_B)
# The 2D diff uses OpenPose indices into the filtered gt_joints array;
# the 3D diff must use SMPLX joint indices into the model output.
# SMPLX body joints: L_Hip=1, R_Hip=2, L_Knee=4, R_Knee=5,
#   L_Shoulder=16, R_Shoulder=17, L_Elbow=18, R_Elbow=19
BODY_EDGES = [
    (5, 12, 16,  1),  # LShoulder-LHip
    (2,  9, 17,  2),  # RShoulder-RHip
    (5,  6, 16, 18),  # LShoulder-LElbow
    (2,  3, 17, 19),  # RShoulder-RElbow
    (12, 13,  1,  4),  # LHip-LKnee
    (9, 10,  2,  5),  # RHip-RKnee
]

# Joints to ignore during fitting (Neck=1, RHip=9, LHip=12).
# Both OpenPose and MediaPipe place hip landmarks on the outer pelvis bone,
# but SMPL-X hip joints are anatomical hip sockets (medial, inside the body).
# Forcing the fit to match the wider 2D hip detections rotates the pelvis
# forward and bends the knees, causing a crouched pose. Leave hips unconstrained.
JOINTS_TO_IGNORE = [1, 9, 12]

# Face keypoints are unreliable from MediaPipe on dynamic poses — downweight
FACE_KEYPOINTS = [15, 16, 17, 18]
FACE_KP_WEIGHT = 0.1


def load_openpose_keypoints(json_path):
    """Load OpenPose BODY_25 keypoints from JSON file."""
    with open(json_path) as f:
        data = json.load(f)

    if not data.get('people'):
        return None

    person = data['people'][0]
    kp = np.array(person['pose_keypoints_2d'], dtype=np.float32).reshape(-1, 3)
    return kp  # [25, 3] = x, y, confidence


@torch.no_grad()
def guess_camera_translation(model, gt_joints, focal_length=5000.0, dtype=torch.float32):
    """Initialize camera translation from limb-length ratios.
    Ported from smplify-x/smplifyx/fitting.py: guess_init()
    """
    output = model(return_verts=False, return_full_pose=False)
    joints_3d = output.joints

    diff3d, diff2d = [], []
    for (o_a, o_b, s_a, s_b) in BODY_EDGES:
        diff3d.append(joints_3d[:, s_a] - joints_3d[:, s_b])
        diff2d.append(gt_joints[:, o_a] - gt_joints[:, o_b])

    diff3d = torch.stack(diff3d, dim=1)
    diff2d = torch.stack(diff2d, dim=1)

    length_2d = diff2d.pow(2).sum(dim=-1).sqrt()
    length_3d = diff3d.pow(2).sum(dim=-1).sqrt()

    height2d = length_2d.mean(dim=1)
    height3d = length_3d.mean(dim=1)

    est_d = focal_length * (height3d / height2d)

    batch_size = joints_3d.shape[0]
    init_t = torch.stack([
        torch.zeros(batch_size, dtype=dtype),
        torch.zeros(batch_size, dtype=dtype),
        est_d.to(dtype=dtype)
    ], dim=1)
    return init_t


class GalateaSMPLifyX:
    """SMPLify-X inspired fitter with multi-stage optimization."""

    def __init__(self, model_path, gender='neutral', device='cpu'):
        self.device = torch.device(device)
        self.dtype = torch.float32

        print(f"[Galatea] Loading SMPL-X ({gender}) from {model_path}...")
        self.model = smplx.create(
            model_path,
            model_type='smplx',
            gender=gender,
            use_face_contour=True,
            num_betas=10,
            use_pca=True,
            num_pca_comps=12,
            flat_hand_mean=False,
            ext='npz'
        ).to(self.device)

        # Priors (same as SMPLify-X)
        self.angle_prior = SMPLifyAnglePrior(dtype=self.dtype).to(self.device)
        self.robustifier = GMoF(rho=100).to(self.device)

        # Build the joint mapping (filter out unmapped joints)
        self.valid_mask = OPENPOSE_TO_SMPLX >= 0
        self.smplx_indices = torch.tensor(
            OPENPOSE_TO_SMPLX[self.valid_mask], dtype=torch.long, device=self.device
        )

        # Joint weights: zero out ambiguous joints, downweight noisy face KPs
        joint_weights = np.ones(25, dtype=np.float32)
        for j in JOINTS_TO_IGNORE:
            joint_weights[j] = 0.0
        for j in FACE_KEYPOINTS:
            joint_weights[j] = FACE_KP_WEIGHT
        self.joint_weights = torch.tensor(
            joint_weights[self.valid_mask], dtype=self.dtype, device=self.device
        ).unsqueeze(0).unsqueeze(-1)  # [1, N, 1]

    def fit(self, keypoints_25, img_h, img_w, focal_length=5000.0, maxiters=30):
        """
        Fit SMPL-X to OpenPose BODY_25 keypoints.
        
        Follows the official SMPLify-X 5-stage optimization process.
        """
        # ── Prepare keypoints ──
        kp = keypoints_25.copy()
        gt_joints_full = torch.tensor(kp[:, :2], dtype=self.dtype, device=self.device)
        gt_conf = torch.tensor(kp[:, 2], dtype=self.dtype, device=self.device)

        # Filter to valid joints only
        gt_joints = gt_joints_full[self.valid_mask].unsqueeze(0)  # [1, N, 2]
        conf = gt_conf[self.valid_mask].unsqueeze(0).unsqueeze(-1)  # [1, N, 1]

        # ── Create camera ──
        camera = PerspectiveCamera(
            focal_length=focal_length,
            center=torch.tensor([img_w / 2.0, img_h / 2.0], dtype=self.dtype),
            dtype=self.dtype
        ).to(self.device)

        # ── Initialize camera translation ──
        # Map gt_joints to SMPL-X joint ordering for initialization
        init_t = guess_camera_translation(
            self.model, gt_joints, focal_length=focal_length, dtype=self.dtype
        )
        with torch.no_grad():
            camera.translation[:] = init_t.view_as(camera.translation)
            camera.center[:] = torch.tensor([img_w, img_h], dtype=self.dtype) * 0.5

        camera.translation.requires_grad = True

        # ── Stage 1: Camera initialization ──
        # Optimize only camera translation + global orientation
        print("[Galatea] Stage 1/5: Camera initialization...")
        self.model.reset_params()
        camera_opt_params = [camera.translation, self.model.global_orient]

        # Use LBFGS with strong Wolfe line search (same as paper)
        camera_optimizer = torch.optim.LBFGS(
            camera_opt_params, lr=1.0, max_iter=20, line_search_fn='strong_wolfe'
        )

        data_weight = 1000.0 / img_h
        for step in range(maxiters):
            def camera_closure():
                camera_optimizer.zero_grad()
                output = self.model(return_verts=False)
                proj = camera(output.joints[:, self.smplx_indices])
                loss = data_weight * torch.sum(
                    self.joint_weights * self.robustifier(gt_joints - proj)
                )
                loss.backward()
                return loss
            loss = camera_optimizer.step(camera_closure)

        print(f"  Camera init loss: {loss.item():.4f}")

        # ── Stages 2-5: Body fitting ──
        # Multi-stage with decreasing prior weights (same schedule as paper)
        body_prior_weights = [4.04e2, 4.04e2, 57.4, 4.78, 4.78]
        shape_weights = [1e2, 5e1, 1e1, 5e0, 5e0]
        bending_weights = [w * 3.17 for w in body_prior_weights]

        for stage_idx, (bp_w, sh_w, bn_w) in enumerate(
            zip(body_prior_weights, shape_weights, bending_weights)
        ):
            print(f"[Galatea] Stage {stage_idx + 1}/5: Body fitting (prior_w={bp_w:.1f})...")

            body_params = [p for p in self.model.parameters() if p.requires_grad]
            body_params.append(camera.translation)

            body_optimizer = torch.optim.LBFGS(
                body_params, lr=1.0, max_iter=20, line_search_fn='strong_wolfe'
            )

            for step in range(maxiters):
                def body_closure():
                    body_optimizer.zero_grad()
                    output = self.model(return_verts=False, return_full_pose=True)

                    # Joint reprojection loss (with robust error + confidence)
                    proj = camera(output.joints[:, self.smplx_indices])
                    joint_diff = self.robustifier(gt_joints - proj)
                    joint_loss = data_weight * torch.sum(
                        (self.joint_weights * conf) ** 2 * joint_diff
                    )

                    # Body pose prior (L2 on pose parameters)
                    pose_prior_loss = bp_w * torch.sum(output.body_pose ** 2)

                    # Shape prior (L2 on betas)
                    shape_loss = sh_w * torch.sum(output.betas ** 2)

                    # Angle prior (prevents extreme elbow/knee bending)
                    body_pose_full = output.full_pose[:, 3:66]
                    angle_loss = bn_w * torch.sum(
                        self.angle_prior(body_pose_full)
                    )

                    # Head/neck prior — prevents the optimizer twisting the head
                    # to chase noisy eye/ear detections from MediaPipe.
                    # body_pose layout (21 joints × 3, joint numbering from SMPL):
                    #   neck=joint12 → body_pose[:,33:36]
                    #   head=joint15 → body_pose[:,42:45]
                    neck_pose = output.body_pose[:, 33:36]
                    head_pose = output.body_pose[:, 42:45]
                    head_prior_loss = 50.0 * (
                        torch.sum(neck_pose ** 2) + torch.sum(head_pose ** 2)
                    )

                    total_loss = joint_loss + pose_prior_loss + shape_loss + angle_loss + head_prior_loss
                    total_loss.backward()
                    return total_loss

                loss = body_optimizer.step(body_closure)

            print(f"  Stage {stage_idx + 1} loss: {loss.item():.4f}")

        # ── Final mesh output ──
        with torch.no_grad():
            final_output = self.model(return_verts=True)

        return final_output

    def save_obj(self, output, filename):
        vertices = output.vertices.detach().cpu().numpy().squeeze()
        faces = self.model.faces
        mesh = trimesh.Trimesh(vertices, faces, process=False)
        # Rotate 180° around X axis (SMPLify-X convention for display)
        rot = trimesh.transformations.rotation_matrix(np.radians(180), [1, 0, 0])
        mesh.apply_transform(rot)
        mesh.export(filename)
        file_size_kb = os.path.getsize(filename) / 1024
        print(f"[Galatea] Model saved: {filename} ({file_size_kb:.0f} KB)")


def main():
    parser = argparse.ArgumentParser(description='Galatea SMPLify-X Fitting')
    parser.add_argument('--data_folder', type=str, default='data',
                        help='Folder with images/ and keypoints/ subfolders')
    parser.add_argument('--output_dir', type=str, default='output')
    parser.add_argument('--model_dir', type=str, default='smplx_models/models')
    parser.add_argument('--focal_length', type=float, default=5000.0)
    parser.add_argument('--gender', type=str, default='neutral',
                        choices=['neutral', 'female', 'male'],
                        help='SMPL-X body model. Use female/male for accurate proportions.')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"[Galatea] Using device: {device}")
    fitter = GalateaSMPLifyX(args.model_dir, gender=args.gender, device=device)

    images_dir = os.path.join(args.data_folder, 'images')
    keypoints_dir = os.path.join(args.data_folder, 'keypoints')

    if not os.path.exists(images_dir) or not os.path.exists(keypoints_dir):
        print(f"ERROR: Expected {images_dir} and {keypoints_dir} folders.")
        print("Run generate_keypoints.py first!")
        sys.exit(1)

    import cv2
    for file in sorted(os.listdir(images_dir)):
        if not file.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue

        basename = os.path.splitext(file)[0]
        img_path = os.path.join(images_dir, file)
        json_path = os.path.join(keypoints_dir, f"{basename}_keypoints.json")

        if not os.path.exists(json_path):
            print(f"SKIP: No keypoints for {file}")
            continue

        print(f"\n{'='*60}")
        print(f"Processing: {file}")
        print(f"{'='*60}")

        img = cv2.imread(img_path)
        h, w = img.shape[:2]

        keypoints = load_openpose_keypoints(json_path)
        if keypoints is None:
            print(f"SKIP: No people in {json_path}")
            continue

        result = fitter.fit(keypoints, h, w, focal_length=args.focal_length)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(args.output_dir, f"{basename}_{ts}.obj")
        fitter.save_obj(result, output_path)


if __name__ == '__main__':
    main()
