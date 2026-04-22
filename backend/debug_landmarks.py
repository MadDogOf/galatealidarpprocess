"""
Galatea Debug Tool: Annotate input image with MediaPipe landmarks.
This script visualizes exactly what MediaPipe detects, so we can verify 
the keypoints are correct before feeding them to SMPL-X.
"""
import os
import sys
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# All 33 MediaPipe Pose Landmarks with human-readable names
LANDMARK_NAMES = {
    0: "Nose", 1: "L Eye Inner", 2: "L Eye", 3: "L Eye Outer",
    4: "R Eye Inner", 5: "R Eye", 6: "R Eye Outer",
    7: "L Ear", 8: "R Ear", 9: "Mouth L", 10: "Mouth R",
    11: "L Shoulder", 12: "R Shoulder", 13: "L Elbow", 14: "R Elbow",
    15: "L Wrist", 16: "R Wrist", 17: "L Pinky", 18: "R Pinky",
    19: "L Index", 20: "R Index", 21: "L Thumb", 22: "R Thumb",
    23: "L Hip", 24: "R Hip", 25: "L Knee", 26: "R Knee",
    27: "L Ankle", 28: "R Ankle", 29: "L Heel", 30: "R Heel",
    31: "L Foot Index", 32: "R Foot Index"
}

# The joints we actually use for SMPL-X fitting (highlighted in green, others in gray)
SMPLX_MAPPED_INDICES = {11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28}

# Skeleton connections for drawing limbs
CONNECTIONS = [
    (11, 13), (13, 15),  # Left arm
    (12, 14), (14, 16),  # Right arm
    (11, 12),            # Shoulders
    (23, 24),            # Hips
    (11, 23), (12, 24),  # Torso
    (23, 25), (25, 27),  # Left leg
    (24, 26), (26, 28),  # Right leg
]


def run_debug(input_path, output_dir):
    # Setup MediaPipe
    model_asset_path = os.path.join(os.path.dirname(__file__), 'pose_landmarker.task')
    if not os.path.exists(model_asset_path):
        model_asset_path = 'backend/pose_landmarker.task'

    print(f"Loading MediaPipe model from {model_asset_path}...")
    base_options = python.BaseOptions(model_asset_path=model_asset_path)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        output_segmentation_masks=False)
    detector = vision.PoseLandmarker.create_from_options(options)

    # Load and detect
    mp_image = mp.Image.create_from_file(input_path)
    result = detector.detect(mp_image)

    if not result.pose_landmarks:
        print(f"ERROR: No pose detected in {input_path}!")
        return

    print(f"Pose detected! Found {len(result.pose_landmarks[0])} landmarks.")

    # Load image with OpenCV for annotation
    img = cv2.imread(input_path)
    h, w = img.shape[:2]
    
    # Create a copy for clean annotation
    annotated = img.copy()

    # Collect landmark pixel coordinates
    landmarks_px = []
    for lm in result.pose_landmarks[0]:
        px = int(lm.x * w)
        py = int(lm.y * h)
        landmarks_px.append((px, py))

    # Draw skeleton connections first (so dots go on top)
    for (i, j) in CONNECTIONS:
        pt1 = landmarks_px[i]
        pt2 = landmarks_px[j]
        cv2.line(annotated, pt1, pt2, (255, 255, 100), 2, cv2.LINE_AA)

    # Draw each landmark
    for idx, (px, py) in enumerate(landmarks_px):
        if idx in SMPLX_MAPPED_INDICES:
            # GREEN = used for SMPL-X fitting
            color = (0, 255, 0)
            radius = 8
        else:
            # GRAY = detected but not used
            color = (150, 150, 150)
            radius = 4

        cv2.circle(annotated, (px, py), radius, color, -1, cv2.LINE_AA)
        cv2.circle(annotated, (px, py), radius, (0, 0, 0), 1, cv2.LINE_AA)

        # Add label
        label = LANDMARK_NAMES.get(idx, str(idx))
        label_color = (0, 255, 0) if idx in SMPLX_MAPPED_INDICES else (200, 200, 200)
        cv2.putText(annotated, label, (px + 10, py - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(annotated, label, (px + 10, py - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, label_color, 1, cv2.LINE_AA)

    # Add legend
    legend_y = 30
    cv2.putText(annotated, "LEGEND:", (10, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    legend_y += 25
    cv2.circle(annotated, (20, legend_y - 5), 6, (0, 255, 0), -1)
    cv2.putText(annotated, "Used for SMPL-X fitting", (35, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    legend_y += 20
    cv2.circle(annotated, (20, legend_y - 5), 4, (150, 150, 150), -1)
    cv2.putText(annotated, "Detected but not used", (35, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    # Print landmark data to console for debugging
    print("\n--- Detected Landmarks (pixel coordinates) ---")
    print(f"{'Idx':<5} {'Name':<15} {'X (px)':<10} {'Y (px)':<10} {'Z (depth)':<12} {'Used?'}")
    print("-" * 65)
    for idx, lm in enumerate(result.pose_landmarks[0]):
        px = lm.x * w
        py = lm.y * h
        pz = lm.z * w
        used = "YES <<<" if idx in SMPLX_MAPPED_INDICES else ""
        name = LANDMARK_NAMES.get(idx, "?")
        print(f"{idx:<5} {name:<15} {px:<10.1f} {py:<10.1f} {pz:<12.4f} {used}")

    # Save annotated image
    os.makedirs(output_dir, exist_ok=True)
    basename = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{basename}_landmarks.png")
    cv2.imwrite(output_path, annotated)
    print(f"\nAnnotated image saved to: {output_path}")

    return result


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else "input/sample.jpg"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output"
    run_debug(input_path, output_dir)
