import { z } from "zod";
import { IdentityVectorSchema } from "./IdentityVector";

export type { IdentityVector } from "./IdentityVector";
export { IdentityVectorSchema, createDefaultVector, validateVector } from "./IdentityVector";

// --- Synergy Request / Response Types ---

export const InterestSchema = z.object({
  category: z.string().min(1),
  weight: z.number(),
});

export type Interest = z.infer<typeof InterestSchema>;

export const UserProfileSchema = z.object({
  user_id: z.string().min(1),
  interests: z.array(InterestSchema).optional(),
  identity_vector: IdentityVectorSchema.optional(),
});

export type UserProfile = z.infer<typeof UserProfileSchema>;

export const SynergyRequestSchema = z.object({
  user_a: UserProfileSchema,
  user_b: UserProfileSchema,
});

export type SynergyRequest = z.infer<typeof SynergyRequestSchema>;

export interface SynergyBreakdown {
  privacy_level?: string;
  synergy_score?: number;
  interest_match?: number;
}

export interface SynergyScore {
  agent_id_a: string;
  agent_id_b: string;
  score: number;
  method: string;
  breakdown: SynergyBreakdown;
}

export interface SynergyResponse {
  synergy: SynergyScore;
}

export interface ErrorResponse {
  error: string;
  code: number;
}
