import { IdentityDimensions, XAlgorithmParams } from "../synergy/engine";

/**
 * Sample identity profiles for testing
 * In production, these would come from user profiles or authentication
 */
export const sampleIdentities = {
  analytical: {
    IE: 0.3,
    SN: 0.7,
    TF: 0.8,
    JP: 0.6,
    EmotionalStability: 0.7,
    Openness: 0.8,
    Conscientiousness: 0.9,
    Agreeableness: 0.4,
    RiskTolerance: 0.6,
    Empathy: 0.5,
    SocialIntelligence: 0.5,
    Creativity: 0.7,
    Logic: 0.9,
    Ambition: 0.8,
    Adaptability: 0.6,
    Altruism: 0.5,
  } as IdentityDimensions,

  empathetic: {
    IE: -0.5,
    SN: 0.5,
    TF: -0.7,
    JP: -0.4,
    EmotionalStability: 0.6,
    Openness: 0.9,
    Conscientiousness: 0.7,
    Agreeableness: 0.9,
    RiskTolerance: 0.3,
    Empathy: 0.95,
    SocialIntelligence: 0.85,
    Creativity: 0.8,
    Logic: 0.5,
    Ambition: 0.5,
    Adaptability: 0.8,
    Altruism: 0.9,
  } as IdentityDimensions,

  creative: {
    IE: 0.0,
    SN: 0.9,
    TF: 0.2,
    JP: -0.6,
    EmotionalStability: 0.5,
    Openness: 0.95,
    Conscientiousness: 0.4,
    Agreeableness: 0.6,
    RiskTolerance: 0.8,
    Empathy: 0.7,
    SocialIntelligence: 0.6,
    Creativity: 0.95,
    Logic: 0.6,
    Ambition: 0.7,
    Adaptability: 0.9,
    Altruism: 0.6,
  } as IdentityDimensions,
};

/**
 * Generate default identity dimensions (neutral profile)
 */
export function getDefaultIdentity(): IdentityDimensions {
  return {
    IE: 0.0,
    SN: 0.0,
    TF: 0.0,
    JP: 0.0,
    EmotionalStability: 0.5,
    Openness: 0.5,
    Conscientiousness: 0.5,
    Agreeableness: 0.5,
    RiskTolerance: 0.5,
    Empathy: 0.5,
    SocialIntelligence: 0.5,
    Creativity: 0.5,
    Logic: 0.5,
    Ambition: 0.5,
    Adaptability: 0.5,
    Altruism: 0.5,
  };
}

/**
 * Get identity by user ID
 * In production, this would fetch from a database or API
 *
 * @param userId - User identifier
 * @returns Identity dimensions for the user
 */
export async function getIdentityByUserId(userId: string): Promise<IdentityDimensions> {
  // TODO: Implement actual database/API lookup
  // For now, return a sample identity based on userId hash
  const hash = userId.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const profiles = Object.values(sampleIdentities);
  return profiles[hash % profiles.length];
}

/**
 * Get current user's identity
 * In production, this would use authentication context
 *
 * @returns Current user's identity dimensions
 */
export async function getCurrentUserIdentity(): Promise<IdentityDimensions> {
  // TODO: Integrate with NextAuth or authentication system
  // For now, return default identity
  return getDefaultIdentity();
}

/**
 * Generate X-Algorithm parameters based on interaction context
 *
 * @param context - Interaction context (e.g., from session or analytics)
 * @returns X-Algorithm parameters
 */
export function generateXParams(context?: {
  dwellTime?: number;
  interactions?: number;
  hasInteracted?: boolean;
}): XAlgorithmParams {
  return {
    dwellTimeSeconds: context?.dwellTime ?? 30, // Default 30 seconds
    shareVelocity: context?.interactions ?? 0.5, // Default moderate velocity
    reciprocalInteraction: context?.hasInteracted ?? false,
  };
}

/**
 * Convenience function to get all data needed for mediation
 *
 * @param userIdA - First user ID
 * @param userIdB - Second user ID
 * @param context - Optional interaction context
 * @returns Complete data for mediation request
 */
export async function getMediationData(
  userIdA?: string,
  userIdB?: string,
  context?: {
    dwellTime?: number;
    interactions?: number;
    hasInteracted?: boolean;
  },
) {
  const identityA = userIdA ? await getIdentityByUserId(userIdA) : await getCurrentUserIdentity();

  const identityB = userIdB ? await getIdentityByUserId(userIdB) : sampleIdentities.empathetic; // Default to empathetic profile for B

  const xParams = generateXParams(context);

  return {
    identityA,
    identityB,
    xParams,
  };
}
