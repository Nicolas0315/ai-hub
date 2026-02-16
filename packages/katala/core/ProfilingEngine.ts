import { Fact, IdentityVector, OpenVisibilityRule } from './types';

export class ProfilingEngine {
  /**
   * ログから事実(Fact)を抽出するコアロジック
   * ZeroClawのHygiene思想に基づき、ノイズ除去と正規化を行う
   */
  async extractFactsFromLog(log: string): Promise<Fact[]> {
    // TODO: LLM (Gemini 3 Flash) を用いた抽出プロンプトの実行
    // 現状はモックとして、特定のキーワードを検知するロジックをシミュレート
    const facts: Fact[] = [];
    if (log.includes('Rust')) facts.push({ category: 'skill', value: 'Rust', confidence: 0.8, evidence: log });
    if (log.includes('ビットコイン')) facts.push({ category: 'interest', value: 'Bitcoin', confidence: 0.9, evidence: log });
    return facts;
  }

  /**
   * 抽出された事実を公開ルール(.openvisibility)に照らしてフィルタリングし、
   * STAGINGエリア（承認待ち）へ送る
   */
  async processToStaging(facts: Fact[], rules: OpenVisibilityRule[]): Promise<Fact[]> {
    return facts.filter(fact => {
      const rule = rules.find(r => r.category === fact.category && r.value === fact.value);
      return rule ? rule.level !== 'IGNORE' : true; // デフォルトは通す
    });
  }

  /**
   * 承認された事実を本番のIdentityVectorに統合(Commit)する
   * 重複がある場合はConfidenceをマージする（Hygieneロジック）
   */
  commitToVector(currentVector: IdentityVector, approvedFacts: Fact[]): IdentityVector {
    const newVector = { ...currentVector };
    approvedFacts.forEach(fact => {
      const existing = newVector.facts.find(f => f.category === fact.category && f.value === fact.value);
      if (existing) {
        // 重複排除ロジック: 確信度を漸進的に向上させる
        existing.confidence = Math.min(1.0, existing.confidence + (1 - existing.confidence) * 0.2);
      } else {
        newVector.facts.push(fact);
      }
    });
    return newVector;
  }
}
