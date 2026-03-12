import { z } from "zod";

export const CORE_CHANNEL_ORDER = [
  "src",
  "obj",
  "ctr",
  "spa",
  "tmp",
  "mat",
  "act",
  "sty",
  "view",
  "merged",
] as const;

export const EXTRA_CHANNEL_ORDER = [
  "depth_desc",
  "segment_desc",
  "keypoint_desc",
  "motion_desc",
  "lighting_desc",
  "symbol_desc",
  "topology_desc",
  "voice_desc",
  "spectral_desc",
  "event_desc",
  "localization_desc",
  "normal_desc",
  "texture_desc",
  "mass_desc",
  "interaction_desc",
] as const;

export const CHANNEL_ORDER = [...CORE_CHANNEL_ORDER, ...EXTRA_CHANNEL_ORDER] as const;

export const DERIVED_MAP_KINDS = [
  "object_map",
  "contour_map",
  "space_graph",
  "depth_map",
  "segment_map",
  "keypoint_map",
  "flow_map",
  "material_map",
  "lighting_map",
  "symbol_map",
  "topology_graph",
  "normal_map",
  "texture_map",
  "mass_map",
  "interaction_graph",
  "voiceprint_map",
  "spectrogram_map",
  "event_density_map",
  "source_localization_map",
] as const;

export const RENDERER_TARGETS = ["image", "audio", "model3d"] as const;

export type ChannelKey = (typeof CHANNEL_ORDER)[number];
export type DerivedMapKind = (typeof DERIVED_MAP_KINDS)[number];
export type RendererTarget = (typeof RENDERER_TARGETS)[number];

export const SceneChannelItemSchema = z.object({
  id: z.string(),
  text: z.string().min(1),
  target: z.string().nullable().default(null),
  confidence: z.number().min(0).max(1),
  source: z.array(z.string()).default([]),
  tags: z.array(z.string()).default([]),
  nodeRefs: z.array(z.string()).default([]),
  mapRefs: z.array(z.string()).default([]),
  params: z.record(z.string(), z.unknown()).default({}),
});

export type SceneChannelItem = z.infer<typeof SceneChannelItemSchema>;

export const SceneChannelSchema = z.object({
  key: z.enum(CHANNEL_ORDER),
  label: z.string(),
  description: z.string(),
  allowDuplicates: z.boolean(),
  items: z.array(SceneChannelItemSchema),
});

export type SceneChannel = z.infer<typeof SceneChannelSchema>;

export const SceneNodeSchema = z.object({
  nodeId: z.string(),
  label: z.string(),
  type: z.string(),
  aliases: z.array(z.string()).default([]),
  tags: z.array(z.string()).default([]),
  attributes: z.record(z.string(), z.unknown()).default({}),
});

export type SceneNode = z.infer<typeof SceneNodeSchema>;

export const SceneEdgeSchema = z.object({
  edgeId: z.string(),
  fromNodeId: z.string(),
  toNodeId: z.string(),
  relation: z.string(),
  weight: z.number().min(0).max(1),
  tags: z.array(z.string()).default([]),
  sourceItemIds: z.array(z.string()).default([]),
  note: z.string().default(""),
});

export type SceneEdge = z.infer<typeof SceneEdgeSchema>;

export const SceneLinkSchema = z.object({
  fromChannel: z.enum(CHANNEL_ORDER),
  fromItemId: z.string(),
  toChannel: z.enum(CHANNEL_ORDER),
  toItemId: z.string(),
  relation: z.string(),
  strength: z.number().min(0).max(1),
  note: z.string(),
});

export type SceneLink = z.infer<typeof SceneLinkSchema>;

export const DerivedMapSchema = z.object({
  mapId: z.string(),
  kind: z.enum(DERIVED_MAP_KINDS),
  sourceChannels: z.array(z.enum(CHANNEL_ORDER)),
  sourceItemIds: z.array(z.string()).default([]),
  nodeIds: z.array(z.string()).default([]),
  tags: z.array(z.string()).default([]),
  payload: z.record(z.string(), z.unknown()).default({}),
});

export type DerivedMap = z.infer<typeof DerivedMapSchema>;

export const RendererInputSchema = z.object({
  target: z.enum(RENDERER_TARGETS),
  prompt: z.string(),
  conditions: z.array(z.string()),
  emphasis: z.array(z.string()),
  graphRefs: z.object({
    nodeIds: z.array(z.string()),
    edgeIds: z.array(z.string()),
    mapIds: z.array(z.string()),
  }),
});

export type RendererInput = z.infer<typeof RendererInputSchema>;

