#!/usr/bin/env python3
"""
Test Shape Recognition on all Katala Studio models
3 approaches × 3 models = comprehensive validation
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import json
import time
import numpy as np
from geometry import Mesh, export_obj

# Import shape recognition
from shape_recognition import classify_mesh, classify_shape, extract_features


def build_test_ring():
    """Quick ring mesh for testing"""
    mesh = Mesh("TestRing")
    segs, rings = 48, 8
    inner_r, thick, width = 8.0, 1.2, 3.0
    for i in range(segs):
        theta = 2*np.pi*i/segs
        for j in range(rings):
            phi = 2*np.pi*j/rings
            r = inner_r + (thick/2)*(1+np.cos(phi))
            y = (width/2)*np.sin(phi)
            mesh.add_vertex(r*np.cos(theta), y, r*np.sin(theta))
    for i in range(segs):
        ni = (i+1)%segs
        for j in range(rings):
            nj = (j+1)%rings
            mesh.add_face([i*rings+j, ni*rings+j, ni*rings+nj, i*rings+nj])
    mesh.compute_normals()
    return mesh


def build_test_sphere():
    """Quick sphere mesh"""
    mesh = Mesh("TestSphere")
    segs, rngs = 16, 12
    r = 5.0
    mesh.add_vertex(0, r, 0)
    for j in range(1, rngs):
        phi = np.pi*j/rngs
        for i in range(segs):
            theta = 2*np.pi*i/segs
            mesh.add_vertex(r*np.sin(phi)*np.cos(theta), r*np.cos(phi), r*np.sin(phi)*np.sin(theta))
    mesh.add_vertex(0, -r, 0)
    for i in range(segs):
        ni = (i+1)%segs
        mesh.add_face([0, 1+i, 1+ni])
    for j in range(rngs-2):
        for i in range(segs):
            ni = (i+1)%segs
            mesh.add_face([1+j*segs+i, 1+(j+1)*segs+i, 1+(j+1)*segs+ni, 1+j*segs+ni])
    bot = len(mesh.vertices)-1
    lr = 1+(rngs-2)*segs
    for i in range(segs):
        ni = (i+1)%segs
        mesh.add_face([bot, lr+ni, lr+i])
    mesh.compute_normals()
    return mesh


def build_test_humanoid():
    """Simple humanoid (stacked cylinders)"""
    mesh = Mesh("TestHumanoid")
    SCALE = 0.01
    segs = 10

    def add_cylinder(cx, y_bot, y_top, r, s=segs):
        base = len(mesh.vertices)
        rings = 4
        for j in range(rings+1):
            t = j/rings
            y = (y_bot + t*(y_top-y_bot))*SCALE
            for i in range(s):
                a = 2*np.pi*i/s
                mesh.add_vertex(cx*SCALE + r*SCALE*np.cos(a), y, r*SCALE*np.sin(a))
        for j in range(rings):
            for i in range(s):
                ni = (i+1)%s
                mesh.add_face([base+j*s+i, base+j*s+ni, base+(j+1)*s+ni, base+(j+1)*s+i])

    # Torso
    add_cylinder(0, 85, 145, 14)
    # Head
    add_cylinder(0, 156, 179, 9)
    # Left leg
    add_cylinder(-8, 0, 85, 5)
    # Right leg
    add_cylinder(8, 0, 85, 5)
    # Left arm
    add_cylinder(-20, 100, 145, 4)
    # Right arm
    add_cylinder(20, 100, 145, 4)

    mesh.compute_normals()
    return mesh


# ═══════════════════════════════════════════════════
# Run Tests
# ═══════════════════════════════════════════════════

print("=" * 60)
print("Katala Studio — Shape Recognition Test Suite")
print("3 Approaches × 3 Models")
print("=" * 60)

test_models = {
    "Ring": build_test_ring(),
    "Sphere": build_test_sphere(),
    "Humanoid": build_test_humanoid(),
}

outdir = os.path.join(os.path.dirname(__file__), 'output')

for name, mesh in test_models.items():
    print(f"\n{'─' * 50}")
    print(f"Testing: {name} ({mesh.vertex_count} verts, {mesh.face_count} faces)")
    print(f"{'─' * 50}")

    # Check if rendered image exists
    image_map = {
        "Ring": "clover_ring_studio.png",
        "Sphere": "diamond_ring_studio.png",
        "Humanoid": "avatar_studio.png",
    }
    img_path = os.path.join(outdir, image_map.get(name, ""))
    use_image = img_path if os.path.exists(img_path) else None

    t0 = time.time()
    result = classify_mesh(mesh, rendered_image_path=use_image)
    elapsed = time.time() - t0

    # Print results
    print(f"\n  [Approach 1] KS Geometric Classification:")
    geo = result["geometric"]
    print(f"    Predicted: {geo['predicted']} (confidence: {geo['confidence']:.4f})")
    top3 = sorted(geo["scores"].items(), key=lambda x: -x[1])[:3]
    for s, sc in top3:
        bar = "█" * int(sc * 30)
        print(f"      {s:12s} {sc:.4f} {bar}")

    if "clip" in result and "error" not in result["clip"]:
        print(f"\n  [Approach 2] CLIP Visual Verification:")
        clip = result["clip"]
        print(f"    Predicted: {clip['predicted']} (confidence: {clip['confidence']:.4f})")
        top3_clip = sorted(clip["scores"].items(), key=lambda x: -x[1])[:3]
        for s, sc in top3_clip:
            bar = "█" * int(sc * 30)
            print(f"      {s:12s} {sc:.4f} {bar}")
    elif "clip" in result:
        print(f"\n  [Approach 2] CLIP: {result['clip'].get('error', 'skipped')}")
    else:
        print(f"\n  [Approach 2] CLIP: No rendered image available")

    print(f"\n  [Approach 3] Mesh Feature Analysis:")
    feat = result["features"]
    topo = feat["topology"]
    surf = feat["surface"]
    sym = feat["symmetry"]
    ind = feat["shape_indicators"]
    print(f"    Topology:  genus={topo['genus']}, closed={topo['is_closed']}, holes={topo['has_holes']}")
    print(f"    Surface:   isotropy={surf['normal_isotropy']:.3f}, convexity={surf['convexity_ratio']:.3f}, compactness={surf['compactness']:.4f}")
    print(f"    Symmetry:  X={sym['x_mirror']:.3f}, Y={sym['y_mirror']:.3f}, Z={sym['z_mirror']:.3f}")
    print(f"    Indicators: {json.dumps(ind)}")

    print(f"\n  [ENSEMBLE] → {result['ensemble']['predicted'].upper()} "
          f"(confidence: {result['ensemble']['confidence']:.4f})")
    print(f"  Methods: {', '.join(result['ensemble']['methods_used'])}")
    print(f"  Time: {elapsed:.2f}s")

print(f"\n{'=' * 60}")
print("All tests complete!")
