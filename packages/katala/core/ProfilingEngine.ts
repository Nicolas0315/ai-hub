import { IdentityVector } from "./types";
import { LLMAdapter, MockLLMAdapter } from "./llm-adapter";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export class ProfilingEngine {
  private adapter: LLMAdapter;

  constructor(adapter?: LLMAdapter) {
    this.adapter = adapter ?? new MockLLMAdapter();
  }

  /**
   * Analyzes chat history to update the user's Identity Vector.
   */
  async updateProfile(
    currentVector: IdentityVector,
    history: ChatMessage[]
  ): Promise<IdentityVector> {
    const analysis = await this.adapter.analyze(history);

    const updatedVector: IdentityVector = {
      ...currentVector,
      personality: {
        ...currentVector.personality,
        ...analysis.personality,
      },
      values: Array.from(
        new Set([...currentVector.values, ...(analysis.values ?? [])])
      ),
      professionalFocus: Array.from(
        new Set([
          ...currentVector.professionalFocus,
          ...(analysis.professionalFocus ?? []),
        ])
      ),
      socialEnergy: {
        ...currentVector.socialEnergy,
        ...analysis.socialEnergy,
      },
      meta: {
        confidenceScore: this.calculateConfidence(history),
        lastUpdated: new Date().toISOString(),
      },
    };

    return updatedVector;
  }

  /**
   * Process explicit user requests for profile adjustment ("Dialogue Tuning").
   */
  async tuneProfile(
    currentVector: IdentityVector,
    tuningInstruction: string
  ): Promise<IdentityVector> {
    console.log(`Tuning profile with instruction: ${tuningInstruction}`);

    const updated = { ...currentVector };
    if (tuningInstruction.includes("outgoing")) {
      updated.personality = {
        ...updated.personality,
        extraversion: Math.min(1, updated.personality.extraversion + 0.2),
      };
    }

    updated.meta = {
      ...updated.meta,
      lastUpdated: new Date().toISOString(),
      confidenceScore: Math.min(1, updated.meta.confidenceScore + 0.1),
    };

    return updated;
  }

  private calculateConfidence(history: ChatMessage[]): number {
    const messageCount = history.length;
    const baseConfidence = Math.min(messageCount / 50, 0.9);
    return baseConfidence;
  }
}