export const SceneDistillationSchema = z.object({
  schemaVersion: z.literal("0.3"),
  input: z.object({
    rawText: z.string().min(1),
    normalizedText: z.string().min(1),
  }),
  channels: z.array(SceneChannelSchema).length(CHANNEL_ORDER.length),
  nodes: z.array(SceneNodeSchema),
  edges: z.array(SceneEdgeSchema),
  links: z.array(SceneLinkSchema),
  derivedMaps: z.array(DerivedMapSchema),
  renderers: z.array(RendererInputSchema).length(RENDERER_TARGETS.length),
});

export type SceneDistillation = z.infer<typeof SceneDistillationSchema>;

const CHANNEL_META: Record<ChannelKey, { label: string; description: string; allowDuplicates: boolean }> = {
  src: { label: "全文", description: "原文そのもの。", allowDuplicates: true },
  obj: { label: "物体・主体", description: "存在要素の列挙。", allowDuplicates: true },
  ctr: { label: "輪郭・形態", description: "形・境界・シルエット。", allowDuplicates: true },
  spa: { label: "空間・配置", description: "位置関係・前後・距離。", allowDuplicates: true },
  tmp: { label: "時間・変化", description: "順序・速度・変化率。", allowDuplicates: true },
  mat: { label: "素材・質感・物性", description: "材質や触感。", allowDuplicates: true },
  act: { label: "動作・作用", description: "動き・姿勢・作用。", allowDuplicates: true },
  sty: { label: "感覚属性・雰囲気", description: "トーンや空気感。", allowDuplicates: true },
  view: { label: "視点・観測条件", description: "観測者位置やカメラ感。", allowDuplicates: true },
  merged: { label: "非重複統合説明", description: "統合された要約説明。", allowDuplicates: false },
  depth_desc: { label: "深度説明", description: "奥行きや距離層の説明。", allowDuplicates: true },
  segment_desc: { label: "領域分割説明", description: "セグメントや領域境界。", allowDuplicates: true },
  keypoint_desc: { label: "キーポイント説明", description: "関節・支点・特徴点。", allowDuplicates: true },
  motion_desc: { label: "動きマップ説明", description: "運動方向やフロー。", allowDuplicates: true },
  lighting_desc: { label: "照明説明", description: "光源・陰影・発光。", allowDuplicates: true },
  symbol_desc: { label: "記号説明", description: "文字・記号・UI的要素。", allowDuplicates: true },
  topology_desc: { label: "トポロジー説明", description: "接続や連結構造。", allowDuplicates: true },
  voice_desc: { label: "声紋説明", description: "声質・話者性の説明。", allowDuplicates: true },
  spectral_desc: { label: "スペクトル説明", description: "周波数構造の説明。", allowDuplicates: true },
  event_desc: { label: "イベント密度説明", description: "onsetやイベント発生密度。", allowDuplicates: true },
  localization_desc: { label: "定位説明", description: "音源や観測源の方向。", allowDuplicates: true },
  normal_desc: { label: "法線説明", description: "面の向きや傾き。", allowDuplicates: true },
  texture_desc: { label: "テクスチャ説明", description: "表面パターン。", allowDuplicates: true },
  mass_desc: { label: "質量感説明", description: "重さ・密度・慣性印象。", allowDuplicates: true },
  interaction_desc: { label: "相互作用説明", description: "接触・反応・干渉。", allowDuplicates: true },
};

const HINTS = {
  sty: ["薄暗い", "静かな", "不穏", "幻想", "工業", "温かい", "冷たい", "ざらつ", "柔らか", "重い空気"],
  mat: ["金属", "木", "ガラス", "布", "液体", "霧", "煙", "石", "紙", "皮", "白い", "透明"],
  view: ["見下ろし", "見上げ", "俯瞰", "主観", "客観", "近距離", "遠景", "広角", "望遠", "手持ち", "固定カメラ", "耳元", "遠くで"],
  tmp: ["ゆっくり", "徐々に", "一瞬", "突然", "連続", "反復", "周期", "揺れる", "流れる", "点滅", "高速", "低速"],
  act: ["立つ", "座る", "歩く", "走る", "開く", "閉じる", "落ちる", "浮かぶ", "揺れる", "光る", "鳴る", "反響", "置かれている"],
  ctr: ["円", "丸", "球", "四角", "長方形", "三角", "線", "シルエット", "輪郭", "境界", "曲線", "矩形", "円筒", "縦長", "横長"],
  spa: ["手前", "奥", "前景", "中景", "背景", "左", "右", "上", "下", "中央", "窓際", "上に", "下に", "間に", "隣", "内側", "外側"],
  depth_desc: ["奥", "手前", "遠く", "近く", "背景", "前景"],
  segment_desc: ["領域", "境界", "分割", "面", "背景", "前景"],
  keypoint_desc: ["手", "足", "顔", "目", "肩", "関節", "指"],
  motion_desc: ["動く", "走る", "揺れる", "流れる", "点滅", "高速", "低速"],
  lighting_desc: ["光", "照", "影", "逆光", "発光", "薄暗い", "暗い", "明るい"],
  symbol_desc: ["文字", "記号", "数字", "看板", "UI", "ボタン"],
  topology_desc: ["つなが", "接続", "枝", "穴", "連結", "閉じ"],
  voice_desc: ["声", "囁", "叫", "歌", "話し声", "発声"],
  spectral_desc: ["高音", "低音", "倍音", "ノイズ", "周波", "スペクト"],
  event_desc: ["一瞬", "突然", "断続", "連続", "onset", "拍"],
  localization_desc: ["左から", "右から", "遠くで", "耳元", "背後", "前方"],
  normal_desc: ["面", "傾", "向き", "角度", "法線"],
  texture_desc: ["ざら", "滑ら", "粒", "模様", "テクスチャ"],
  mass_desc: ["重い", "軽い", "密度", "圧", "慣性"],
  interaction_desc: ["接触", "ぶつか", "反射", "押す", "引く", "干渉"],
} satisfies Partial<Record<ChannelKey, string[]>>;

