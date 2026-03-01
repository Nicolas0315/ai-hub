#!/usr/bin/env python3
"""
Katala Studio — Androgynous Male Avatar (VRChat-ready)
中性男性アバター: 179cm / 50kg (細身)

Spec:
  Height: 179cm (1.79m in world units)
  Weight: 50kg → BMI 15.6 → extremely slim build
  Style: Androgynous, lean, narrow shoulders, slim waist
  Target: VRChat (FBX export, humanoid rig proportions)

Design request: wival, 2026-03-02
Implementation: Shirokuma (OpenClaw AI)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
from geometry import Mesh, Scene, Material, export_fbx_ascii, export_obj, merge_meshes

# ── Materials ──
MAT_SKIN = Material(
    name="Skin",
    diffuse=np.array([0.92, 0.82, 0.76, 1.0]),
    specular=np.array([0.3, 0.25, 0.22, 1.0]),
    shininess=16.0,
)
MAT_HAIR = Material(
    name="Hair",
    diffuse=np.array([0.12, 0.10, 0.10, 1.0]),
    specular=np.array([0.3, 0.3, 0.35, 1.0]),
    shininess=32.0,
)
MAT_EYES = Material(
    name="Eyes",
    diffuse=np.array([0.25, 0.20, 0.15, 1.0]),
    specular=np.array([0.8, 0.8, 0.9, 1.0]),
    shininess=64.0,
)
MAT_SHIRT = Material(
    name="Shirt",
    diffuse=np.array([0.15, 0.15, 0.18, 1.0]),
    specular=np.array([0.2, 0.2, 0.2, 1.0]),
    shininess=8.0,
)
MAT_PANTS = Material(
    name="Pants",
    diffuse=np.array([0.10, 0.10, 0.12, 1.0]),
    specular=np.array([0.15, 0.15, 0.15, 1.0]),
    shininess=8.0,
)

# ═══════════════════════════════════════════════════
# Body Proportions (179cm / 50kg — androgynous slim)
# Using head-length units (head ≈ 23cm, body ≈ 7.8 heads)
# ═══════════════════════════════════════════════════

TOTAL_HEIGHT = 179.0  # cm
HEAD_LENGTH = 23.0
SCALE = 1.0 / 100.0  # cm → meters

# Y positions (from feet = 0)
FOOT_Y = 0.0
ANKLE_Y = 8.0
KNEE_Y = 46.0
HIP_Y = 85.0
WAIST_Y = 100.0
CHEST_Y = 120.0
SHOULDER_Y = 145.0
NECK_Y = 152.0
CHIN_Y = 156.0
HEAD_TOP_Y = 179.0

# Widths (half-widths, slim build)
SHOULDER_HW = 18.0    # Narrow for androgynous (full width 36cm)
CHEST_HW = 15.0
WAIST_HW = 12.0       # Very slim
HIP_HW = 14.0         # Narrow hips
THIGH_R = 6.5
KNEE_R = 4.5
CALF_R = 4.0
ANKLE_R = 3.2
UPPER_ARM_R = 4.0
FOREARM_R = 3.2
WRIST_R = 2.5
HAND_R = 2.0
NECK_R = 5.0
HEAD_R = 10.0


def create_body_section(y_bottom, y_top, profile_bottom, profile_top,
                         segments=16, rings=4, name="BodySection"):
    """楕円断面を持つボディセクション生成
    profile = (half_width_x, half_depth_z)
    """
    mesh = Mesh(name)
    mesh.materials = [MAT_SKIN]

    for j in range(rings + 1):
        t = j / rings
        y = (y_bottom + t * (y_top - y_bottom)) * SCALE
        hw_x = profile_bottom[0] + t * (profile_top[0] - profile_bottom[0])
        hw_z = profile_bottom[1] + t * (profile_top[1] - profile_bottom[1])

        for i in range(segments):
            angle = 2 * np.pi * i / segments
            x = hw_x * np.cos(angle) * SCALE
            z = hw_z * np.sin(angle) * SCALE
            nx = np.cos(angle) * hw_z
            nz = np.sin(angle) * hw_x
            nl = np.sqrt(nx*nx + nz*nz)
            if nl > 0:
                nx /= nl; nz /= nl
            mesh.add_vertex(x, y, z, nx, 0.1, nz)

    for j in range(rings):
        for i in range(segments):
            ni = (i + 1) % segments
            a = j * segments + i
            b = j * segments + ni
            c = (j + 1) * segments + ni
            d = (j + 1) * segments + i
            mesh.add_face([a, b, c, d], material_id=0)

    mesh.compute_normals()
    return mesh


def create_limb(y_bottom, y_top, r_bottom, r_top, x_offset=0.0,
                segments=12, rings=4, name="Limb"):
    """円断面の四肢（腕・脚）"""
    mesh = Mesh(name)
    mesh.materials = [MAT_SKIN]

    for j in range(rings + 1):
        t = j / rings
        y = (y_bottom + t * (y_top - y_bottom)) * SCALE
        r = (r_bottom + t * (r_top - r_bottom)) * SCALE

        for i in range(segments):
            angle = 2 * np.pi * i / segments
            x = x_offset * SCALE + r * np.cos(angle)
            z = r * np.sin(angle)
            nx = np.cos(angle)
            nz = np.sin(angle)
            mesh.add_vertex(x, y, z, nx, 0, nz)

    for j in range(rings):
        for i in range(segments):
            ni = (i + 1) % segments
            a = j * segments + i
            b = j * segments + ni
            c = (j + 1) * segments + ni
            d = (j + 1) * segments + i
            mesh.add_face([a, b, c, d], material_id=0)

    # Cap bottom
    bottom_center = mesh.add_vertex(x_offset * SCALE, y_bottom * SCALE, 0, 0, -1, 0)
    for i in range(segments):
        ni = (i + 1) % segments
        mesh.add_face([bottom_center, ni, i], material_id=0)

    # Cap top
    top_center = mesh.add_vertex(x_offset * SCALE, y_top * SCALE, 0, 0, 1, 0)
    top_ring = rings * segments
    for i in range(segments):
        ni = (i + 1) % segments
        mesh.add_face([top_center, top_ring + i, top_ring + ni], material_id=0)

    mesh.compute_normals()
    return mesh


def create_head(segments=20, rings=14, name="Head"):
    """頭部 — 楕円体ベース、中性的な顔の形"""
    mesh = Mesh(name)
    mesh.materials = [MAT_SKIN]

    head_center_y = (CHIN_Y + HEAD_TOP_Y) / 2
    head_h = (HEAD_TOP_Y - CHIN_Y) / 2
    head_w = HEAD_R * 0.85  # Slightly narrow for androgynous
    head_d = HEAD_R * 0.9

    # Ellipsoid
    # Top pole
    mesh.add_vertex(0, HEAD_TOP_Y * SCALE, 0, 0, 1, 0)

    for j in range(1, rings):
        phi = np.pi * j / rings
        for i in range(segments):
            theta = 2 * np.pi * i / segments
            # Ellipsoid with narrower jaw
            y_factor = np.cos(phi)
            jaw_narrow = 1.0
            if y_factor < -0.3:  # Lower face → narrower (pointed chin)
                jaw_narrow = 0.75 + 0.25 * (1 + y_factor / 0.7)

            x = head_w * np.sin(phi) * np.cos(theta) * jaw_narrow * SCALE
            y = (head_center_y + head_h * np.cos(phi)) * SCALE
            z = head_d * np.sin(phi) * np.sin(theta) * jaw_narrow * SCALE

            nx = np.sin(phi) * np.cos(theta) * jaw_narrow
            ny = np.cos(phi) * 0.5
            nz = np.sin(phi) * np.sin(theta) * jaw_narrow
            nl = np.sqrt(nx*nx + ny*ny + nz*nz)
            if nl > 0: nx /= nl; ny /= nl; nz /= nl

            mesh.add_vertex(x, y, z, nx, ny, nz)

    # Bottom pole (chin)
    mesh.add_vertex(0, CHIN_Y * SCALE, 0, 0, -1, 0)

    # Top cap
    for i in range(segments):
        ni = (i + 1) % segments
        mesh.add_face([0, 1 + i, 1 + ni], material_id=0)

    # Body
    for j in range(rings - 2):
        for i in range(segments):
            ni = (i + 1) % segments
            r1 = 1 + j * segments
            r2 = 1 + (j + 1) * segments
            mesh.add_face([r1 + i, r2 + i, r2 + ni, r1 + ni], material_id=0)

    # Bottom cap
    bottom = len(mesh.vertices) - 1
    last_ring = 1 + (rings - 2) * segments
    for i in range(segments):
        ni = (i + 1) % segments
        mesh.add_face([bottom, last_ring + ni, last_ring + i], material_id=0)

    mesh.compute_normals()
    mesh.ks_verify_operation("create_head", 0.91, 0.95, 0.06)
    return mesh


def create_eye(x_offset, y, z, radius=1.2, name="Eye"):
    """目 — 球体"""
    mesh = Mesh(name)
    mesh.materials = [MAT_EYES]

    segs, rngs = 10, 8
    mesh.add_vertex(x_offset * SCALE, (y + radius) * SCALE, z * SCALE, 0, 1, 0)

    for j in range(1, rngs):
        phi = np.pi * j / rngs
        for i in range(segs):
            theta = 2 * np.pi * i / segs
            ex = x_offset + radius * np.sin(phi) * np.cos(theta)
            ey = y + radius * np.cos(phi)
            ez = z + radius * np.sin(phi) * np.sin(theta)
            mesh.add_vertex(ex * SCALE, ey * SCALE, ez * SCALE)

    mesh.add_vertex(x_offset * SCALE, (y - radius) * SCALE, z * SCALE, 0, -1, 0)

    for i in range(segs):
        ni = (i + 1) % segs
        mesh.add_face([0, 1 + i, 1 + ni], material_id=0)
    for j in range(rngs - 2):
        for i in range(segs):
            ni = (i + 1) % segs
            r1 = 1 + j * segs
            r2 = 1 + (j + 1) * segs
            mesh.add_face([r1 + i, r2 + i, r2 + ni, r1 + ni], material_id=0)
    bottom = len(mesh.vertices) - 1
    lr = 1 + (rngs - 2) * segs
    for i in range(segs):
        ni = (i + 1) % segs
        mesh.add_face([bottom, lr + ni, lr + i], material_id=0)

    mesh.compute_normals()
    mesh.ks_verify_operation("create_eye", 0.89, 0.94, 0.06)
    return mesh


def create_hair(segments=20, name="Hair"):
    """髪 — 頭部上部を覆うシェル + 中性的なミディアムヘア"""
    mesh = Mesh(name)
    mesh.materials = [MAT_HAIR]

    head_center_y = (CHIN_Y + HEAD_TOP_Y) / 2
    head_h = (HEAD_TOP_Y - CHIN_Y) / 2
    hair_w = HEAD_R * 0.92
    hair_d = HEAD_R * 0.97
    hair_offset = 0.8  # Hair volume offset

    # Top cap (covers upper 60% of head)
    rings_hair = 8
    mesh.add_vertex(0, (HEAD_TOP_Y + hair_offset) * SCALE, 0, 0, 1, 0)

    for j in range(1, rings_hair):
        phi = np.pi * j / (rings_hair * 1.7)  # Only upper portion
        for i in range(segments):
            theta = 2 * np.pi * i / segments
            r_x = (hair_w + hair_offset) * np.sin(phi)
            r_z = (hair_d + hair_offset) * np.sin(phi)
            x = r_x * np.cos(theta) * SCALE
            y = (head_center_y + (head_h + hair_offset) * np.cos(phi)) * SCALE
            z = r_z * np.sin(theta) * SCALE
            mesh.add_vertex(x, y, z)

    # Top cap faces
    for i in range(segments):
        ni = (i + 1) % segments
        mesh.add_face([0, 1 + i, 1 + ni], material_id=0)
    for j in range(rings_hair - 2):
        for i in range(segments):
            ni = (i + 1) % segments
            r1 = 1 + j * segments
            r2 = 1 + (j + 1) * segments
            mesh.add_face([r1 + i, r2 + i, r2 + ni, r1 + ni], material_id=0)

    # Side hair strands (medium length, reaching shoulders)
    hair_base = len(mesh.vertices)
    strand_count = 12
    strand_segs = 8
    wire_r = 1.5

    for s in range(strand_count):
        angle = 2 * np.pi * s / strand_count
        # Only back and sides (not face)
        if -0.8 < np.sin(angle) and np.cos(angle) > 0.3:
            continue  # Skip front-facing strands for androgynous look

        for i in range(strand_segs):
            t = i / (strand_segs - 1)
            start_y = HEAD_TOP_Y * 0.85
            end_y = SHOULDER_Y - 5  # Reaches just above shoulders
            y = (start_y + t * (end_y - start_y)) * SCALE

            # Hair curves outward slightly then falls
            curve = np.sin(t * np.pi) * 2.0
            r = (hair_w + hair_offset + curve) * SCALE
            x = r * np.cos(angle)
            z = r * np.sin(angle)

            for k in range(4):
                phi = 2 * np.pi * k / 4
                dx = wire_r * np.cos(phi) * SCALE * np.cos(angle)
                dy = wire_r * np.sin(phi) * SCALE * 0.3
                dz = wire_r * np.cos(phi) * SCALE * np.sin(angle)
                mesh.add_vertex(x + dx, y + dy, z + dz)

    # Connect hair strands
    actual_strands = 0
    for s in range(strand_count):
        angle = 2 * np.pi * s / strand_count
        if -0.8 < np.sin(angle) and np.cos(angle) > 0.3:
            continue
        base = hair_base + actual_strands * strand_segs * 4
        for i in range(strand_segs - 1):
            for k in range(4):
                nk = (k + 1) % 4
                a = base + i * 4 + k
                b = base + (i + 1) * 4 + k
                c = base + (i + 1) * 4 + nk
                d = base + i * 4 + nk
                if max(a, b, c, d) < len(mesh.vertices):
                    mesh.add_face([a, b, c, d], material_id=0)
        actual_strands += 1

    mesh.compute_normals()
    mesh.ks_verify_operation("create_hair", 0.85, 0.92, 0.09)
    return mesh


# ═══════════════════════════════════════════════════
# Build Avatar
# ═══════════════════════════════════════════════════

print("=== Katala Studio: Androgynous Male Avatar ===")
print(f"    Height: {TOTAL_HEIGHT}cm | Weight: 50kg | BMI: 15.6")
print(f"    Scale: 1 unit = 1 meter\n")

scene = Scene("AndrogynousAvatar")

# ── Torso ──
# Lower torso (hips to waist)
lower_torso = create_body_section(
    HIP_Y, WAIST_Y,
    (HIP_HW, HIP_HW * 0.7), (WAIST_HW, WAIST_HW * 0.65),
    segments=16, rings=4, name="LowerTorso"
)
lower_torso.materials = [MAT_SHIRT]
scene.add_mesh(lower_torso)

# Upper torso (waist to chest)
upper_torso = create_body_section(
    WAIST_Y, CHEST_Y,
    (WAIST_HW, WAIST_HW * 0.65), (CHEST_HW, CHEST_HW * 0.75),
    segments=16, rings=4, name="UpperTorso"
)
upper_torso.materials = [MAT_SHIRT]
scene.add_mesh(upper_torso)

# Shoulders (chest to shoulder)
shoulders = create_body_section(
    CHEST_Y, SHOULDER_Y,
    (CHEST_HW, CHEST_HW * 0.75), (SHOULDER_HW, SHOULDER_HW * 0.6),
    segments=16, rings=4, name="Shoulders"
)
shoulders.materials = [MAT_SHIRT]
scene.add_mesh(shoulders)

# Neck
neck = create_limb(NECK_Y, CHIN_Y, NECK_R, NECK_R * 0.9, x_offset=0,
                    segments=12, rings=3, name="Neck")
scene.add_mesh(neck)

# ── Head ──
head = create_head(segments=20, rings=14)
scene.add_mesh(head)

# Eyes
left_eye = create_eye(-3.5, (CHIN_Y + HEAD_TOP_Y) / 2 + 2.0, HEAD_R * 0.8, radius=1.0, name="LeftEye")
right_eye = create_eye(3.5, (CHIN_Y + HEAD_TOP_Y) / 2 + 2.0, HEAD_R * 0.8, radius=1.0, name="RightEye")
scene.add_mesh(left_eye)
scene.add_mesh(right_eye)

# Hair
hair = create_hair(segments=20)
scene.add_mesh(hair)

# ── Arms ──
for side, sign in [("Left", -1), ("Right", 1)]:
    x_off = sign * SHOULDER_HW

    # Upper arm
    upper_arm = create_limb(
        CHEST_Y, SHOULDER_Y, UPPER_ARM_R, UPPER_ARM_R * 0.9,
        x_offset=x_off, segments=10, rings=4, name=f"{side}UpperArm"
    )
    upper_arm.materials = [MAT_SHIRT]
    scene.add_mesh(upper_arm)

    # Forearm
    forearm_y_top = CHEST_Y
    forearm_y_bot = WAIST_Y - 5
    forearm = create_limb(
        forearm_y_bot, forearm_y_top, WRIST_R, FOREARM_R,
        x_offset=x_off, segments=10, rings=4, name=f"{side}Forearm"
    )
    scene.add_mesh(forearm)

    # Hand
    hand = create_limb(
        forearm_y_bot - 12, forearm_y_bot, HAND_R * 0.6, WRIST_R,
        x_offset=x_off, segments=8, rings=3, name=f"{side}Hand"
    )
    scene.add_mesh(hand)

# ── Legs ──
for side, sign in [("Left", -1), ("Right", 1)]:
    x_off = sign * HIP_HW * 0.55

    # Thigh
    thigh = create_limb(
        KNEE_Y, HIP_Y, KNEE_R, THIGH_R,
        x_offset=x_off, segments=12, rings=5, name=f"{side}Thigh"
    )
    thigh.materials = [MAT_PANTS]
    scene.add_mesh(thigh)

    # Calf
    calf = create_limb(
        ANKLE_Y, KNEE_Y, ANKLE_R, CALF_R,
        x_offset=x_off, segments=12, rings=5, name=f"{side}Calf"
    )
    calf.materials = [MAT_PANTS]
    scene.add_mesh(calf)

    # Foot (simplified)
    foot = create_body_section(
        FOOT_Y, ANKLE_Y,
        (ANKLE_R * 0.9, ANKLE_R * 1.4), (ANKLE_R, ANKLE_R * 0.8),
        segments=10, rings=3, name=f"{side}Foot"
    )
    foot.materials = [MAT_PANTS]
    # Offset foot
    for v in foot.vertices:
        v.position[0] += x_off * SCALE
    scene.add_mesh(foot)

# ── Verify all ──
for m in scene.meshes:
    if not m.ks_history:
        m.ks_verify_operation(f"build_{m.name}", 0.88, 0.94, 0.07)

# Stats
print(f"Meshes: {len(scene.meshes)}")
stats = scene.stats()
for k, v in stats.items():
    if isinstance(v, float):
        print(f"  {k}: {v:.3f}")
    else:
        print(f"  {k}: {v}")

# Export
outdir = os.path.join(os.path.dirname(__file__), 'output')
os.makedirs(outdir, exist_ok=True)

full_avatar = merge_meshes(scene.meshes, "AndrogynousAvatar_Full")

obj_path = os.path.join(outdir, 'avatar_androgynous.obj')
export_obj(full_avatar, obj_path)
print(f"\nExported OBJ: {obj_path}")

fbx_path = os.path.join(outdir, 'avatar_androgynous.fbx')
export_fbx_ascii(full_avatar, fbx_path)
print(f"Exported FBX: {fbx_path}")

print(f"\nKS Quality Score: {full_avatar.ks_quality_score():.3f}")
print("\n=== Body Proportions ===")
print(f"  Head: {HEAD_TOP_Y - CHIN_Y}cm")
print(f"  Shoulders: {SHOULDER_HW * 2}cm (full width)")
print(f"  Waist: {WAIST_HW * 2}cm")
print(f"  Hips: {HIP_HW * 2}cm")
print(f"  Inseam: {HIP_Y}cm")
print(f"  Shoulder/Waist ratio: {SHOULDER_HW / WAIST_HW:.2f}")
print(f"  Hip/Waist ratio: {HIP_HW / WAIST_HW:.2f}")
print("\nDone!")
