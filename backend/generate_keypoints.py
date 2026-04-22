"""
Galatea Keypoint Converter: MediaPipe → OpenPose BODY_25 JSON

This script detects pose landmarks using MediaPipe and outputs them
in the exact JSON format that SMPLify-X expects (OpenPose BODY_25).

Usage:
    python generate_keypoints.py --input_dir input --data_folder data
"""
import os
import sys
import json
import argparse
import shutil
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# ─── MediaPipe (33 landmarks) → OpenPose BODY_25 (25 keypoints) ──
# OpenPose BODY_25 ordering:
#  0: Nose, 1: Neck (synthetic midpoint), 2: RShoulder, 3: RElbow, 4: RWrist,
#  5: LShoulder, 6: LElbow, 7: LWrist, 8: MidHip (synthetic), 9: RHip,
# 10: RKnee, 11: RAnkle, 12: LHip, 13: LKnee, 14: LAnkle,
# 15: REye, 16: LEye, 17: REar, 18: LEar,
# 19: LBigToe, 20: LSmallToe, 21: LHeel, 22: RBigToe, 23: RSmallToe, 24: RHeel

def mediapipe_to_openpose_body25(mp_landmarks, img_w, img_h):
    """Convert MediaPipe 33 landmarks to OpenPose BODY_25 format.
    
    Returns a flat list: [x0, y0, c0, x1, y1, c1, ..., x24, y24, c24]
    where x,y are pixel coordinates and c is confidence (0-1).
    """
    def get_lm(idx):
        """Get a MediaPipe landmark as (x_px, y_px, confidence)."""
        lm = mp_landmarks[idx]
        return (lm.x * img_w, lm.y * img_h, lm.visibility if hasattr(lm, 'visibility') else 0.9)

    def midpoint(idx1, idx2):
        """Compute the midpoint of two landmarks (for synthetic joints like Neck)."""
        lm1 = get_lm(idx1)
        lm2 = get_lm(idx2)
        return ((lm1[0] + lm2[0]) / 2, (lm1[1] + lm2[1]) / 2, min(lm1[2], lm2[2]))

    # Build the 25 OpenPose keypoints
    openpose_25 = [
        get_lm(0),           #  0: Nose
        midpoint(11, 12),    #  1: Neck (synthetic: midpoint of shoulders)
        get_lm(12),          #  2: Right Shoulder
        get_lm(14),          #  3: Right Elbow
        get_lm(16),          #  4: Right Wrist
        get_lm(11),          #  5: Left Shoulder
        get_lm(13),          #  6: Left Elbow
        get_lm(15),          #  7: Left Wrist
        midpoint(23, 24),    #  8: Mid Hip (synthetic: midpoint of hips)
        get_lm(24),          #  9: Right Hip
        get_lm(26),          # 10: Right Knee
        get_lm(28),          # 11: Right Ankle
        get_lm(23),          # 12: Left Hip
        get_lm(25),          # 13: Left Knee
        get_lm(27),          # 14: Left Ankle
        get_lm(5),           # 15: Right Eye
        get_lm(2),           # 16: Left Eye
        get_lm(8),           # 17: Right Ear
        get_lm(7),           # 18: Left Ear
        get_lm(31),          # 19: Left Big Toe
        get_lm(31),          # 20: Left Small Toe (approx)
        get_lm(29),          # 21: Left Heel
        get_lm(32),          # 22: Right Big Toe
        get_lm(32),          # 23: Right Small Toe (approx)
        get_lm(30),          # 24: Right Heel
    ]

    # Flatten to [x0, y0, c0, x1, y1, c1, ...]
    flat = []
    for (x, y, c) in openpose_25:
        flat.extend([float(x), float(y), float(c)])

    return flat


def generate_keypoints(input_dir, data_folder):
    """Process all images in input_dir, generate OpenPose JSONs in data_folder."""
    
    # Create SMPLify-X expected folder structure
    images_dir = os.path.join(data_folder, "images")
    keypoints_dir = os.path.join(data_folder, "keypoints")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(keypoints_dir, exist_ok=True)

    # Setup MediaPipe
    model_asset_path = os.path.join(os.path.dirname(__file__), 'pose_landmarker.task')
    if not os.path.exists(model_asset_path):
        model_asset_path = 'backend/pose_landmarker.task'

    print(f"[Galatea] Loading MediaPipe model from {model_asset_path}...")
    base_options = python.BaseOptions(model_asset_path=model_asset_path)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        output_segmentation_masks=False)
    detector = vision.PoseLandmarker.create_from_options(options)

    processed = 0
    for file in sorted(os.listdir(input_dir)):
        if not file.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue

        input_path = os.path.join(input_dir, file)
        basename = os.path.splitext(file)[0]

        print(f"[Galatea] Processing {file}...")

        # Copy image to data/images/
        dest_img = os.path.join(images_dir, file)
        shutil.copy2(input_path, dest_img)

        # Detect landmarks
        mp_image = mp.Image.create_from_file(input_path)
        result = detector.detect(mp_image)

        if not result.pose_landmarks:
            print(f"  WARNING: No pose detected in {file}, skipping.")
            continue

        h, w = mp_image.height, mp_image.width

        # Convert to OpenPose format
        pose_keypoints_2d = mediapipe_to_openpose_body25(
            result.pose_landmarks[0], w, h
        )

        # Build OpenPose JSON
        openpose_json = {
            "version": 1.3,
            "people": [{
                "person_id": [-1],
                "pose_keypoints_2d": pose_keypoints_2d,
                "face_keypoints_2d": [],
                "hand_left_keypoints_2d": [],
                "hand_right_keypoints_2d": [],
                "pose_keypoints_3d": [],
                "face_keypoints_3d": [],
                "hand_left_keypoints_3d": [],
                "hand_right_keypoints_3d": []
            }]
        }

        # Save JSON
        json_path = os.path.join(keypoints_dir, f"{basename}_keypoints.json")
        with open(json_path, 'w') as f:
            json.dump(openpose_json, f, indent=2)

        print(f"  Saved keypoints: {json_path}")
        print(f"  Detected {len(result.pose_landmarks[0])} MediaPipe -> 25 OpenPose keypoints")
        processed += 1

    print(f"\n[Galatea] Done! Processed {processed} image(s).")
    print(f"  Images:    {images_dir}")
    print(f"  Keypoints: {keypoints_dir}")
    return processed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate OpenPose keypoints from images using MediaPipe')
    parser.add_argument('--input_dir', type=str, default='input')
    parser.add_argument('--data_folder', type=str, default='data')
    args = parser.parse_args()
    generate_keypoints(args.input_dir, args.data_folder)