const STOPWORDS = new Set(["こと", "もの", "よう", "ため", "それ", "これ", "あれ", "そこ", "ここ", "そして", "しかし"]);

function normalizeWhitespace(text: string): string {
  return text.replace(/\s+/g, " ").replace(/[。]+/g, "。 ").trim();
}

function splitClauses(text: string): string[] {
  return text.split(/[。！？!?.\n]+/).map((s) => s.trim()).filter(Boolean);
}

function normalizeForSimilarity(text: string): string {
  return text.replace(/\s+/g, "").replace(/[。、「」,，・]/g, "");
}

function tokenizeForSimilarity(text: string): string[] {
  const compact = normalizeForSimilarity(text);
  if (compact.length <= 1) return compact ? [compact] : [];
  const chars = [...compact];
  const out: string[] = [];
  for (let i = 0; i < chars.length - 1; i += 1) out.push(`${chars[i]}${chars[i + 1]}`);
  return out;
}

function similarityScore(a: string, b: string): number {
  const aTokens = new Set(tokenizeForSimilarity(a));
  const bTokens = new Set(tokenizeForSimilarity(b));
  if (aTokens.size === 0 || bTokens.size === 0) return normalizeForSimilarity(a) === normalizeForSimilarity(b) ? 1 : 0;
  let overlap = 0;
  for (const token of aTokens) if (bTokens.has(token)) overlap += 1;
  return overlap / Math.max(aTokens.size, bTokens.size);
}

function uniqueSentences(sentences: string[], threshold = 0.78): string[] {
  const deduped: string[] = [];
  for (const sentence of sentences) {
    if (!normalizeForSimilarity(sentence)) continue;
    if (!deduped.some((existing) => similarityScore(existing, sentence) >= threshold)) deduped.push(sentence.trim());
  }
  return deduped;
}

function inferTemporalRate(text: string): "low" | "medium" | "high" {
  if (/(高速|激しく|一瞬|突然|点滅|連続)/.test(text)) return "high";
  if (/(ゆっくり|徐々に|揺れる|流れる|反復)/.test(text)) return "medium";
  return "low";
}

function extractCandidateNouns(clause: string): string[] {
  const matches = clause.match(/[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}A-Za-z0-9_-]{2,16}/gu) ?? [];
  return matches.filter((token) => !STOPWORDS.has(token) && !/^(いる|ある|する|なる|して|です|ます|その|この|あの)$/.test(token));
}

function detectObjectLikePhrases(clauses: string[]): string[] {
  const nouns = new Map<string, { clause: string; score: number }>();
  for (const clause of clauses) {
    for (const noun of extractCandidateNouns(clause)) {
      const score = (clause.includes(noun) ? 1 : 0) + (/(が|は|を|に|の)/.test(clause) ? 0.2 : 0);
      const existing = nouns.get(noun);
      if (!existing || existing.score < score) nouns.set(noun, { clause, score });
    }
  }
  return [...nouns.entries()]
    .sort((a, b) => b[1].score - a[1].score || a[0].length - b[0].length)
    .slice(0, 10)
    .map(([noun, v]) => `${noun}が場面の主要要素として存在する（文脈: ${v.clause}）`);
}

function buildGenericChannelItems(channel: ChannelKey, clauses: string[], fallback: string): string[] {
  const hints = HINTS[channel] ?? [];
  const hits = clauses.filter((clause) => hints.some((hint) => clause.includes(hint)));
  return hits.length > 0 ? uniqueSentences(hits.map((clause) => `${clause}として${CHANNEL_META[channel].label}の手掛かりを持つ`)) : [fallback];
}

