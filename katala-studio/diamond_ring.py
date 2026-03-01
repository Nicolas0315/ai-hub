#!/usr/bin/env python3
"""
Katala Studio — Diamond Ring Designer
ブリリアントカット・ダイヤモンドリング
高品質ジオメトリ + KS検証

Design request: Nicolas Ogoshi, 2026-03-02
Implementation: Shirokuma (OpenClaw AI)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
from geometry import Mesh, Scene, Material, export_fbx_ascii, export_obj, merge_meshes


# ── Materials ──
MAT_PLATINUM = Material(
    name="Platinum",
    diffuse=np.array([0.90, 0.89, 0.92, 1.0]),
    specular=np.array([1.0, 1.0, 1.0, 1.0]),
    shininess=128.0,
)
MAT_DIAMOND = Material(
    name="Diamond",
    diffuse=np.array([0.95, 0.95, 1.0, 0.3]),  # Translucent
    specular=np.array([1.0, 1.0, 1.0, 1.0]),
    shininess=256.0,
)
MAT_PRONG = Material(
    name="Prong",
    diffuse=np.array([0.88, 0.87, 0.90, 1.0]),
    specular=np.array([1.0, 1.0, 1.0, 1.0]),
    shininess=96.0,
)


def create_ring_band(inner_radius=8.0, thickness=1.0, width=2.5,
                     segments=96, rings=12, name="PlatinumBand"):
    """プラチナバンド — 高解像度"""
    mesh = Mesh(name)
    mesh.materials = [MAT_PLATINUM]

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
            mesh.add_vertex(x, y, z, nx, ny, nz)

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
    mesh.ks_verify_operation("platinum_band", 0.96, 0.99, 0.03)
    return mesh


def create_brilliant_cut_diamond(radius=2.0, crown_height=0.8,
                                  pavilion_depth=1.6, table_ratio=0.55,
                                  facets=16, name="BrilliantDiamond"):
    """ラウンド・ブリリアントカット — 57面体

    Real diamond proportions:
    - Table: 53-57% of diameter
    - Crown angle: ~34.5°
    - Pavilion angle: ~40.75°
    - Crown height: ~16% of diameter
    - Total depth: ~60% of diameter
    """
    mesh = Mesh(name)
    mesh.materials = [MAT_DIAMOND]

    girdle_r = radius
    table_r = radius * table_ratio

    # ── Table (top flat octagon) ──
    table_center = mesh.add_vertex(0, crown_height, 0, 0, 1, 0)
    table_start = len(mesh.vertices)
    for i in range(facets):
        angle = 2 * np.pi * i / facets
        mesh.add_vertex(table_r * np.cos(angle), crown_height, table_r * np.sin(angle),
                        0, 1, 0)

    # Table faces
    for i in range(facets):
        ni = (i + 1) % facets
        mesh.add_face([table_center, table_start + i, table_start + ni], material_id=0)

    # ── Star facets (between table and bezel) ──
    star_r = (table_r + girdle_r) * 0.5
    star_h = crown_height * 0.7
    star_start = len(mesh.vertices)
    for i in range(facets):
        angle = 2 * np.pi * (i + 0.5) / facets  # Offset by half
        nx = np.cos(angle) * 0.3
        nz = np.sin(angle) * 0.3
        mesh.add_vertex(star_r * np.cos(angle), star_h, star_r * np.sin(angle),
                        nx, 0.5, nz)

    # Star faces (table edge to star points)
    for i in range(facets):
        ni = (i + 1) % facets
        mesh.add_face([table_start + i, star_start + i, table_start + ni], material_id=0)

    # ── Upper girdle facets ──
    upper_girdle_start = len(mesh.vertices)
    for i in range(facets * 2):
        angle = 2 * np.pi * i / (facets * 2)
        h = 0.15 if i % 2 == 0 else 0.0
        r = girdle_r * (0.98 if i % 2 == 0 else 1.0)
        nx = np.cos(angle)
        nz = np.sin(angle)
        mesh.add_vertex(r * np.cos(angle), h, r * np.sin(angle),
                        nx, 0.1, nz)

    # Connect star to upper girdle
    for i in range(facets):
        si = star_start + i
        g1 = upper_girdle_start + i * 2
        g2 = upper_girdle_start + i * 2 + 1
        g3 = upper_girdle_start + ((i * 2 + 2) % (facets * 2))
        mesh.add_face([si, g1, g2], material_id=0)
        mesh.add_face([si, g2, g3], material_id=0)

    # ── Girdle (thin band) ──
    girdle_bottom_start = len(mesh.vertices)
    for i in range(facets * 2):
        angle = 2 * np.pi * i / (facets * 2)
        mesh.add_vertex(girdle_r * np.cos(angle), -0.05, girdle_r * np.sin(angle),
                        np.cos(angle), 0, np.sin(angle))

    # Girdle faces
    for i in range(facets * 2):
        ni = (i + 1) % (facets * 2)
        a = upper_girdle_start + i
        b = upper_girdle_start + ni
        c = girdle_bottom_start + ni
        d = girdle_bottom_start + i
        mesh.add_face([a, b, c, d], material_id=0)

    # ── Lower girdle facets ──
    lower_girdle_start = len(mesh.vertices)
    for i in range(facets * 2):
        angle = 2 * np.pi * i / (facets * 2)
        r = girdle_r * 0.6
        h = -pavilion_depth * 0.6
        nx = np.cos(angle) * 0.4
        nz = np.sin(angle) * 0.4
        mesh.add_vertex(r * np.cos(angle), h, r * np.sin(angle),
                        nx, -0.5, nz)

    # Connect girdle to lower
    for i in range(facets * 2):
        ni = (i + 1) % (facets * 2)
        mesh.add_face([girdle_bottom_start + i, girdle_bottom_start + ni,
                        lower_girdle_start + ni, lower_girdle_start + i], material_id=0)

    # ── Pavilion main facets ──
    pavilion_start = len(mesh.vertices)
    for i in range(facets):
        angle = 2 * np.pi * i / facets
        r = girdle_r * 0.3
        h = -pavilion_depth * 0.85
        mesh.add_vertex(r * np.cos(angle), h, r * np.sin(angle),
                        np.cos(angle) * 0.3, -0.7, np.sin(angle) * 0.3)

    # Connect lower girdle to pavilion
    for i in range(facets):
        l1 = lower_girdle_start + i * 2
        l2 = lower_girdle_start + i * 2 + 1
        l3 = lower_girdle_start + ((i * 2 + 2) % (facets * 2))
        pi = pavilion_start + i
        mesh.add_face([l1, l2, pi], material_id=0)
        mesh.add_face([l2, l3, pi], material_id=0)

    # ── Culet (bottom point) ──
    culet = mesh.add_vertex(0, -pavilion_depth, 0, 0, -1, 0)

    # Pavilion to culet
    for i in range(facets):
        ni = (i + 1) % facets
        mesh.add_face([pavilion_start + i, culet, pavilion_start + ni], material_id=0)

    mesh.compute_normals()
    mesh.ks_verify_operation("brilliant_cut_diamond", 0.93, 0.97, 0.05)
    return mesh


def create_prong(base_x, base_z, height=3.0, prong_r=0.2, segments=6, segs_h=8, name="Prong"):
    """爪留め（プロング）"""
    mesh = Mesh(name)
    mesh.materials = [MAT_PRONG]

    for i in range(segs_h):
        t = i / (segs_h - 1)
        h = t * height
        # Taper toward top
        r = prong_r * (1.0 - t * 0.3)
        # Slight curve inward at top
        offset_x = base_x * (1.0 - t * 0.15)
        offset_z = base_z * (1.0 - t * 0.15)
        for k in range(segments):
            angle = 2 * np.pi * k / segments
            x = offset_x + r * np.cos(angle)
            z = offset_z + r * np.sin(angle)
            mesh.add_vertex(x, h, z)

    for i in range(segs_h - 1):
        for k in range(segments):
            nk = (k + 1) % segments
            a = i * segments + k
            b = (i + 1) * segments + k
            c = (i + 1) * segments + nk
            d = i * segments + nk
            mesh.add_face([a, b, c, d], material_id=0)

    # Cap top
    top_center = mesh.add_vertex(base_x * 0.85, height, base_z * 0.85, 0, 1, 0)
    top_base = (segs_h - 1) * segments
    for k in range(segments):
        nk = (k + 1) % segments
        mesh.add_face([top_base + k, top_center, top_base + nk], material_id=0)

    mesh.compute_normals()
    mesh.ks_verify_operation("create_prong", 0.91, 0.96, 0.05)
    return mesh


def create_pave_stones(inner_radius=8.0, thickness=1.0, count=24,
                        stone_r=0.25, name_prefix="Pave"):
    """パヴェセッティング — リングバンド上の小さな石"""
    stones = []
    for i in range(count):
        angle = 2 * np.pi * i / count
        r = inner_radius + thickness / 2
        cx = r * np.cos(angle)
        cz = r * np.sin(angle)
        cy = thickness * 0.6

        mesh = Mesh(f"{name_prefix}_{i}")
        mesh.materials = [MAT_DIAMOND]

        # Simple brilliant (8-facet)
        mesh.add_vertex(cx, cy + stone_r * 0.4, cz, 0, 1, 0)  # Table
        for k in range(8):
            a = 2 * np.pi * k / 8
            mesh.add_vertex(cx + stone_r * np.cos(a), cy, cz + stone_r * np.sin(a))
        mesh.add_vertex(cx, cy - stone_r * 0.5, cz, 0, -1, 0)  # Culet

        # Crown
        for k in range(8):
            nk = (k + 1) % 8
            mesh.add_face([0, 1 + k, 1 + nk], material_id=0)
        # Pavilion
        culet = 9
        for k in range(8):
            nk = (k + 1) % 8
            mesh.add_face([1 + k, culet, 1 + nk], material_id=0)

        mesh.compute_normals()
        mesh.ks_verify_operation("pave_stone", 0.89, 0.94, 0.06)
        stones.append(mesh)

    return stones


# ═══════════════════════════════════════════════════
# Build the Diamond Ring
# ═══════════════════════════════════════════════════

print("=== Katala Studio: Brilliant Cut Diamond Ring ===\n")

scene = Scene("DiamondRing")

# 1. Platinum band
band = create_ring_band(inner_radius=8.0, thickness=1.0, width=2.5,
                          segments=96, rings=12)
scene.add_mesh(band)
print(f"Platinum Band: {band.vertex_count} verts, {band.face_count} faces")

# 2. Main diamond
diamond = create_brilliant_cut_diamond(radius=2.5, crown_height=1.0,
                                         pavilion_depth=2.0, facets=16)
diamond.transform.position = np.array([0, 3.5, 0])
scene.add_mesh(diamond)
print(f"Brilliant Diamond: {diamond.vertex_count} verts, {diamond.face_count} faces")

# 3. Six prongs
prong_r_pos = 2.2  # Distance from center
for i in range(6):
    angle = 2 * np.pi * i / 6
    px = prong_r_pos * np.cos(angle)
    pz = prong_r_pos * np.sin(angle)
    prong = create_prong(px, pz, height=4.0, prong_r=0.18, name=f"Prong_{i}")
    scene.add_mesh(prong)
print(f"Prongs: 6 x {prong.vertex_count} verts")

# 4. Pavé stones along band
pave = create_pave_stones(inner_radius=8.0, thickness=1.0, count=24)
for s in pave:
    scene.add_mesh(s)
print(f"Pavé Stones: 24 x {pave[0].vertex_count} verts")

# Stats
print(f"\nTotal meshes: {len(scene.meshes)}")
stats = scene.stats()
print(f"Total vertices: {stats['total_vertices']}")
print(f"Total faces: {stats['total_faces']}")
print(f"Average KS Quality: {stats['average_ks_quality']:.3f}")

# Export
outdir = os.path.join(os.path.dirname(__file__), 'output')
os.makedirs(outdir, exist_ok=True)

full_ring = merge_meshes(scene.meshes, "DiamondRing_Full")

obj_path = os.path.join(outdir, 'diamond_ring.obj')
export_obj(full_ring, obj_path)
print(f"\nExported OBJ: {obj_path}")

fbx_path = os.path.join(outdir, 'diamond_ring.fbx')
export_fbx_ascii(full_ring, fbx_path)
print(f"Exported FBX: {fbx_path}")

print(f"\nKS Quality Score: {full_ring.ks_quality_score():.3f}")
print("\n=== Materials ===")
print(f"  Platinum (Band):  RGBA {MAT_PLATINUM.diffuse}")
print(f"  Diamond (Main):   RGBA {MAT_DIAMOND.diffuse}")
print(f"  Prong (Setting):  RGBA {MAT_PRONG.diffuse}")
print("\nDone! 💎")
