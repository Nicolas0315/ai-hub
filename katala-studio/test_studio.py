#!/usr/bin/env python3
"""Katala Studio — Test Suite"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from geometry import (
    create_cube, create_sphere, create_cylinder, create_plane, create_torus,
    subdivide, merge_meshes, export_obj, export_fbx_ascii, export_unitypackage,
    Scene, Mesh
)
import tempfile
import os
import json

passed = 0
failed = 0

def test(name, condition, msg=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} — {msg}")

print("═══ Katala Studio Test Suite ═══\n")

# ── Primitives ──
print("── Primitives ──")
cube = create_cube(2.0)
test("cube vertices", cube.vertex_count == 8, f"got {cube.vertex_count}")
test("cube faces", cube.face_count == 6, f"got {cube.face_count}")
test("cube tris", cube.tri_count == 12, f"got {cube.tri_count}")
test("cube bounds", abs(cube.bounds()[0][0] - (-1.0)) < 0.01)
test("cube ks_history", len(cube.ks_history) == 1)
test("cube ks_verdict", cube.ks_history[0].verdict == "VERIFIED")

sphere = create_sphere(1.0, 16, 12)
test("sphere vertices", sphere.vertex_count == 16 * 11 + 2, f"got {sphere.vertex_count}")
test("sphere faces", sphere.face_count > 100, f"got {sphere.face_count}")
test("sphere normals", all(abs(np.linalg.norm(v.normal) - 1.0) < 0.1 for v in sphere.vertices[:10]))

cyl = create_cylinder(1.0, 2.0, 16)
test("cylinder vertices", cyl.vertex_count == 34, f"got {cyl.vertex_count}")
test("cylinder faces", cyl.face_count == 48, f"got {cyl.face_count}")

plane = create_plane(2.0, 2)
test("plane vertices", plane.vertex_count == 16, f"got {plane.vertex_count}")
test("plane y=0", all(abs(v.position[1]) < 0.001 for v in plane.vertices))

torus = create_torus(1.0, 0.3, 24, 12)
test("torus vertices", torus.vertex_count == 24 * 12, f"got {torus.vertex_count}")
test("torus faces", torus.face_count == 24 * 12, f"got {torus.face_count}")

# ── Modifiers ──
print("\n── Modifiers ──")
sub_cube = subdivide(cube, 1)
test("subdivide increases verts", sub_cube.vertex_count > cube.vertex_count,
     f"{sub_cube.vertex_count} <= {cube.vertex_count}")
test("subdivide increases faces", sub_cube.face_count > cube.face_count,
     f"{sub_cube.face_count} <= {cube.face_count}")
test("subdivide ks_history", len(sub_cube.ks_history) > 0)

merged = merge_meshes([cube, sphere], "CubeSphere")
test("merge vertex count", merged.vertex_count == cube.vertex_count + sphere.vertex_count)
test("merge face count", merged.face_count == cube.face_count + sphere.face_count)
test("merge name", merged.name == "CubeSphere")

# ── Exporters ──
print("\n── Exporters ──")
with tempfile.TemporaryDirectory() as tmpdir:
    # OBJ
    obj_path = os.path.join(tmpdir, "test.obj")
    export_obj(cube, obj_path)
    test("obj exists", os.path.exists(obj_path))
    with open(obj_path) as f:
        content = f.read()
    test("obj has vertices", content.count("\nv ") == 8, f"got {content.count('v ')}")
    test("obj has KS score", "KS Quality Score" in content)

    # FBX ASCII
    fbx_path = os.path.join(tmpdir, "test.fbx")
    export_fbx_ascii(cube, fbx_path)
    test("fbx exists", os.path.exists(fbx_path))
    with open(fbx_path) as f:
        fbx_content = f.read()
    test("fbx header", "FBX 7.4.0" in fbx_content)
    test("fbx has vertices", "Vertices:" in fbx_content)
    test("fbx has polygons", "PolygonVertexIndex:" in fbx_content)
    test("fbx has normals", "LayerElementNormal" in fbx_content)
    test("fbx has material", "Material::" in fbx_content)
    test("fbx has KS score", "KS Quality Score" in fbx_content)
    test("fbx > 500 bytes", os.path.getsize(fbx_path) > 500, f"got {os.path.getsize(fbx_path)}")

    # .unitypackage
    unity_path = os.path.join(tmpdir, "test.unitypackage")
    export_unitypackage(sphere, unity_path)
    test("unitypackage exists", os.path.exists(unity_path))
    test("unitypackage > 100 bytes", os.path.getsize(unity_path) > 100)

    # Verify unitypackage structure
    import tarfile
    with tarfile.open(unity_path, 'r:gz') as tar:
        names = tar.getnames()
        test("unitypackage has asset", any("asset" in n and "meta" not in n for n in names))
        test("unitypackage has meta", any("asset.meta" in n for n in names))
        test("unitypackage has pathname", any("pathname" in n for n in names))

    # Scene export
    scene = Scene("TestScene")
    scene.add_mesh(cube)
    scene.add_mesh(sphere)
    scene.add_mesh(cyl)

    scene.export_all_fbx(os.path.join(tmpdir, "fbx_out"))
    test("scene fbx count", len(os.listdir(os.path.join(tmpdir, "fbx_out"))) == 3)

    scene_unity = os.path.join(tmpdir, "scene.unitypackage")
    scene.export_all_unitypackage(scene_unity)
    test("scene unitypackage exists", os.path.exists(scene_unity))

# ── KS Integration ──
print("\n── KS Integration ──")
test("cube ks_quality", 0.8 <= cube.ks_quality_score() <= 1.0,
     f"got {cube.ks_quality_score():.3f}")
test("sphere ks_quality", 0.8 <= sphere.ks_quality_score() <= 1.0)

# After export, cube should have more history entries
test("cube ks_history after export", len(cube.ks_history) >= 2,
     f"got {len(cube.ks_history)}")

# ── Scene Stats ──
print("\n── Scene Stats ──")
scene = Scene("FinalScene")
scene.add_mesh(create_cube())
scene.add_mesh(create_sphere())
scene.add_mesh(create_torus())
stats = scene.stats()
test("scene mesh_count", stats["mesh_count"] == 3)
test("scene total_vertices > 0", stats["total_vertices"] > 0)
test("scene total_triangles > 0", stats["total_triangles"] > 0)
test("scene ks_quality > 0", stats["average_ks_quality"] > 0)
print(f"\n  Scene stats: {json.dumps(stats, indent=2)}")

# ── Summary ──
print(f"\n{'═' * 40}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"  {'ALL PASSED ✓' if failed == 0 else 'SOME FAILED ✗'}")
print(f"{'═' * 40}")

sys.exit(0 if failed == 0 else 1)