function makeItem(channel: ChannelKey, index: number, text: string, overrides: Partial<SceneChannelItem> = {}): SceneChannelItem {
  return {
    id: `${channel}_${String(index + 1).padStart(3, "0")}`,
    text,
    target: overrides.target ?? null,
    confidence: overrides.confidence ?? 0.7,
    source: overrides.source ?? ["src"],
    tags: overrides.tags ?? [],
    nodeRefs: overrides.nodeRefs ?? [],
    mapRefs: overrides.mapRefs ?? [],
    params: overrides.params ?? {},
  };
}

function buildMergedExplanation(rawText: string, channelMap: Record<ChannelKey, SceneChannel>): string {
  const sourceSentences = splitClauses(rawText);
  const priority: ChannelKey[] = ["obj", "spa", "act", "ctr", "mat", "tmp", "sty", "view", "depth_desc", "lighting_desc", "motion_desc", "interaction_desc"];
  const selected: string[] = [];
  for (const key of priority) {
    const channel = channelMap[key];
    if (!channel) continue;
    for (const candidate of channel.items.map((i) => i.text)) {
      if (sourceSentences.some((source) => similarityScore(source, candidate) >= 0.72)) continue;
      if (selected.some((existing) => similarityScore(existing, candidate) >= 0.78)) continue;
      selected.push(candidate);
      if (selected.length >= 8) break;
    }
    if (selected.length >= 8) break;
  }
  if (selected.length === 0) return "原文と比較して追加の非重複統合説明はない。";
  return selected.map((s) => (/[。]$/.test(s) ? s : `${s}。`)).join(" ");
}

function createNodeId(label: string): string {
  return `node_${normalizeForSimilarity(label).slice(0, 24) || "unknown"}`;
}

function buildGraph(objItems: SceneChannelItem[], actItems: SceneChannelItem[], spaItems: SceneChannelItem[], matItems: SceneChannelItem[]): { nodes: SceneNode[]; edges: SceneEdge[]; labelToNodeId: Map<string, string> } {
  const labelToNodeId = new Map<string, string>();
  const nodes: SceneNode[] = [];

  for (const item of objItems) {
    const match = item.text.match(/^(.+?)が場面の主要要素として存在する/u);
    const label = match?.[1]?.trim();
    if (!label || labelToNodeId.has(label)) continue;
    const nodeId = createNodeId(label);
    labelToNodeId.set(label, nodeId);
    nodes.push({ nodeId, label, type: "entity", aliases: [], tags: ["object"], attributes: { sourceItemId: item.id } });
  }

  const sceneNodeId = "node_scene";
  if (!nodes.some((node) => node.nodeId === sceneNodeId)) {
    nodes.unshift({ nodeId: sceneNodeId, label: "scene", type: "scene", aliases: [], tags: ["root"], attributes: {} });
  }

  const edges: SceneEdge[] = [];
  for (const node of nodes) {
    if (node.nodeId === sceneNodeId) continue;
    edges.push({
      edgeId: `edge_scene_${node.nodeId}`,
      fromNodeId: sceneNodeId,
      toNodeId: node.nodeId,
      relation: "contains",
      weight: 0.8,
      tags: ["scene"],
      sourceItemIds: [String(node.attributes.sourceItemId ?? "")].filter(Boolean),
      note: "scene contains entity",
    });
  }

  const firstNode = nodes.find((node) => node.nodeId !== sceneNodeId);
  if (firstNode && actItems[0]) {
    edges.push({ edgeId: `edge_${firstNode.nodeId}_act`, fromNodeId: firstNode.nodeId, toNodeId: sceneNodeId, relation: "acts_in", weight: 0.64, tags: ["action"], sourceItemIds: [actItems[0].id], note: actItems[0].text });
  }
  if (firstNode && spaItems[0]) {
    edges.push({ edgeId: `edge_${firstNode.nodeId}_space`, fromNodeId: firstNode.nodeId, toNodeId: sceneNodeId, relation: "located_in", weight: 0.66, tags: ["space"], sourceItemIds: [spaItems[0].id], note: spaItems[0].text });
  }
  if (firstNode && matItems[0]) {
    edges.push({ edgeId: `edge_${firstNode.nodeId}_material`, fromNodeId: firstNode.nodeId, toNodeId: sceneNodeId, relation: "has_material_hint", weight: 0.58, tags: ["material"], sourceItemIds: [matItems[0].id], note: matItems[0].text });
  }

  return { nodes, edges, labelToNodeId };
}

