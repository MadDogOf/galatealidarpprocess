"""
Galatea Runner - Orchestrates the full image-to-3D pipeline.

Usage:
    python run.py                        # Full pipeline: install deps → keypoints → fit → output
    python run.py --view                 # Launch 3D viewer in browser
    python run.py --skip-deps            # Skip dependency installation
    python run.py --gender female        # Use female SMPL-X body model (also: male, neutral)
"""
import os
import sys
import subprocess
import platform


def run_command(command):
    """Runs a shell command and prints its output."""
    print(f"$ {command}")
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='')
        process.wait()
        return process.returncode
    except Exception as e:
        print(f"Error: {e}")
        return 1


def main():
    print("=" * 60)
    print("  Galatea: Digital Wardrobe - Image to 3D Pipeline")
    print("=" * 60)
    print(f"System: {platform.system()} | Python: {sys.version.split()[0]}")

    skip_deps = "--skip-deps" in sys.argv

    # Optional --gender passthrough
    gender = "neutral"
    if "--gender" in sys.argv:
        idx = sys.argv.index("--gender")
        if idx + 1 < len(sys.argv):
            gender = sys.argv[idx + 1]

    # 1. Install dependencies
    if not skip_deps:
        print("\n[Step 1/3] Checking dependencies...")
        if os.path.exists("requirements.txt"):
            run_command(f"{sys.executable} -m pip install -r requirements.txt -q")
        else:
            print("Warning: requirements.txt not found!")
    else:
        print("\n[Step 1/3] Skipping dependency installation.")

    # 2. Check for View Mode
    if "--view" in sys.argv:
        print("\n[Viewer] Launching 3D Viewer...")
        print("Open http://localhost:8000/viewer.html in your browser.")
        try:
            subprocess.Popen([sys.executable, "-m", "http.server", "8000"])
            import webbrowser
            webbrowser.open("http://localhost:8000/viewer.html")
            print("Press Ctrl+C to stop.")
            while True:
                pass
        except KeyboardInterrupt:
            print("\nViewer stopped.")
            return

    # 3. Generate OpenPose keypoints from input images using MediaPipe
    print("\n[Step 2/3] Generating keypoints (MediaPipe → OpenPose format)...")
    rc = run_command(
        f"{sys.executable} backend/generate_keypoints.py "
        f"--input_dir input/images --data_folder data"
    )
    if rc != 0:
        print("ERROR: Keypoint generation failed!")
        return

    # 4. Run SMPLify-X fitting
    print(f"\n[Step 3/3] Fitting SMPL-X model (gender={gender})...")
    rc = run_command(
        f"{sys.executable} backend/main.py "
        f"--data_folder data --output_dir output/images --model_dir smplx_models/models "
        f"--gender {gender}"
    )
    if rc != 0:
        print("ERROR: SMPL-X fitting failed!")
        return

    print("\n" + "=" * 60)
    print("  Done! Check the output/images/ folder for your 3D models.")
    print("=" * 60)


if __name__ == "__main__":
    main()
