const AGGRESSIVE_PATTERNS: Array<[RegExp, string]> = [
  [/\b(死ね|殺す|潰す)\b/g, "取り下げ"],
  [/\b(バカ|無能|ゴミ)\b/g, "課題"],
  [/\b(must|絶対|今すぐ)\b/gi, "優先"],
];

export function detoxText(input: string): string {
  return AGGRESSIVE_PATTERNS.reduce((text, [pattern, replacement]) => {
    return text.replace(pattern, replacement);
  }, input).trim();
}

export function inferPriority(text: string): "low" | "medium" | "high" {
  if (/(至急|urgent|asap|critical)/i.test(text)) return "high";
  if (/(今日|soon|priority)/i.test(text)) return "medium";
  return "low";
}
