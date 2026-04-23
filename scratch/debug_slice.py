import trimesh
import os

mesh_path = 'output/models/final/your_scan_smplx_measurements.obj'
if not os.path.exists(mesh_path):
    print(f"File {mesh_path} not found")
    exit(1)

mesh = trimesh.load(mesh_path)
print(f"Mesh loaded: {len(mesh.vertices)} vertices")
print(f"Bounds: {mesh.bounds}")

z = 0.0821
print(f"Testing slice at z={z}")

# Try below
below = mesh.slice_plane(plane_origin=[0, 0, z], plane_normal=[0, 0, -1])
if below is None:
    print("Below slice returned None")
else:
    print(f"Below vertices: {len(below.vertices)}")

# Try above
above = mesh.slice_plane(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
if above is None:
    print("Above slice returned None")
else:
    print(f"Above vertices: {len(above.vertices)}")
