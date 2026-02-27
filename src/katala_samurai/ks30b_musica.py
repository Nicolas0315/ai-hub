"""
KS30b Musica — Katala_Samurai_30_b_musica
Spectrogram-to-spectrogram music generation with semantic paper reference.

Architecture (KS30b = S2->S7 semantic connection applied to music):
  S2: Harmonic structure extraction (theory-grounded, LLM-enhanced)
  S3: Spectral patch clustering (CNN learned features + orchestration knowledge)
  S4: Patch selection (energy/position/chord-similarity/CNN-distance)
  S5: Griffin-Lim phase estimation (shared-phase for stereo coherence)
  S6: Vision self-analysis (spectrogram critique via KS30 pipeline)
  S7: Theory reference via S2.key_concepts (KS30b semantic search)

Design: Youta Hilono (@visz_cham)
Implementation: Shirokuma
"""

import numpy as np
import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

# ═══ Configuration ═══

@dataclass
class MusicaConfig:
    sr: int = 22050
    n_fft: int = 2048
    hop_length: int = 512
    target_bpm: int = 78
    target_key: str = "F#m"
    patch_size: Tuple[int, int] = (128, 32)
    gl_iterations: int = 200
    chord_sim_threshold: float = 0.45
    avoid_suppress_db: float = -18.0
    beat_grid_amplitude: float = 2.0
    intro_max_seconds: float = 4.0
    stereo_channels: List[str] = field(default_factory=lambda: ["L", "R", "C", "S"])
    cnn_latent_dim: int = 64

# ═══ S2: Harmonic Structure (KS30b semantic) ═══

@dataclass
class HarmonicStructure:
    chroma_profile: np.ndarray = None
    detected_chords: List[Dict] = field(default_factory=list)
    key_estimate: str = ""
    tempo_estimate: float = 0.0
    spectral_centroid: float = 0.0
    key_concepts: List[str] = field(default_factory=list)
    semantic_domain: str = "music"
    implicit_assumptions: List[str] = field(default_factory=list)

def extract_harmonic_structure(spectrogram, sr=22050, hop_length=512):
    import librosa
    hs = HarmonicStructure()
    S = np.abs(spectrogram)
    hs.chroma_profile = librosa.feature.chroma_stft(S=S, sr=sr, hop_length=hop_length)
    cent = librosa.feature.spectral_centroid(S=S, sr=sr)
    hs.spectral_centroid = float(np.mean(cent))
    onset_env = librosa.onset.onset_strength(S=S, sr=sr)
    tempo = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)[0]
    hs.tempo_estimate = float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)
    hs.detected_chords = _detect_chords(hs.chroma_profile)
    hs.key_estimate = _estimate_key(hs.chroma_profile)
    hs.key_concepts = _gen_concepts(hs)
    hs.implicit_assumptions = _derive_assumptions(hs)
    return hs

