from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import os
import subprocess
import sys
import json
from pathlib import Path
from backend.generate_pdf import generate_pdf

app = Flask(__name__)
CORS(app)

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "input" / "models"
OUTPUT_DIR = ROOT / "output" / "models" / "final"
ALIGNED_DIR = ROOT / "output" / "models" / "aligned"

# Ensure directories exist
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ALIGNED_DIR.mkdir(parents=True, exist_ok=True)

@app.route('/')
def index():
    return send_file(ROOT / 'dashboard.html')

@app.route('/motion_studio.html')
def motion_studio():
    return send_file(ROOT / 'motion_studio.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    gender = request.form.get('gender', 'auto')
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        filename = "uploaded_scan.obj"
        file_path = INPUT_DIR / filename
        file.save(str(file_path))
        
        # Run the pipeline
        # Using sys.executable to ensure we use the right python
        cmd = [sys.executable, str(ROOT / "runfor3dmodel.py"), str(file_path), "--gender", gender, "--no-ui"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(e.stderr)
            return jsonify({"error": "Pipeline failed", "details": e.stderr}), 500
        
        # Paths for output
        # Based on runfor3dmodel.py logic
        aligned_path = ALIGNED_DIR / "uploaded_scan_aligned.obj"
        morphed_path = OUTPUT_DIR / "uploaded_scan_smplx_measurements.obj"
        json_path = OUTPUT_DIR / "uploaded_scan_smplx_measurements.json"
        
        measurements = {}
        pdf_url = ""
        if json_path.exists():
            with open(json_path, 'r') as f:
                measurements = json.load(f)
            
            # Generate PDF
            pdf_out = generate_pdf(str(json_path), str(OUTPUT_DIR), "uploaded_scan_smplx", gender)
            if pdf_out:
                pdf_url = "/files/output/models/final/uploaded_scan_smplx_measurements.pdf"
        
        # Return both solid and exploded versions for the frontend to toggle
        morphed_path = "/files/output/models/final/uploaded_scan_smplx_measurements.obj"
        fbx_path = "/files/output/models/final/uploaded_scan_smplx_measurements.fbx"
        exploded_path = "/files/output/models/final/uploaded_scan_smplx_measurements_exploded.obj"
        
        # Filter technical slice data from measurements to keep UI clean
        ui_measurements = {k: v for k, v in measurements.items() if k != 'slice_z_m'}
        
        return jsonify({
            "status": "success",
            "raw_scan": "/files/input/models/uploaded_scan.obj",
            "og_scan": "/files/output/models/aligned/uploaded_scan_aligned.obj",
            "morphed_model": morphed_path,
            "fbx_model": fbx_path,
            "exploded_model": exploded_path,
            "pdf_model": pdf_url,
            "measurements": ui_measurements
        })

@app.route('/files/<path:path>')
def send_files(path):
    return send_from_directory(ROOT, path)

if __name__ == '__main__':
    # Start the server on 5001 to avoid conflicts
    app.run(port=5001, debug=True)
