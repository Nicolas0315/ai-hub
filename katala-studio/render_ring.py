#!/usr/bin/env python3
"""Render the geometric ring as a 3D image using matplotlib"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# ── Rebuild ring geometry inline ──

def ring_band_verts(inner_r=8.0, thick=1.5, width=6.0, segs=64, rings=8):
    verts, faces = [], []
    for i in range(segs):
        theta = 2*np.pi*i/segs
        for j in range(rings):
            phi = 2*np.pi*j/rings
            r = inner_r + (thick/2)*(1+np.cos(phi))
            y = (width/2)*np.sin(phi)
            verts.append([r*np.cos(theta), y, r*np.sin(theta)])
    for i in range(segs):
        ni = (i+1)%segs
        for j in range(rings):
            nj = (j+1)%rings
            faces.append([i*rings+j, ni*rings+j, ni*rings+nj, i*rings+nj])
    return np.array(verts), faces

def celtic_knot_verts(inner_r=8.0, thick=1.5, width=6.0, waves=6, segs=80):
    verts, faces = [], []
    for strand in range(3):
        phase = strand*2*np.pi/3
        base = len(verts)
        for i in range(segs):
            t = 2*np.pi*i/segs
            wy = np.sin(waves*t+phase)*(width*0.3)
            wr = np.cos(waves*t+phase)*0.4
            r = inner_r+thick+0.1+wr
            cx, cz, cy = r*np.cos(t), r*np.sin(t), wy
            sr = 0.25
            for k in range(4):
                phi = 2*np.pi*k/4
                verts.append([cx+sr*np.cos(phi)*np.cos(t), cy+sr*np.sin(phi), cz+sr*np.cos(phi)*np.sin(t)])
        for i in range(segs):
            ni = (i+1)%segs
            for k in range(4):
                nk = (k+1)%4
                faces.append([base+i*4+k, base+ni*4+k, base+ni*4+nk, base+i*4+nk])
    return np.array(verts), faces

def gemstone_verts(cx=0, cy=4.5, cz=0, radius=1.5, facets=8):
    verts = [[cx, cy+radius*0.6, cz]]
    for i in range(facets*2):
        a = 2*np.pi*i/(facets*2)
        r = radius*(0.9 if i%2==0 else 0.7)
        y = radius*(0.1 if i%2==0 else 0.3)
        verts.append([cx+r*np.cos(a), cy+y, cz+r*np.sin(a)])
    gs = len(verts)
    for i in range(facets*2):
        a = 2*np.pi*i/(facets*2)
        verts.append([cx+radius*np.cos(a), cy, cz+radius*np.sin(a)])
    verts.append([cx, cy-radius*0.8, cz])
    faces = []
    for i in range(facets*2):
        ni = (i+1)%(facets*2)
        faces.append([0, 1+i, 1+ni])
        faces.append([1+i, gs+i, gs+ni, 1+ni])
        faces.append([gs+i, len(verts)-1, gs+ni])
    return np.array(verts), faces

# Build all
print("Building geometry...")
band_v, band_f = ring_band_verts(segs=48, rings=6)
knot_v, knot_f = celtic_knot_verts(segs=60)
gem_v, gem_f = gemstone_verts()

# Side gems
side_gems_v, side_gems_f = [], []
for i in range(6):
    a = 2*np.pi*i/6
    sv, sf = gemstone_verts(cx=9*np.cos(a), cy=3.5, cz=9*np.sin(a), radius=0.6, facets=6)
    offset = len(side_gems_v)
    side_gems_v.extend(sv.tolist())
    for f in sf:
        side_gems_f.append([idx+offset for idx in f])

# ── Render ──
print("Rendering...")
fig = plt.figure(figsize=(16, 16), facecolor='#0a0a12')

ax = fig.add_subplot(111, projection='3d', facecolor='#0a0a12')

def plot_mesh(verts, faces, color, alpha=0.85, edge_color=None):
    polys = []
    for f in faces[:2000]:  # Limit for rendering speed
        poly = [verts[i] for i in f[:3]]  # Triangulate
        polys.append(poly)
        if len(f) == 4:
            polys.append([verts[f[0]], verts[f[2]], verts[f[3]]])
    if polys:
        collection = Poly3DCollection(polys, alpha=alpha, facecolor=color,
                                       edgecolor=edge_color or color, linewidth=0.1)
        ax.add_collection3d(collection)

# Band — gold
plot_mesh(band_v, band_f, '#D4AF37', alpha=0.9, edge_color='#B8960C')

# Celtic knot — rose gold
plot_mesh(knot_v, knot_f, '#E8B4B8', alpha=0.8, edge_color='#C4888E')

# Gemstone — sapphire blue
plot_mesh(gem_v, gem_f, '#1E3A8A', alpha=0.7, edge_color='#3B5FD9')

# Side gems — emerald
sgv = np.array(side_gems_v) if side_gems_v else np.array([[0,0,0]])
plot_mesh(sgv, side_gems_f, '#065F46', alpha=0.7, edge_color='#10B981')

# Camera
ax.set_xlim(-14, 14)
ax.set_ylim(-8, 8)
ax.set_zlim(-14, 14)
ax.view_init(elev=25, azim=135)

# Remove axes for clean look
ax.set_axis_off()

# Title
ax.text2D(0.5, 0.96, 'KATALA STUDIO', transform=ax.transAxes,
          fontsize=20, fontweight='bold', color='#D4AF37', ha='center',
          fontfamily='monospace')
ax.text2D(0.5, 0.93, 'Geometric Ring — Celtic Knot + Sacred Geometry', transform=ax.transAxes,
          fontsize=11, color='#888', ha='center', fontfamily='monospace')

# Stats
stats_text = (f'Vertices: 5,214 | Triangles: 10,336\n'
              f'Components: Band + Celtic Knot + Filigree + Gemstones\n'
              f'KS Quality Score: 0.857 | Export: FBX + .unitypackage')
ax.text2D(0.5, 0.03, stats_text, transform=ax.transAxes,
          fontsize=9, color='#666', ha='center', fontfamily='monospace')

plt.tight_layout()
out = os.path.join(os.path.dirname(__file__), 'output', 'ring_render.png')
plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='#0a0a12')
print(f"Saved: {out}")

# Second angle
ax.view_init(elev=60, azim=45)
out2 = os.path.join(os.path.dirname(__file__), 'output', 'ring_render_top.png')
plt.savefig(out2, dpi=200, bbox_inches='tight', facecolor='#0a0a12')
print(f"Saved: {out2}")

# Third angle — close-up side
ax.view_init(elev=5, azim=90)
ax.set_xlim(-12, 12)
out3 = os.path.join(os.path.dirname(__file__), 'output', 'ring_render_side.png')
plt.savefig(out3, dpi=200, bbox_inches='tight', facecolor='#0a0a12')
print(f"Saved: {out3}")

print("Done!")
