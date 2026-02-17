import Anthropic from "@anthropic-ai/sdk";
import { config } from "dotenv";
import type { ChatMessage } from "./ProfilingEngine";

/**
 * Partial identity vector returned by LLM analysis.
 * All fields optional since the LLM may not extract everything.
 */
export interface PartialIdentityVector {
  personality?: Partial<{
    extraversion: number;
    intuition: number;
    thinking: number;
    judging: number;
  }>;
  values?: string[];
  professionalFocus?: string[];
  socialEnergy?: Partial<{
    battery: number;
    preferredTone: "concise" | "enthusiastic" | "professional" | "casual";
  }>;
}

/**
 * Adapter interface for LLM-based chat analysis.
 */
export interface LLMAdapter {
  analyze(messages: ChatMessage[]): Promise<PartialIdentityVector>;
}

const SYSTEM_PROMPT = `You are a psychological profiling assistant for the Katala identity system.
Analyze the provided chat history and extract personality traits, values, and expertise.

Return ONLY valid JSON matching this schema (all fields optional, omit what you can't determine):
{
  "personality": {
    "extraversion": 0.0-1.0,
    "intuition": 0.0-1.0,
    "thinking": 0.0-1.0,
    "judging": 0.0-1.0
  },
  "values": ["string array of core values"],
  "professionalFocus": ["string array of expertise areas"],
  "socialEnergy": {
    "battery": 0-100,
    "preferredTone": "concise" | "enthusiastic" | "professional" | "casual"
  }
}

Guidelines:
- extraversion: high = outgoing/talkative, low = reserved/brief
- intuition: high = abstract/theoretical, low = concrete/practical
- thinking: high = logical/analytical, low = empathetic/feeling-based
- judging: high = structured/planned, low = flexible/spontaneous
- Only include fields you have sufficient evidence for
- Values should reflect what the person cares about (e.g., "transparency", "efficiency")
- professionalFocus should reflect demonstrated expertise or interests`;

/**
 * Claude API adapter for LLM analysis.
 */
export class ClaudeLLMAdapter implements LLMAdapter {
  private client: Anthropic;

  constructor(apiKey?: string) {
    config(); // Load .env
    const key = apiKey ?? process.env.ANTHROPIC_API_KEY;
    if (!key) {
      throw new Error("ANTHROPIC_API_KEY is required. Set it in .env or pass it to the constructor.");
    }
    this.client = new Anthropic({ apiKey: key });
  }

  async analyze(messages: ChatMessage[]): Promise<PartialIdentityVector> {
    const chatContent = messages
      .map((m) => `[${m.role}] ${m.content}`)
      .join("\n");

    const response = await this.client.messages.create({
      model: "claude-sonnet-4-20250514",
      max_tokens: 1024,
      system: SYSTEM_PROMPT,
      messages: [
        {
          role: "user",
          content: `Analyze this chat history:\n\n${chatContent}`,
        },
      ],
    });

    const text =
      response.content[0].type === "text" ? response.content[0].text : "";

    try {
      return JSON.parse(text) as PartialIdentityVector;
    } catch {
      throw new Error(`Failed to parse LLM response as JSON: ${text}`);
    }
  }
}

/**
 * Mock adapter for testing. Returns a fixed or custom result.
 */
export class MockLLMAdapter implements LLMAdapter {
  private result: PartialIdentityVector;
  public callCount = 0;
  public lastMessages: ChatMessage[] = [];

  constructor(result?: PartialIdentityVector) {
    this.result = result ?? {
      personality: { extraversion: 0.7, thinking: 0.8 },
      values: ["transparency"],
      professionalFocus: ["TypeScript", "AI Architecture"],
      socialEnergy: { battery: 50, preferredTone: "concise" },
    };
  }

  async analyze(messages: ChatMessage[]): Promise<PartialIdentityVector> {
    this.callCount++;
    this.lastMessages = messages;
    return this.result;
  }
}