function createDerivedMaps(channelMap: Record<ChannelKey, SceneChannel>, nodes: SceneNode[], edges: SceneEdge[]): DerivedMap[] {
  const sceneNodeIds = nodes.map((node) => node.nodeId);
  const map = (kind: DerivedMapKind, sourceChannels: ChannelKey[], sourceItemIds: string[], tags: string[], payload: Record<string, unknown>): DerivedMap => ({
    mapId: `map_${kind}`,
    kind,
    sourceChannels,
    sourceItemIds,
    nodeIds: sceneNodeIds,
    tags,
    payload,
  });

  return [
    map("object_map", ["obj"], channelMap.obj.items.map((i) => i.id), ["visual", "entity"], { labels: nodes.filter((n) => n.type === "entity").map((n) => n.label) }),
    map("contour_map", ["ctr"], channelMap.ctr.items.map((i) => i.id), ["visual", "shape"], { summary: channelMap.ctr.items.map((i) => i.text) }),
    map("space_graph", ["spa"], channelMap.spa.items.map((i) => i.id), ["visual", "layout"], { edgeIds: edges.filter((e) => e.tags.includes("space")).map((e) => e.edgeId) }),
    map("depth_map", ["depth_desc", "spa"], [...channelMap.depth_desc.items.map((i) => i.id), ...channelMap.spa.items.map((i) => i.id)], ["visual", "depth"], { summary: channelMap.depth_desc.items.map((i) => i.text) }),
    map("segment_map", ["segment_desc", "obj"], [...channelMap.segment_desc.items.map((i) => i.id), ...channelMap.obj.items.map((i) => i.id)], ["visual", "mask"], { segments: nodes.filter((n) => n.type === "entity").map((n) => n.label) }),
    map("keypoint_map", ["keypoint_desc"], channelMap.keypoint_desc.items.map((i) => i.id), ["pose"], { points: channelMap.keypoint_desc.items.map((i) => i.text) }),
    map("flow_map", ["motion_desc", "tmp"], [...channelMap.motion_desc.items.map((i) => i.id), ...channelMap.tmp.items.map((i) => i.id)], ["motion"], { temporalRate: channelMap.tmp.items[0]?.params.temporalRate ?? "low" }),
    map("material_map", ["mat", "texture_desc"], [...channelMap.mat.items.map((i) => i.id), ...channelMap.texture_desc.items.map((i) => i.id)], ["surface"], { materials: channelMap.mat.items.map((i) => i.text) }),
    map("lighting_map", ["lighting_desc", "sty"], [...channelMap.lighting_desc.items.map((i) => i.id), ...channelMap.sty.items.map((i) => i.id)], ["light"], { lighting: channelMap.lighting_desc.items.map((i) => i.text) }),
    map("symbol_map", ["symbol_desc"], channelMap.symbol_desc.items.map((i) => i.id), ["symbolic"], { symbols: channelMap.symbol_desc.items.map((i) => i.text) }),
    map("topology_graph", ["topology_desc", "interaction_desc"], [...channelMap.topology_desc.items.map((i) => i.id), ...channelMap.interaction_desc.items.map((i) => i.id)], ["graph"], { topology: channelMap.topology_desc.items.map((i) => i.text) }),
    map("normal_map", ["normal_desc"], channelMap.normal_desc.items.map((i) => i.id), ["surface", "orientation"], { normals: channelMap.normal_desc.items.map((i) => i.text) }),
    map("texture_map", ["texture_desc"], channelMap.texture_desc.items.map((i) => i.id), ["surface", "texture"], { textures: channelMap.texture_desc.items.map((i) => i.text) }),
    map("mass_map", ["mass_desc"], channelMap.mass_desc.items.map((i) => i.id), ["physics"], { masses: channelMap.mass_desc.items.map((i) => i.text) }),
    map("interaction_graph", ["interaction_desc", "act"], [...channelMap.interaction_desc.items.map((i) => i.id), ...channelMap.act.items.map((i) => i.id)], ["interaction"], { interactions: channelMap.interaction_desc.items.map((i) => i.text) }),
    map("voiceprint_map", ["voice_desc"], channelMap.voice_desc.items.map((i) => i.id), ["audio", "voice"], { voices: channelMap.voice_desc.items.map((i) => i.text) }),
    map("spectrogram_map", ["spectral_desc"], channelMap.spectral_desc.items.map((i) => i.id), ["audio", "frequency"], { spectral: channelMap.spectral_desc.items.map((i) => i.text) }),
    map("event_density_map", ["event_desc", "tmp"], [...channelMap.event_desc.items.map((i) => i.id), ...channelMap.tmp.items.map((i) => i.id)], ["audio", "temporal"], { events: channelMap.event_desc.items.map((i) => i.text) }),
    map("source_localization_map", ["localization_desc", "view"], [...channelMap.localization_desc.items.map((i) => i.id), ...channelMap.view.items.map((i) => i.id)], ["audio", "spatial"], { localization: channelMap.localization_desc.items.map((i) => i.text) }),
  ];
}