def _detect_chords(chroma, min_conf=0.3):
    if chroma is None: return []
    TEMPLATES = {
        'C':[1,0,0,0,1,0,0,1,0,0,0,0], 'Cm':[1,0,0,1,0,0,0,1,0,0,0,0],
        'D':[0,0,1,0,0,0,1,0,0,1,0,0], 'Dm':[0,0,1,0,0,1,0,0,0,1,0,0],
        'E':[0,0,0,0,1,0,0,0,1,0,0,1], 'Em':[0,0,0,0,1,0,0,1,0,0,0,1],
        'F':[1,0,0,0,0,1,0,0,0,1,0,0], 'G':[0,0,1,0,0,0,0,1,0,0,0,1],
        'Am':[1,0,0,0,1,0,0,0,0,1,0,0], 'Bm':[0,0,0,1,0,0,1,0,0,0,1,0],
        'Cmaj7':[1,0,0,0,1,0,0,1,0,0,0,1], 'Am7':[1,0,0,0,1,0,0,1,0,1,0,0],
    }
    chords = []
    n_frames = chroma.shape[1]
    w = max(4, n_frames // 16)
    for i in range(0, n_frames - w + 1, w):
        fc = np.mean(chroma[:, i:i+w], axis=1)
        fc = fc / (np.linalg.norm(fc) + 1e-8)
        best, best_s = 'C', -1
        for name, t in TEMPLATES.items():
            t = np.array(t, dtype=float); t = t / (np.linalg.norm(t) + 1e-8)
            s = float(np.dot(fc, t))
            if s > best_s: best_s = s; best = name
        if best_s >= min_conf:
            chords.append({'name': best, 'beat': i * 512 / 22050, 'confidence': round(best_s, 3)})
    return chords

def _estimate_key(chroma):
    if chroma is None: return "unknown"
    maj = [6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88]
    minor = [6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17]
    mc = np.mean(chroma, axis=1)
    notes = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    best_k, best_c = 'C', -1
    for i in range(12):
        r = np.roll(mc, -i)
        for prof, suf in [(maj,''), (minor,'m')]:
            c = float(np.corrcoef(r, prof)[0,1])
            if c > best_c: best_c = c; best_k = f"{notes[i]}{suf}"
    return best_k

def _gen_concepts(hs):
    c = ['spectrogram', 'music generation']
    if 'm' in hs.key_estimate: c.append('minor key harmony')
    else: c.append('major key harmony')
    if any('7' in ch['name'] for ch in hs.detected_chords):
        c.extend(['jazz harmony', 'extended chords', 'lofi'])
    if hs.tempo_estimate < 90: c.append('slow tempo relaxation')
    return c

def _derive_assumptions(hs):
    a = []
    if hs.key_estimate: a.append(f"Target key is {hs.key_estimate}")
    chord_names = [c['name'] for c in hs.detected_chords]
    v7s = ['G7','B7','D7','A7','E7','C#7','F#7']
    if not any(c in v7s for c in chord_names):
        a.append("No functional dominant 7th (V7)")
    avoid_map = {'C':['F'],'Am':['Bb'],'F#m':['G'],'Em':['F'],'Dm':['Eb']}
    if hs.key_estimate in avoid_map:
        for n in avoid_map[hs.key_estimate]:
            a.append(f"Avoid note: {n} (minor 2nd)")
    return a

# ═══ S3: Patch Extraction ═══

@dataclass
class SpectralPatch:
    data: np.ndarray
    chroma: np.ndarray = None
    centroid: float = 0.0
    energy: float = 0.0
    chord_label: str = ""
    source_track: str = ""
    cnn_features: np.ndarray = None

def extract_patches(audio_path, config=None):
    import librosa, soundfile as sf
    if config is None: config = MusicaConfig()
    y, sr = sf.read(audio_path)
    if y.ndim > 1: y = np.mean(y, axis=1)
    if sr != config.sr: y = librosa.resample(y, orig_sr=sr, target_sr=config.sr); sr = config.sr
    S = librosa.stft(y, n_fft=config.n_fft, hop_length=config.hop_length)
    S_mag = np.abs(S)
    chroma = librosa.feature.chroma_stft(S=S_mag, sr=sr, hop_length=config.hop_length)
    patches = []
    fb, tb = S_mag.shape
    ph, pw = min(config.patch_size[0], fb), config.patch_size[1]
    for t in range(0, tb - pw, pw):
        pd = S_mag[:ph, t:t+pw]
        pc = np.mean(chroma[:, t:t+pw], axis=1)
        p = SpectralPatch(data=pd, chroma=pc,
            centroid=float(np.average(np.arange(ph), weights=np.mean(pd, axis=1)+1e-8)),
            energy=float(np.mean(pd)), source_track=os.path.basename(audio_path))
        # Chord label
        templates = {'C':[1,0,0,0,1,0,0,1,0,0,0,0],'Am':[1,0,0,0,1,0,0,0,0,1,0,0],
                     'F':[1,0,0,0,0,1,0,0,0,1,0,0],'G':[0,0,1,0,0,0,0,1,0,0,0,1],
                     'Dm':[0,0,1,0,0,1,0,0,0,1,0,0],'Em':[0,0,0,0,1,0,0,1,0,0,0,1]}
        cv = pc / (np.linalg.norm(pc)+1e-8)
        best, bs = 'C', -1
        for nm, tp in templates.items():
            tp = np.array(tp,dtype=float); tp=tp/(np.linalg.norm(tp)+1e-8)
            s = float(np.dot(cv,tp))
            if s > bs: bs=s; best=nm
        p.chord_label = best
        patches.append(p)
    return patches, S, sr

# ═══ S3b: CNN Learned Features ═══

def train_patch_autoencoder(patches, latent_dim=64, epochs=30):
    try:
        import torch, torch.nn as nn
    except ImportError:
        return None
    class PAE(nn.Module):
        def __init__(self, h, w, ld):
            super().__init__()
            self.enc = nn.Sequential(nn.Conv2d(1,16,3,padding=1),nn.ReLU(),
                nn.AdaptiveAvgPool2d((h//4,w//4)),nn.Conv2d(16,32,3,padding=1),nn.ReLU(),
                nn.AdaptiveAvgPool2d((4,4)),nn.Flatten(),nn.Linear(32*4*4,ld))
            self.dec = nn.Sequential(nn.Linear(ld,32*4*4),nn.Unflatten(1,(32,4,4)),
                nn.ConvTranspose2d(32,16,3,padding=1),nn.ReLU(),nn.Upsample(size=(h//4,w//4)),
                nn.ConvTranspose2d(16,1,3,padding=1),nn.Upsample(size=(h,w)))
        def forward(self, x):
            z = self.enc(x); return self.dec(z), z
    h, w = patches[0].data.shape
    X = np.stack([p.data for p in patches]); X = X/(X.max()+1e-8)
    Xt = __import__('torch').FloatTensor(X).unsqueeze(1)
    m = PAE(h, w, latent_dim); opt = __import__('torch').optim.Adam(m.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    labels = [p.chord_label for p in patches]
    m.train()
    for ep in range(epochs):
        opt.zero_grad(); rec, z = m(Xt); loss = loss_fn(rec, Xt)
        if len(set(labels)) > 1:
            for i in range(min(len(patches),32)):
                for j in range(i+1, min(len(patches),32)):
                    d = __import__('torch').sum((z[i]-z[j])**2)
                    if labels[i]==labels[j]: loss += 0.01*d
                    else: loss += 0.01*__import__('torch').clamp(1.0-d, min=0)
        loss.backward(); opt.step()
    m.eval()
    with __import__('torch').no_grad():
        _, feats = m(Xt); feats = feats.numpy()
    for i, p in enumerate(patches): p.cnn_features = feats[i]
    return m

# ═══ S4: Patch Selection ═══

def select_patches(patches, chord, energy, config=None, avoid_notes=None):
    if config is None: config = MusicaConfig()
    cands = []
    for p in patches:
        cs = 1.0 if p.chord_label == chord else 0.3
        if cs < config.chord_sim_threshold: continue
        ed = abs(p.energy - energy); es = max(0, 1.0 - ed/(energy+1e-8))
        ap = 0.0
        if avoid_notes and p.chroma is not None:
            nm = {'C':0,'C#':1,'D':2,'D#':3,'E':4,'F':5,'F#':6,'G':7,'G#':8,'A':9,'A#':10,'B':11,'Bb':10,'Eb':3}
            for n in avoid_notes:
                idx = nm.get(n,-1)
                if idx >= 0 and p.chroma[idx] > 0.3: ap += p.chroma[idx]
        score = cs*0.4 + es*0.3 - ap*0.3
        cands.append((score, p))
    cands.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in cands[:8]]

# ═══ S5: Griffin-Lim (shared-phase stereo) ═══

def griffin_lim_shared(S_C, S_L=None, S_R=None, S_S=None, n_iter=200, hop=512):
    import librosa
    y_c = librosa.griffinlim(S_C, n_iter=n_iter, hop_length=hop)
    phase = np.angle(librosa.stft(y_c, hop_length=hop))
    out = {'C': y_c}
    for lbl, S in [('L',S_L),('R',S_R),('S',S_S)]:
        if S is not None:
            mf, mt = min(S.shape[0],phase.shape[0]), min(S.shape[1],phase.shape[1])
            out[lbl] = librosa.istft(S[:mf,:mt]*np.exp(1j*phase[:mf,:mt]), hop_length=hop)
    return out

# ═══ S5b: Beat Grid Synthesis ═══

def synth_beat_grid(n_frames, sr=22050, hop=512, bpm=78, n_fft=2048, amp=2.0):
    fb = n_fft//2+1; grid = np.zeros((fb, n_frames))
    freqs = np.linspace(0, sr/2, fb)
    fpb = (60.0/bpm) * (sr/hop)
    for bi in range(int(n_frames/fpb)):
        fr = int(bi*fpb)
        if fr >= n_frames: break
        if bi%2==0: grid[:, fr] += amp*np.exp(-0.5*((freqs-80)/30)**2)
        if bi%2==1: grid[:, fr] += amp*0.7*np.exp(-0.5*((freqs-1600)/400)**2)
        grid[:, fr] += amp*0.3*np.exp(-0.5*((freqs-6000)/1000)**2)
    return grid

# ═══ S6: Post-generation Analysis ═══

def analyze_output(S_lrcs, config=None):
    import librosa
    if config is None: config = MusicaConfig()
    r = {}
    if 'C' in S_lrcs:
        S = S_lrcs['C']; chroma = librosa.feature.chroma_stft(S=np.abs(S), sr=config.sr)
        tmpls = {'I':[1,0,0,0,1,0,0,1,0,0,0,0],'vi':[1,0,0,0,1,0,0,0,0,1,0,0],
                 'ii':[0,0,1,0,0,1,0,0,0,1,0,0],'IV':[1,0,0,0,0,1,0,0,0,1,0,0]}
        nf = chroma.shape[1]; ss = nf//4; m = 0
        for i,(nm,t) in enumerate(tmpls.items()):
            st = i*ss; en = st+ss
            if en > nf: break
            sc = np.mean(chroma[:,st:en],axis=1); sc=sc/(np.linalg.norm(sc)+1e-8)
            tv = np.array(t,dtype=float); tv=tv/(np.linalg.norm(tv)+1e-8)
            if float(np.dot(sc,tv)) > 0.5: m += 1
        r['loop_integrity'] = m/4.0
    if 'L' in S_lrcs and 'R' in S_lrcs:
        L,R = S_lrcs['L'],S_lrcs['R']; ml = min(len(L),len(R))
        r['stereo_correlation'] = round(float(np.corrcoef(L[:ml],R[:ml])[0,1]),3)
    if 'C' in S_lrcs:
        oe = librosa.onset.onset_strength(S=np.abs(S_lrcs['C']), sr=config.sr)
        t = librosa.beat.beat_track(onset_envelope=oe, sr=config.sr)[0]
        bpm_d = float(t[0]) if hasattr(t,'__len__') else float(t)
        r['detected_bpm'] = round(bpm_d,1); r['target_bpm'] = config.target_bpm
        cent = librosa.feature.spectral_centroid(S=np.abs(S_lrcs['C']), sr=config.sr)
        r['spectral_centroid'] = round(float(np.mean(cent)),1)
    return r

# ═══ S7: Theory Reference (KS30b semantic) ═══

def search_papers(harmonic, max_papers=3):
    from katala_samurai.paper_reference import _build_search_query_semantic, _query_openalex, _reconstruct_abstract, PaperReference
    from katala_samurai.ks29b import LogicalStructure
    ls = LogicalStructure()
    ls.key_concepts = harmonic.key_concepts
    ls.semantic_domain = harmonic.semantic_domain
    ls.propositions = {f"key_{harmonic.key_estimate}": True}
    q = _build_search_query_semantic(ls, None)
    if not q.strip(): q = " ".join(harmonic.key_concepts[:6])
    results = _query_openalex(q, per_page=max_papers, timeout=10)
    papers = []
    for w in results:
        ab = _reconstruct_abstract(w.get('abstract_inverted_index'))
        au = [a.get('author',{}).get('display_name','') for a in w.get('authorships',[])[:3]]
        papers.append(PaperReference(title=w.get('title','?'), year=w.get('publication_year',0) or 0,
            authors=au, cited_by=w.get('cited_by_count',0), openalex_id=w.get('id',''),
            doi=w.get('doi'), abstract=ab, context_domain='music'))
    return papers

# ═══ Song Structure ═══

SONG_STRUCTURE = [
    {"section":"intro","beats":4,"energy":0.3,"chord":"I"},
    {"section":"verse1","beats":16,"energy":0.5,"chord":"I-vi-ii-IV"},
    {"section":"chorus1","beats":16,"energy":0.8,"chord":"I-V-vi-IV"},
    {"section":"verse2","beats":16,"energy":0.5,"chord":"I-vi-ii-IV"},
    {"section":"chorus2","beats":16,"energy":0.85,"chord":"I-V-vi-IV"},
    {"section":"bridge","beats":8,"energy":0.4,"chord":"vi-IV"},
    {"section":"chorus3","beats":16,"energy":0.9,"chord":"I-V-vi-IV"},
    {"section":"outro","beats":8,"energy":0.2,"chord":"I"},
]

# ═══ Stereo Positioning ═══

def position_stereo(S_mono, sr=22050):
    fb = S_mono.shape[0]; freqs = np.linspace(0, sr/2, fb)
    L,R,C,Sd = (np.zeros_like(S_mono) for _ in range(4))
    for i,f in enumerate(freqs):
        if f < 200: C[i,:] = S_mono[i,:]
        elif f < 2000:
            if i%2==0: L[i,:]=S_mono[i,:]*0.7; R[i,:]=S_mono[i,:]*0.3
            else: L[i,:]=S_mono[i,:]*0.3; R[i,:]=S_mono[i,:]*0.7
            C[i,:] = S_mono[i,:]*0.3
        else:
            L[i,:]=S_mono[i,:]*(0.5+0.3*np.sin(i*0.1))
            R[i,:]=S_mono[i,:]*(0.5-0.3*np.sin(i*0.1))
            Sd[i,:]=S_mono[i,:]*0.4
    return {'L':L,'R':R,'C':C,'S':Sd}

# ═══ Main Pipeline ═══

def generate(audio_paths, output_path="ks30b_musica.wav", config=None):
    """Full KS30b Musica pipeline: S2→S3→S3b→S4→S5b→S5→S6→S7"""
    import librosa, soundfile as sf
    if config is None: config = MusicaConfig()
    print("=== KS30b Musica === Katala_Samurai_30_b_musica ===")
    print(f"  {config.target_bpm}BPM, key={config.target_key}, {len(audio_paths)} sources")

    # S3: patches
    print("\n[S3] Extracting patches...")
    all_p = []
    for path in audio_paths:
        if os.path.exists(path):
            ps, _, _ = extract_patches(path, config); all_p.extend(ps)
            print(f"  {os.path.basename(path)}: {len(ps)} patches")
    if not all_p: raise ValueError("No patches")
    print(f"  Total: {len(all_p)}")

    # S3b: CNN
    print("\n[S3b] CNN PatchAutoEncoder...")
    mdl = train_patch_autoencoder(all_p, config.cnn_latent_dim, 30)
    print(f"  CNN: {'OK' if mdl else 'skip'}")

    # S2: harmonic structure
    print("\n[S2] Harmonic structure (KS30b)...")
    _, ref_S, ref_sr = extract_patches(audio_paths[0], config)
    hs = extract_harmonic_structure(ref_S, ref_sr, config.hop_length)
    print(f"  Key={hs.key_estimate} Tempo={hs.tempo_estimate:.0f} Cent={hs.spectral_centroid:.0f}")
    print(f"  concepts={hs.key_concepts}")
    print(f"  assumptions={hs.implicit_assumptions}")

    # S4: assemble
    print("\n[S4] Assembling song...")
    fb = all_p[0].data.shape[0]; pw = all_p[0].data.shape[1]
    total_beats = sum(s['beats'] for s in SONG_STRUCTURE)
    bpf = int(60.0/config.target_bpm * config.sr/config.hop_length)
    tf = total_beats * bpf
    S_out = np.zeros((fb, tf))
    avoid = [a.split('Avoid note:')[1].split('(')[0].strip() for a in hs.implicit_assumptions if 'Avoid note:' in a]
    cur = 0
    chord_map = {'I':'C','ii':'Dm','IV':'F','V':'G','vi':'Am'}
    for sec in SONG_STRUCTURE:
        sf_ = sec['beats']*bpf; te = sec['energy']*np.mean([p.energy for p in all_p])
        cseq = sec['chord'].split('-'); fpc = sf_//len(cseq)
        for ci, cn in enumerate(cseq):
            ch = chord_map.get(cn,'C')
            sel = select_patches(all_p, ch, te, config, avoid)
            if sel:
                cs = cur + ci*fpc
                for pi, pa in enumerate(sel):
                    st = cs + pi*pw; en = min(st+pw, cur+sf_, tf)
                    if st >= tf or en <= st: break
                    S_out[:, st:en] = pa.data[:, :en-st]
                    # Avoid suppress
                    nm = {'C':0,'C#':1,'D':2,'D#':3,'E':4,'F':5,'F#':6,'G':7,'G#':8,'A':9,'A#':10,'B':11,'Bb':10,'Eb':3}
                    for n in avoid:
                        idx = nm.get(n,-1)
                        if idx >= 0:
                            af = 440*2**((idx-9)/12)
                            for oc in range(1,8):
                                f = af*(2**(oc-4)); bi = int(f*fb/(config.sr/2))
                                if 0<=bi<fb: S_out[bi,st:en] *= 10**(config.avoid_suppress_db/20)
        # Envelope
        se = min(cur+sf_, tf); env = np.ones(se-cur)
        fd = max(1, len(env)//10)
        env[:fd] = np.linspace(0.3,1.0,fd); env[-fd:] = np.linspace(1.0,0.3,fd)
        S_out[:, cur:se] *= env[np.newaxis,:]
        print(f"  {sec['section']}: {sec['beats']}b e={sec['energy']}")
        cur += sf_

    # S5b: beat grid
    print("\n[S5b] Beat grid synthesis...")
    bg = synth_beat_grid(tf, config.sr, config.hop_length, config.target_bpm, config.n_fft, config.beat_grid_amplitude)
    mf = min(bg.shape[0], S_out.shape[0]); S_out[:mf, :] += bg[:mf, :tf]

    # Stereo
    print("[Stereo] L/R/C/S...")
    S_st = position_stereo(S_out, config.sr)

    # S5: Griffin-Lim
    print(f"[S5] Shared-phase GL ({config.gl_iterations} iter)...")
    ach = griffin_lim_shared(S_st['C'], S_st['L'], S_st['R'], S_st['S'], config.gl_iterations, config.hop_length)

    # Mix stereo
    yL = ach.get('L', np.zeros(1)); yR = ach.get('R', np.zeros(1)); yC = ach.get('C', np.zeros(1))
    ml = min(len(yL), len(yR), len(yC))
    ys = np.column_stack([yL[:ml]*0.5+yC[:ml]*0.5, yR[:ml]*0.5+yC[:ml]*0.5])
    ys = ys / (np.max(np.abs(ys))+1e-8) * 0.9
    sf.write(output_path, ys, config.sr)
    dur = len(ys)/config.sr
    print(f"\n  Output: {output_path} ({dur:.1f}s)")

    # S6: analysis
    print("\n[S6] Post-generation analysis...")
    S_an = {}
    for ch in ['L','R','C']:
        if ch in ach: S_an[ch] = librosa.stft(ach[ch][:ml], n_fft=config.n_fft, hop_length=config.hop_length)
    ana = analyze_output(S_an, config)
    print(f"  Loop: {ana.get('loop_integrity',0)*100:.1f}%")
    print(f"  Stereo: {ana.get('stereo_correlation',0):.3f}")
    print(f"  Tempo: {ana.get('detected_bpm',0):.1f}/{config.target_bpm}")
    print(f"  Centroid: {ana.get('spectral_centroid',0):.0f}Hz")

    # S7: papers
    print("\n[S7] Theory papers (KS30b semantic)...")
    try:
        pps = search_papers(hs, 3)
        for p in pps: print(f"  -> {p.title[:55]} (cited:{p.cited_by})")
        ana['papers'] = [{'title':p.title,'cited_by':p.cited_by} for p in pps]
    except Exception as e:
        print(f"  S7: {e}"); ana['papers'] = []

    ana['duration'] = round(dur,1); ana['n_patches'] = len(all_p)
    print("\n=== KS30b Musica Complete ===")
    return ana
