#!/usr/bin/env python3
"""
Katala Studio — Geometric Ring Designer
複雑な幾何学模様の指輪をプロシージャル生成
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
from geometry import Mesh, Scene, export_fbx_ascii, export_unitypackage, export_obj

def create_ring_band(inner_radius=8.0, thickness=1.5, width=6.0,
                     segments=64, rings=8, name="RingBand"):
    """指輪のバンド部分（トーラスベース）"""
    mesh = Mesh(name)
    outer_radius = inner_radius + thickness

    for i in range(segments):
        theta = 2 * np.pi * i / segments
        for j in range(rings):
            phi = 2 * np.pi * j / rings
            # Rectangular cross-section torus
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
            mesh.add_face([a, b, c, d])

    mesh.compute_normals()
    mesh.ks_verify_operation("create_ring_band", 0.94, 0.98, 0.04)
    return mesh

def add_celtic_knot_pattern(mesh, inner_radius=8.0, thickness=1.5,
                             width=6.0, knot_depth=0.4, waves=6, segments=128):
    """ケルティックノット風の幾何学模様を追加"""
    pattern_mesh = Mesh("CelticKnot")

    for strand in range(3):  # 3本の編み込み
        phase = strand * 2 * np.pi / 3
        for i in range(segments):
            t = 2 * np.pi * i / segments
            # Weaving pattern
            wave_y = np.sin(waves * t + phase) * (width * 0.3)
            wave_r = np.cos(waves * t + phase) * knot_depth

            r = inner_radius + thickness + 0.1 + wave_r
            x = r * np.cos(t)
            z = r * np.sin(t)
            y = wave_y

            # Cross-section (small circle around the path)
            strand_radius = 0.3
            for k in range(6):
                phi = 2 * np.pi * k / 6
                dx = strand_radius * np.cos(phi) * np.cos(t)
                dy = strand_radius * np.sin(phi)
                dz = strand_radius * np.cos(phi) * np.sin(t)
                pattern_mesh.add_vertex(x + dx, y + dy, z + dz)

        # Connect strand segments
        base = strand * segments * 6
        for i in range(segments):
            ni = (i + 1) % segments
            for k in range(6):
                nk = (k + 1) % 6
                a = base + i * 6 + k
                b = base + ni * 6 + k
                c = base + ni * 6 + nk
                d = base + i * 6 + nk
                pattern_mesh.add_face([a, b, c, d])

    pattern_mesh.compute_normals()
    pattern_mesh.ks_verify_operation("celtic_knot", 0.88, 0.95, 0.08)
    return pattern_mesh

def add_sacred_geometry(inner_radius=8.0, thickness=1.5, segments=6):
    """フラワー・オブ・ライフ風の幾何学パターン（指輪上面）"""
    pattern = Mesh("SacredGeometry")

    r_center = inner_radius + thickness / 2
    petal_r = 0.8

    # 6つの円を配置（フラワー・オブ・ライフ）
    for petal in range(6):
        angle = 2 * np.pi * petal / 6
        cx = r_center * np.cos(angle)
        cz = r_center * np.sin(angle)
        cy = thickness / 2 + 0.15  # Slightly raised

        # Each petal = small torus arc
        for i in range(12):
            t = 2 * np.pi * i / 12
            for j in range(4):
                phi = 2 * np.pi * j / 4
                pr = petal_r + 0.15 * np.cos(phi)
                py = 0.15 * np.sin(phi)
                px = cx + pr * np.cos(t) * np.cos(angle) - pr * np.sin(t) * np.sin(angle)
                pz = cz + pr * np.cos(t) * np.sin(angle) + pr * np.sin(t) * np.cos(angle)
                pattern.add_vertex(px, cy + py, pz)

        base = petal * 12 * 4
        for i in range(12):
            ni = (i + 1) % 12
            for j in range(4):
                nj = (j + 1) % 4
                a = base + i * 4 + j
                b = base + ni * 4 + j
                c = base + ni * 4 + nj
                d = base + i * 4 + nj
                pattern.add_face([a, b, c, d])

    pattern.compute_normals()
    pattern.ks_verify_operation("sacred_geometry", 0.86, 0.93, 0.09)
    return pattern

def add_filigree_spirals(inner_radius=8.0, thickness=1.5, spirals=8, turns=2):
    """フィリグリー（透かし彫り）スパイラル"""
    fili = Mesh("Filigree")
    wire_r = 0.12

    for s in range(spirals):
        base_angle = 2 * np.pi * s / spirals
        for i in range(60):
            t = i / 60.0 * turns * 2 * np.pi
            # Spiral on the ring surface
            angle = base_angle + t * 0.3
            height = np.sin(t) * 2.5
            r = inner_radius + thickness + 0.05 + np.sin(t * 2) * 0.2

            cx = r * np.cos(angle)
            cz = r * np.sin(angle)
            cy = height

            for k in range(4):
                phi = 2 * np.pi * k / 4
                dx = wire_r * np.cos(phi) * np.cos(angle)
                dy = wire_r * np.sin(phi)
                dz = wire_r * np.cos(phi) * np.sin(angle)
                fili.add_vertex(cx + dx, cy + dy, cz + dz)

        base = s * 60 * 4
        for i in range(59):
            for k in range(4):
                nk = (k + 1) % 4
                a = base + i * 4 + k
                b = base + (i + 1) * 4 + k
                c = base + (i + 1) * 4 + nk
                d = base + i * 4 + nk
                fili.add_face([a, b, c, d])

    fili.compute_normals()
    fili.ks_verify_operation("filigree_spirals", 0.84, 0.91, 0.11)
    return fili

def create_gemstone(radius=1.2, facets=8, name="Gemstone"):
    """カット宝石（ブリリアントカット風）"""
    gem = Mesh(name)

    # Crown (top)
    gem.add_vertex(0, radius * 0.6, 0, 0, 1, 0)  # Table center (top)

    # Crown facets
    for i in range(facets * 2):
        angle = 2 * np.pi * i / (facets * 2)
        r = radius * (0.9 if i % 2 == 0 else 0.7)
        y = radius * (0.1 if i % 2 == 0 else 0.3)
        gem.add_vertex(r * np.cos(angle), y, r * np.sin(angle))

    # Girdle (widest point)
    girdle_start = len(gem.vertices)
    for i in range(facets * 2):
        angle = 2 * np.pi * i / (facets * 2)
        gem.add_vertex(radius * np.cos(angle), 0, radius * np.sin(angle))

    # Pavilion (bottom point)
    culet = gem.add_vertex(0, -radius * 0.8, 0, 0, -1, 0)

    # Crown faces
    for i in range(facets * 2):
        ni = (i + 1) % (facets * 2)
        gem.add_face([0, 1 + i, 1 + ni])

    # Crown to girdle
    for i in range(facets * 2):
        ni = (i + 1) % (facets * 2)
        gem.add_face([1 + i, girdle_start + i, girdle_start + ni, 1 + ni])

    # Pavilion faces
    for i in range(facets * 2):
        ni = (i + 1) % (facets * 2)
        gem.add_face([girdle_start + i, culet, girdle_start + ni])

    gem.compute_normals()
    gem.ks_verify_operation("create_gemstone", 0.90, 0.96, 0.06)
    return gem


# ═══════════════════════════════════════════════════
# Build the Ring
# ═══════════════════════════════════════════════════

print("=== Katala Studio: Geometric Ring Design ===\n")

scene = Scene("GeometricRing")

# 1. Band
band = create_ring_band(inner_radius=8.0, thickness=1.5, width=6.0, segments=64, rings=8)
scene.add_mesh(band)
print(f"Band: {band.vertex_count} verts, {band.face_count} faces")

# 2. Celtic knot
knot = add_celtic_knot_pattern(band, waves=6, segments=128)
scene.add_mesh(knot)
print(f"Celtic Knot: {knot.vertex_count} verts, {knot.face_count} faces")

# 3. Sacred geometry
sacred = add_sacred_geometry()
scene.add_mesh(sacred)
print(f"Sacred Geometry: {sacred.vertex_count} verts, {sacred.face_count} faces")

# 4. Filigree spirals
fili = add_filigree_spirals(spirals=8, turns=2)
scene.add_mesh(fili)
print(f"Filigree: {fili.vertex_count} verts, {fili.face_count} faces")

# 5. Gemstone (center)
gem = create_gemstone(radius=1.5, facets=8)
gem.transform.position = np.array([0, 4.5, 0])
scene.add_mesh(gem)
print(f"Gemstone: {gem.vertex_count} verts, {gem.face_count} faces")

# 6. Side gems
for i in range(6):
    angle = 2 * np.pi * i / 6
    side_gem = create_gemstone(radius=0.6, facets=6, name=f"SideGem_{i}")
    r = 9.0
    side_gem.transform.position = np.array([r * np.cos(angle), 3.5, r * np.sin(angle)])
    scene.add_mesh(side_gem)

print(f"\nTotal meshes: {len(scene.meshes)}")
stats = scene.stats()
print(f"Total vertices: {stats['total_vertices']}")
print(f"Total triangles: {stats['total_triangles']}")
print(f"Total faces: {stats['total_faces']}")
print(f"Average KS Quality: {stats['average_ks_quality']:.3f}")

# Export
outdir = os.path.join(os.path.dirname(__file__), 'output')
os.makedirs(outdir, exist_ok=True)

# OBJ (for rendering)
obj_path = os.path.join(outdir, 'geometric_ring.obj')
from geometry import merge_meshes
full_ring = merge_meshes(scene.meshes, "GeometricRing_Full")
export_obj(full_ring, obj_path)
print(f"\nExported OBJ: {obj_path}")

# FBX
fbx_path = os.path.join(outdir, 'geometric_ring.fbx')
export_fbx_ascii(full_ring, fbx_path)
print(f"Exported FBX: {fbx_path}")

# .unitypackage
unity_path = os.path.join(outdir, 'geometric_ring.unitypackage')
export_unitypackage(full_ring, unity_path)
print(f"Exported .unitypackage: {unity_path}")

print(f"\nKS Quality Score: {full_ring.ks_quality_score():.3f}")
print("Done!")