function attachRefs(channels: SceneChannel[], nodes: SceneNode[], derivedMaps: DerivedMap[]): SceneChannel[] {
  const entityNodes = nodes.filter((node) => node.type === "entity");
  return channels.map((channel) => ({
    ...channel,
    items: channel.items.map((item) => {
      const nodeRefs = entityNodes.filter((node) => item.text.includes(node.label)).map((node) => node.nodeId);
      const mapRefs = derivedMaps.filter((map) => map.sourceItemIds.includes(item.id)).map((map) => map.mapId);
      return { ...item, nodeRefs, mapRefs, tags: uniqueSentences([...item.tags, channel.key, ...nodeRefs.map(() => "node-linked"), ...mapRefs.map(() => "map-linked")], 1) };
    }),
  }));
}

function buildLinks(channelMap: Record<ChannelKey, SceneChannel>): SceneLink[] {
  const links: SceneLink[] = [];
  const push = (fromChannel: ChannelKey, toChannel: ChannelKey, relation: string, strength: number, note: string) => {
    const from = channelMap[fromChannel]?.items[0];
    const to = channelMap[toChannel]?.items[0];
    if (!from || !to) return;
    links.push({ fromChannel, fromItemId: from.id, toChannel, toItemId: to.id, relation, strength, note });
  };
  if (channelMap.tmp.items.some((i) => i.params.blurPotential === true)) push("tmp", "ctr", "modulates_blur", 0.88, "時間変化率が高いため輪郭ブラーへ効く");
  push("mat", "sty", "colors_mood", 0.62, "素材は雰囲気を色づける");
  push("spa", "view", "anchors_observer", 0.66, "空間配置が観測位置を初期化する");
  push("lighting_desc", "sty", "sculpts_mood", 0.74, "照明条件がムードを形成する");
  push("motion_desc", "tmp", "expresses_temporal_change", 0.71, "運動説明が時間変化を具体化する");
  push("voice_desc", "spectral_desc", "projects_to_spectrum", 0.69, "声質はスペクトル構造に影響する");
  push("interaction_desc", "topology_desc", "reshapes_connectivity", 0.57, "相互作用が接続構造を変える");
  return links;
}

function buildRendererInputs(channelMap: Record<ChannelKey, SceneChannel>, nodes: SceneNode[], edges: SceneEdge[], derivedMaps: DerivedMap[]): RendererInput[] {
  const nodeIds = nodes.map((n) => n.nodeId);
  const edgeIds = edges.map((e) => e.edgeId);
  const imageMapIds = derivedMaps.filter((m) => ["object_map", "contour_map", "space_graph", "depth_map", "lighting_map", "material_map", "texture_map"].includes(m.kind)).map((m) => m.mapId);
  const audioMapIds = derivedMaps.filter((m) => ["voiceprint_map", "spectrogram_map", "event_density_map", "source_localization_map"].includes(m.kind)).map((m) => m.mapId);
  const modelMapIds = derivedMaps.filter((m) => ["object_map", "depth_map", "normal_map", "material_map", "topology_graph", "interaction_graph", "mass_map"].includes(m.kind)).map((m) => m.mapId);

  const join = (keys: ChannelKey[], limit = 2) => keys.flatMap((key) => channelMap[key].items.slice(0, limit).map((i) => i.text)).join(" ");

  return [
    {
      target: "image",
      prompt: join(["src", "merged", "ctr", "spa", "depth_desc", "lighting_desc", "texture_desc", "sty", "view"], 1),
      conditions: ["shape-aware", "space-aware", "depth-aware", "lighting-aware"],
      emphasis: ["merged", "ctr", "spa", "depth_desc", "lighting_desc", "texture_desc"],
      graphRefs: { nodeIds, edgeIds, mapIds: imageMapIds },
    },
    {
      target: "audio",
      prompt: join(["src", "voice_desc", "spectral_desc", "event_desc", "localization_desc", "tmp", "sty"], 1),
      conditions: ["voiceprint", "spectral", "event-density", "spatial-audio"],
      emphasis: ["voice_desc", "spectral_desc", "event_desc", "localization_desc", "tmp"],
      graphRefs: { nodeIds, edgeIds, mapIds: audioMapIds },
    },
    {
      target: "model3d",
      prompt: join(["src", "obj", "ctr", "spa", "depth_desc", "normal_desc", "mat", "mass_desc", "interaction_desc", "topology_desc"], 1),
      conditions: ["object-layout", "depth-volume", "surface-orientation", "material-mass"],
      emphasis: ["obj", "ctr", "spa", "depth_desc", "normal_desc", "mat", "mass_desc", "interaction_desc"],
      graphRefs: { nodeIds, edgeIds, mapIds: modelMapIds },
    },
  ];
}

