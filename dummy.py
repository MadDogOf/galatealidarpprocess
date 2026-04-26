import numpy as np
from pathlib import Path
from backend.smplx_measure import save_fbx_ascii
v = np.zeros((10,3))
f = np.zeros((2,3))
j = np.zeros((55,3))
w = np.zeros((10,55))
out = Path('output/models/final/uploaded_scan_smplx_measurements.fbx')
out.parent.mkdir(parents=True, exist_ok=True)
save_fbx_ascii(v, f, j, w, out)
