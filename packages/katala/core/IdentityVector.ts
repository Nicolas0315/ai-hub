import { z } from "zod";

const personalityValue = z.number().min(0.0).max(1.0);

export const IdentityVectorSchema = z.object({
  personality: z.object({
    extraversion: personalityValue,
    intuition: personalityValue,
    thinking: personalityValue,
    judging: personalityValue,
  }),
  values: z.array(z.string()),
  professionalFocus: z.array(z.string()),
  socialEnergy: z.object({
    battery: z.number().min(0).max(100),
    preferredTone: z.enum(["concise", "enthusiastic", "professional", "casual"]),
  }),
  meta: z.object({
    confidenceScore: z.number().min(0).max(1),
    lastUpdated: z.string().datetime(),
  }),
});

export type IdentityVector = z.infer<typeof IdentityVectorSchema>;

export function createDefaultVector(): IdentityVector {
  return {
    personality: {
      extraversion: 0.5,
      intuition: 0.5,
      thinking: 0.5,
      judging: 0.5,
    },
    values: [],
    professionalFocus: [],
    socialEnergy: {
      battery: 50,
      preferredTone: "casual",
    },
    meta: {
      confidenceScore: 0,
      lastUpdated: new Date().toISOString(),
    },
  };
}

export function validateVector(input: unknown): IdentityVector {
  return IdentityVectorSchema.parse(input);
}