function toChannelMap(channels: SceneChannel[]): Record<ChannelKey, SceneChannel> {
  return Object.fromEntries(channels.map((channel) => [channel.key, channel])) as Record<ChannelKey, SceneChannel>;
}

export function distillSceneText(rawText: string): SceneDistillation {
  const normalizedText = normalizeWhitespace(rawText);
  const clauses = splitClauses(normalizedText);

  const channelBuilders: Record<ChannelKey, () => SceneChannel> = {
    src: () => ({ ...CHANNEL_META.src, key: "src", items: [makeItem("src", 0, normalizedText, { confidence: 1, source: ["raw"], tags: ["verbatim"] })] }),
    obj: () => ({ ...CHANNEL_META.obj, key: "obj", items: (detectObjectLikePhrases(clauses).length ? detectObjectLikePhrases(clauses) : ["主要な主体・物体が存在する"]).map((text, index) => makeItem("obj", index, text, { confidence: 0.82 })) }),
    ctr: () => ({ ...CHANNEL_META.ctr, key: "ctr", items: buildGenericChannelItems("ctr", clauses, "輪郭や形態の詳細は後段補完対象とする").map((text, index) => makeItem("ctr", index, text, { confidence: 0.72 })) }),
    spa: () => ({ ...CHANNEL_META.spa, key: "spa", items: buildGenericChannelItems("spa", clauses, "空間配置は中立的な場面構造として扱う").map((text, index) => makeItem("spa", index, text, { confidence: 0.74 })) }),
    tmp: () => ({ ...CHANNEL_META.tmp, key: "tmp", items: [makeItem("tmp", 0, `時間変化率は${inferTemporalRate(normalizedText)}として扱う`, { confidence: 0.65, source: ["src", "inferred"], params: { temporalRate: inferTemporalRate(normalizedText), blurPotential: inferTemporalRate(normalizedText) === "high" } }), ...buildGenericChannelItems("tmp", clauses, "時間変化は低く静的な場面として扱える").map((text, index) => makeItem("tmp", index + 1, text, { confidence: 0.7 }))] }),
    mat: () => ({ ...CHANNEL_META.mat, key: "mat", items: buildGenericChannelItems("mat", clauses, "素材や質感は後段補完対象とする").map((text, index) => makeItem("mat", index, text, { confidence: 0.7 })) }),
    act: () => ({ ...CHANNEL_META.act, key: "act", items: buildGenericChannelItems("act", clauses, "明示的な動作は少ないが状態保持として解釈できる").map((text, index) => makeItem("act", index, text, { confidence: 0.75 })) }),
    sty: () => ({ ...CHANNEL_META.sty, key: "sty", items: buildGenericChannelItems("sty", clauses, "全体の雰囲気は原文の語感から補完可能である").map((text, index) => makeItem("sty", index, text, { confidence: 0.79 })) }),
    view: () => ({ ...CHANNEL_META.view, key: "view", items: buildGenericChannelItems("view", clauses, "視点条件は中立的な観測位置として扱う").map((text, index) => makeItem("view", index, text, { confidence: 0.68 })) }),
    merged: () => ({ ...CHANNEL_META.merged, key: "merged", items: [] }),
    depth_desc: () => ({ ...CHANNEL_META.depth_desc, key: "depth_desc", items: buildGenericChannelItems("depth_desc", clauses, "奥行きは前景・中景・背景の3層として扱う").map((text, index) => makeItem("depth_desc", index, text, { confidence: 0.64 })) }),
    segment_desc: () => ({ ...CHANNEL_META.segment_desc, key: "segment_desc", items: buildGenericChannelItems("segment_desc", clauses, "領域分割は主要要素ごとに分離可能とみなす").map((text, index) => makeItem("segment_desc", index, text, { confidence: 0.58 })) }),
    keypoint_desc: () => ({ ...CHANNEL_META.keypoint_desc, key: "keypoint_desc", items: buildGenericChannelItems("keypoint_desc", clauses, "特徴点は姿勢や主要接点に集約される").map((text, index) => makeItem("keypoint_desc", index, text, { confidence: 0.55 })) }),
    motion_desc: () => ({ ...CHANNEL_META.motion_desc, key: "motion_desc", items: buildGenericChannelItems("motion_desc", clauses, "動きマップは低速または静置として扱う").map((text, index) => makeItem("motion_desc", index, text, { confidence: 0.63 })) }),
    lighting_desc: () => ({ ...CHANNEL_META.lighting_desc, key: "lighting_desc", items: buildGenericChannelItems("lighting_desc", clauses, "照明は中立的な拡散光として扱う").map((text, index) => makeItem("lighting_desc", index, text, { confidence: 0.71 })) }),
    symbol_desc: () => ({ ...CHANNEL_META.symbol_desc, key: "symbol_desc", items: buildGenericChannelItems("symbol_desc", clauses, "記号要素は明示されていない").map((text, index) => makeItem("symbol_desc", index, text, { confidence: 0.46 })) }),
    topology_desc: () => ({ ...CHANNEL_META.topology_desc, key: "topology_desc", items: buildGenericChannelItems("topology_desc", clauses, "接続構造はscene-root配下の連結として扱う").map((text, index) => makeItem("topology_desc", index, text, { confidence: 0.51 })) }),
    voice_desc: () => ({ ...CHANNEL_META.voice_desc, key: "voice_desc", items: buildGenericChannelItems("voice_desc", clauses, "声紋情報は未確定で、必要時に話者特性へ補完する").map((text, index) => makeItem("voice_desc", index, text, { confidence: 0.44 })) }),
    spectral_desc: () => ({ ...CHANNEL_META.spectral_desc, key: "spectral_desc", items: buildGenericChannelItems("spectral_desc", clauses, "スペクトル構造は広帯域または未確定として扱う").map((text, index) => makeItem("spectral_desc", index, text, { confidence: 0.45 })) }),
    event_desc: () => ({ ...CHANNEL_META.event_desc, key: "event_desc", items: buildGenericChannelItems("event_desc", clauses, "イベント密度は疎で静的な場面として扱う").map((text, index) => makeItem("event_desc", index, text, { confidence: 0.52 })) }),
    localization_desc: () => ({ ...CHANNEL_META.localization_desc, key: "localization_desc", items: buildGenericChannelItems("localization_desc", clauses, "定位情報は中央または未確定として扱う").map((text, index) => makeItem("localization_desc", index, text, { confidence: 0.49 })) }),
    normal_desc: () => ({ ...CHANNEL_META.normal_desc, key: "normal_desc", items: buildGenericChannelItems("normal_desc", clauses, "面方向は安定した法線場として扱う").map((text, index) => makeItem("normal_desc", index, text, { confidence: 0.53 })) }),
    texture_desc: () => ({ ...CHANNEL_META.texture_desc, key: "texture_desc", items: buildGenericChannelItems("texture_desc", clauses, "表面テクスチャは均質または後段補完対象とする").map((text, index) => makeItem("texture_desc", index, text, { confidence: 0.57 })) }),
    mass_desc: () => ({ ...CHANNEL_META.mass_desc, key: "mass_desc", items: buildGenericChannelItems("mass_desc", clauses, "質量感は中程度として扱う").map((text, index) => makeItem("mass_desc", index, text, { confidence: 0.5 })) }),
    interaction_desc: () => ({ ...CHANNEL_META.interaction_desc, key: "interaction_desc", items: buildGenericChannelItems("interaction_desc", clauses, "相互作用は弱いか未確定として扱う").map((text, index) => makeItem("interaction_desc", index, text, { confidence: 0.56 })) }),
  };

  const channels = CHANNEL_ORDER.map((key) => channelBuilders[key]());
  const channelMapBeforeMerged = toChannelMap(channels);
  const mergedText = buildMergedExplanation(normalizedText, channelMapBeforeMerged);
  const mergedChannelIndex = channels.findIndex((channel) => channel.key === "merged");
  channels[mergedChannelIndex] = { ...channels[mergedChannelIndex], items: [makeItem("merged", 0, mergedText, { confidence: 0.84, source: ["src", "obj", "spa", "act", "ctr", "mat", "tmp", "sty", "view"], tags: ["deduped", "integrated", "summary"] })] };

  const channelMap = toChannelMap(channels);
  const { nodes, edges } = buildGraph(channelMap.obj.items, channelMap.act.items, channelMap.spa.items, channelMap.mat.items);
  const links = buildLinks(channelMap);
  const derivedMaps = createDerivedMaps(channelMap, nodes, edges);
  const channelsWithRefs = attachRefs(channels, nodes, derivedMaps);
  const channelMapFinal = toChannelMap(channelsWithRefs);
  const renderers = buildRendererInputs(channelMapFinal, nodes, edges, derivedMaps);

  return SceneDistillationSchema.parse({
    schemaVersion: "0.3",
    input: { rawText, normalizedText },
    channels: channelsWithRefs,
    nodes,
    edges,
    links,
    derivedMaps,
    renderers,
  });
}
