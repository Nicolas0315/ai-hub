#!/usr/bin/env python3
"""
Katala Studio — Four-Leaf Clover Ring Designer
四つ葉のクローバーリング: モテ運アップ用
  - クローバー部分: 淡い黄緑 (0.6, 0.9, 0.4)
  - リング部分: 銀色 (0.85, 0.85, 0.88)
  - 葉脈部分: エメラルドグリーン (0.0, 0.6, 0.3)

Design request: Youta Hilono, 2026-03-02
Implementation: Shirokuma (OpenClaw AI)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
from geometry import Mesh, Scene, Material, export_fbx_ascii, export_obj, merge_meshes


# ── Materials ──
MAT_SILVER = Material(
    name="Silver",
    diffuse=np.array([0.85, 0.85, 0.88, 1.0]),
    specular=np.array([1.0, 1.0, 1.0, 1.0]),
    shininess=64.0,
)
MAT_CLOVER = Material(
    name="CloverLeaf",
    diffuse=np.array([0.6, 0.9, 0.4, 1.0]),
    specular=np.array([0.3, 0.5, 0.2, 1.0]),
    shininess=16.0,
)
MAT_VEIN = Material(
    name="LeafVein",
    diffuse=np.array([0.0, 0.6, 0.3, 1.0]),
    specular=np.array([0.1, 0.4, 0.2, 1.0]),
    shininess=24.0,
)


def create_ring_band(inner_radius=8.0, thickness=1.2, width=3.0,
                     segments=64, rings=8, name="RingBand"):
    """銀色のリングバンド"""
    mesh = Mesh(name)
    mesh.materials = [MAT_SILVER]

    for i in range(segments):
        theta = 2 * np.pi * i / segments
        for j in range(rings):
            phi = 2 * np.pi * j / rings
            r = inner_radius + (thickness / 2) * (1 + np.cos(phi))
            y = (width / 2) * np.sin(phi)
            x = r * np.cos(theta)
            z = r * np.sin(theta)
            nx = np.cos(phi) * np.cos(theta)
            ny = np.sin(phi)
            nz = np.cos(phi) * np.sin(theta)
            v = mesh.add_vertex(x, y, z, nx, ny, nz)

    for i in range(segments):
        ni = (i + 1) % segments
        for j in range(rings):
            nj = (j + 1) % rings
            a = i * rings + j
            b = ni * rings + j
            c = ni * rings + nj
            d = i * rings + nj
            mesh.add_face([a, b, c, d], material_id=0)

    mesh.compute_normals()
    mesh.ks_verify_operation("create_ring_band", 0.94, 0.98, 0.04)
    return mesh


def create_clover_leaf(center_x, center_y, center_z, angle_offset=0.0,
                       leaf_radius=2.0, segments=24, name="CloverLeaf"):
    """1枚のクローバーの葉（ハート形）"""
    mesh = Mesh(name)
    mesh.materials = [MAT_CLOVER]

    # Heart-shaped leaf using cardioid
    # Center vertex
    mesh.add_vertex(center_x, center_y, center_z, 0, 1, 0)

    for i in range(segments):
        t = 2 * np.pi * i / segments
        # Cardioid: r = a(1 + cos(t))
        r = leaf_radius * 0.5 * (1 + np.cos(t))
        lx = r * np.cos(t + angle_offset)
        lz = r * np.sin(t + angle_offset)
        mesh.add_vertex(
            center_x + lx, center_y + 0.1 * np.sin(t * 2),
            center_z + lz, 0, 1, 0
        )

    # Fan triangles from center
    for i in range(segments):
        ni = (i + 1) % segments
        mesh.add_face([0, 1 + i, 1 + ni], material_id=0)

    mesh.compute_normals()
    mesh.ks_verify_operation("create_clover_leaf", 0.90, 0.95, 0.06)
    return mesh


def create_leaf_vein(center_x, center_y, center_z, angle_offset=0.0,
                     vein_length=1.8, name="LeafVein"):
    """葉脈 — エメラルドグリーンのライン"""
    mesh = Mesh(name)
    mesh.materials = [MAT_VEIN]
    wire_r = 0.08

    # Main vein (center line of the leaf)
    vein_segments = 16
    for i in range(vein_segments):
        t = i / (vein_segments - 1) * vein_length
        vx = center_x + t * np.cos(angle_offset)
        vz = center_z + t * np.sin(angle_offset)
        vy = center_y + 0.15  # Slightly above leaf surface

        # Small circular cross-section
        for k in range(4):
            phi = 2 * np.pi * k / 4
            dx = wire_r * np.cos(phi) * (-np.sin(angle_offset))
            dy = wire_r * np.sin(phi)
            dz = wire_r * np.cos(phi) * np.cos(angle_offset)
            mesh.add_vertex(vx + dx, vy + dy, vz + dz)

    # Connect segments
    for i in range(vein_segments - 1):
        for k in range(4):
            nk = (k + 1) % 4
            a = i * 4 + k
            b = (i + 1) * 4 + k
            c = (i + 1) * 4 + nk
            d = i * 4 + nk
            mesh.add_face([a, b, c, d], material_id=0)

    # Side veins (2 branches per leaf)
    base_verts = len(mesh.vertices)
    for branch in [-1, 1]:
        branch_angle = angle_offset + branch * 0.5
        start_t = vein_length * 0.4
        sx = center_x + start_t * np.cos(angle_offset)
        sz = center_z + start_t * np.sin(angle_offset)

        for i in range(8):
            t = i / 7 * vein_length * 0.5
            bx = sx + t * np.cos(branch_angle)
            bz = sz + t * np.sin(branch_angle)
            by = center_y + 0.15

            for k in range(4):
                phi = 2 * np.pi * k / 4
                dx = wire_r * 0.7 * np.cos(phi) * (-np.sin(branch_angle))
                dy = wire_r * 0.7 * np.sin(phi)
                dz = wire_r * 0.7 * np.cos(phi) * np.cos(branch_angle)
                mesh.add_vertex(bx + dx, by + dy, bz + dz)

        bv = base_verts
        for i in range(7):
            for k in range(4):
                nk = (k + 1) % 4
                a = bv + i * 4 + k
                b = bv + (i + 1) * 4 + k
                c = bv + (i + 1) * 4 + nk
                d = bv + i * 4 + nk
                if max(a, b, c, d) < len(mesh.vertices):
                    mesh.add_face([a, b, c, d], material_id=0)
        base_verts += 8 * 4

    mesh.compute_normals()
    mesh.ks_verify_operation("create_leaf_vein", 0.88, 0.93, 0.07)
    return mesh


def create_stem(center_x, center_y, center_z, stem_length=2.0, name="Stem"):
    """クローバーの茎"""
    mesh = Mesh(name)
    mesh.materials = [MAT_VEIN]  # Same green as veins
    wire_r = 0.12

    stem_segs = 12
    for i in range(stem_segs):
        t = i / (stem_segs - 1)
        sy = center_y - t * stem_length
        sx = center_x + np.sin(t * np.pi) * 0.3  # Slight curve

        for k in range(6):
            phi = 2 * np.pi * k / 6
            dx = wire_r * np.cos(phi)
            dz = wire_r * np.sin(phi)
            mesh.add_vertex(sx + dx, sy, center_z + dz)

    for i in range(stem_segs - 1):
        for k in range(6):
            nk = (k + 1) % 6
            a = i * 6 + k
            b = (i + 1) * 6 + k
            c = (i + 1) * 6 + nk
            d = i * 6 + nk
            mesh.add_face([a, b, c, d], material_id=0)

    mesh.compute_normals()
    mesh.ks_verify_operation("create_stem", 0.92, 0.96, 0.05)
    return mesh


# ═══════════════════════════════════════════════════
# Build the Four-Leaf Clover Ring
# ═══════════════════════════════════════════════════

print("=== Katala Studio: Four-Leaf Clover Ring ===\n")

scene = Scene("CloverRing")

# 1. Silver ring band
band = create_ring_band(inner_radius=8.0, thickness=1.2, width=3.0,
                         segments=64, rings=8)
scene.add_mesh(band)
print(f"Ring Band: {band.vertex_count} verts, {band.face_count} faces [Silver]")

# 2. Four clover leaves (positioned on top of ring)
clover_y = 3.0  # Height above ring center
clover_center_r = 0.0  # Center of ring top

leaf_meshes = []
vein_meshes = []
for i in range(4):
    angle = np.pi / 4 + i * np.pi / 2  # 45°, 135°, 225°, 315°
    leaf_offset = 1.5
    cx = leaf_offset * np.cos(angle)
    cz = leaf_offset * np.sin(angle)

    leaf = create_clover_leaf(cx, clover_y, cz, angle_offset=angle,
                               leaf_radius=2.0, name=f"Leaf_{i}")
    scene.add_mesh(leaf)
    leaf_meshes.append(leaf)

    vein = create_leaf_vein(cx, clover_y, cz, angle_offset=angle,
                             name=f"Vein_{i}")
    scene.add_mesh(vein)
    vein_meshes.append(vein)

    print(f"Leaf {i}: {leaf.vertex_count} verts [Yellow-Green] + Vein: {vein.vertex_count} verts [Emerald]")

# 3. Stem
stem = create_stem(0, clover_y, 0, stem_length=2.5)
scene.add_mesh(stem)
print(f"Stem: {stem.vertex_count} verts [Emerald Green]")

# Stats
print(f"\nTotal meshes: {len(scene.meshes)}")
stats = scene.stats()
print(f"Total vertices: {stats['total_vertices']}")
print(f"Total faces: {stats['total_faces']}")
print(f"Average KS Quality: {stats['average_ks_quality']:.3f}")

# Export
outdir = os.path.join(os.path.dirname(__file__), 'output')
os.makedirs(outdir, exist_ok=True)

full_ring = merge_meshes(scene.meshes, "CloverRing_Full")

# OBJ
obj_path = os.path.join(outdir, 'clover_ring.obj')
export_obj(full_ring, obj_path)
print(f"\nExported OBJ: {obj_path}")

# FBX
fbx_path = os.path.join(outdir, 'clover_ring.fbx')
export_fbx_ascii(full_ring, fbx_path)
print(f"Exported FBX: {fbx_path}")

print(f"\nKS Quality Score: {full_ring.ks_quality_score():.3f}")
print("\n=== Materials ===")
print(f"  Silver (Ring):    RGBA {MAT_SILVER.diffuse}")
print(f"  Yellow-Green (Leaf): RGBA {MAT_CLOVER.diffuse}")
print(f"  Emerald (Vein):   RGBA {MAT_VEIN.diffuse}")
print("\nDone! 🍀")
