import { NextResponse } from "next/server";

// ── KCS-2a Lite: TypeScript port of the reverse inference engine ──

const FRAMEWORK_SIGNATURES: Record<string, string[]> = {
  harmonic_analysis: ["chroma", "chord", "key_estimate", "harmony", "tonal", "detected_chords", "progression"],
  spectral_processing: ["spectrogram", "fft", "stft", "griffin", "phase", "spectral_centroid", "hop_length", "librosa"],
  spatial_audio: ["stereo", "panning", "surround", "positioning", "binaural", "spatial"],
  rhythmic_structure: ["bpm", "tempo", "beat", "grid", "onset", "beat_track", "rhythm"],
  music_generation: ["patch", "song_structure", "verse", "chorus", "bridge", "intro", "outro", "arrangement"],
  psychoacoustics: ["loudness", "masking", "timbre", "roughness", "dissonance", "consonance", "auditory"],
  quine_indeterminacy: ["indeterminacy", "underdetermined", "translation", "radical translation"],
  duhem_quine: ["holistic", "web of belief", "auxiliary"],
  kuhn_paradigm: ["paradigm", "incommensurable", "revolution", "normal science"],
  behaviorism: ["behavioral", "observable", "stimulus", "response"],
  pragmatism: ["pragmat", "usefulness", "practical consequence"],
  information_theory: ["entropy", "mutual information", "channel capacity", "shannon"],
};

const PATTERN_SIGNATURES: Record<string, RegExp> = {
  pipeline: /pipeline|stage|step.*result|chain/i,
  factory: /create_|make_|build_|factory/i,
  bridge: /bridge|adapter|rust_bridge/i,
  strategy: /strategy|backend|fallback/i,
  observer: /callback|listener|on_event|subscribe/i,
  singleton: /_CACHED_|_instance/i,
};

interface Goal {
  goal: string;
  priority: "high" | "medium" | "low";
  rationale: string;
  estimated_impact: string;
  source: string;
}

function analyze(code: string) {
  const codeLower = code.toLowerCase();
  const lines = code.split("\n");

  // Detect frameworks
  const frameworks: string[] = [];
  for (const [name, markers] of Object.entries(FRAMEWORK_SIGNATURES)) {
    if (markers.some((m) => codeLower.includes(m))) {
      frameworks.push(name);
    }
  }

  // Detect patterns
  const patterns: string[] = [];
  for (const [name, regex] of Object.entries(PATTERN_SIGNATURES)) {
    if (regex.test(code)) {
      patterns.push(name);
    }
  }

  // Extract purpose from first docstring
  const docMatch = code.match(/"""([\s\S]*?)"""/);
  const purpose = docMatch
    ? docMatch[1].trim().split("\n")[0].trim()
    : "Purpose not detected";

  // Count functions and docstrings
  const funcNames: string[] = [];
  const funcRegex = /def\s+(\w+)\s*\(/g;
  let m;
  while ((m = funcRegex.exec(code)) !== null) {
    funcNames.push(m[1]);
  }
  const publicFuncs = funcNames.filter((f) => !f.startsWith("_"));

  const docstringCount = (code.match(/def\s+\w+[^:]*:\s*\n\s+"""/g) || []).length;
  const coverage = funcNames.length > 0 ? docstringCount / funcNames.length : 0;

  // Detect architecture
  const classCount = (code.match(/^class\s+/gm) || []).length;
  const architecture = classCount > 3 ? "layered" : classCount > 0 ? "modular" : funcNames.length > 5 ? "pipeline" : "monolithic";

  // Find TODOs
  const incomplete: string[] = [];
  const todoRegex = /#\s*(TODO|FIXME|HACK)[\s:]+(.+)/gi;
  while ((m = todoRegex.exec(code)) !== null) {
    incomplete.push(`${m[1]}: ${m[2].trim()}`);
  }

  // Find undocumented magic numbers
  let magicLines = 0;
  for (const line of lines) {
    if (line.includes("#")) continue;
    const nums = line.match(/(?<![.\w])\d+\.\d+(?![.\w])/g) || [];
    const bad = nums.filter((n) => !["0.0", "1.0", "0.5"].includes(n));
    if (bad.length > 0) magicLines++;
  }

  const undocumented: string[] = [];
  if (magicLines > 3) undocumented.push(`${magicLines} lines with unexplained numeric constants`);
  const undocFuncs = funcNames.length - docstringCount;
  if (undocFuncs > 0) undocumented.push(`${undocFuncs} functions without docstrings`);

  // Extract concepts
  const conceptRegex = /[a-z_]{4,}/g;
  const noise = new Set(["self", "none", "true", "false", "return", "import", "from", "class", "with", "result", "value", "data", "text", "name"]);
  const freq: Record<string, number> = {};
  while ((m = conceptRegex.exec(codeLower)) !== null) {
    const w = m[0];
    if (!noise.has(w)) freq[w] = (freq[w] || 0) + 1;
  }
  const concepts = Object.entries(freq)
    .filter(([, n]) => n >= 2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([w]) => w);

  // Generate goals
  const goals: Goal[] = [];

  for (const gap of incomplete) {
    goals.push({ goal: `Complete: ${gap}`, priority: "high", rationale: "Incomplete implementation", estimated_impact: "R_struct", source: "reverse_inference" });
  }
  for (const f of publicFuncs.slice(0, 5)) {
    goals.push({ goal: `Add test: ${f}()`, priority: "medium", rationale: "Public API without test", estimated_impact: "R_temporal (future survivability)", source: "gap_analysis" });
  }
  for (const u of undocumented) {
    goals.push({ goal: `Document: ${u}`, priority: "medium", rationale: "Design decision without docs", estimated_impact: "R_context (theoretical context)", source: "gap_analysis" });
  }

  const knownModules: Record<string, string> = {
    harmonic_analysis: "harmonic_structure",
    spectral_processing: "spectrogram",
    spatial_audio: "stereo",
    rhythmic_structure: "beat_grid",
    music_generation: "song_structure",
    psychoacoustics: "perceptual_model",
  };
  for (const fw of frameworks) {
    const expected = knownModules[fw];
    if (expected && !concepts.includes(expected)) {
      goals.push({ goal: `Deepen ${fw} integration`, priority: "low", rationale: `Framework referenced but not fully implemented`, estimated_impact: "R_context (theoretical depth)", source: "reverse_inference" });
    }
  }

  // Confidence
  const signals = [purpose !== "Purpose not detected", frameworks.length > 0, concepts.length > 0, patterns.length > 0, true];
  const confidence = signals.filter(Boolean).length / signals.length;

  return {
    purpose,
    architecture,
    frameworks,
    patterns,
    concepts,
    confidence,
    coverage: Math.round(coverage * 100) / 100,
    goals,
    incomplete,
    undocumented,
  };
}

export async function POST(request: Request) {
  try {
    const { code } = await request.json();
    if (!code || typeof code !== "string") {
      return NextResponse.json({ error: "Code is required" }, { status: 400 });
    }
    const result = analyze(code);
    return NextResponse.json(result);
  } catch {
    return NextResponse.json({ error: "Analysis failed" }, { status: 500 });
  }
}
