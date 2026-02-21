import { KaniMediationResponse } from "./types";

/**
 * Mock mediation response for testing when Kani API is unavailable
 */
export const mockMediationResponse: KaniMediationResponse = {
  mediationScore: 78.5,
  synergyScore: 82.3,
  recommendations: [
    "共通の価値観を重視したコミュニケーション",
    "相互理解を深めるための対話時間の確保",
    "柔軟性を持った意思決定プロセス",
  ],
  timestamp: new Date().toISOString(),
  status: "success",
};

/**
 * Generate mock response with some randomization
 */
export function generateMockResponse(): KaniMediationResponse {
  const baseScore = 50 + Math.random() * 40; // 50-90 range
  const variance = (Math.random() - 0.5) * 10;

  return {
    mediationScore: Math.round((baseScore + variance) * 10) / 10,
    synergyScore: Math.round((baseScore + variance + 5) * 10) / 10,
    recommendations: [
      "共通の価値観を重視したコミュニケーション",
      "相互理解を深めるための対話時間の確保",
      "柔軟性を持った意思決定プロセス",
      "双方のストレングスを活かした協力体制",
    ].slice(0, Math.floor(Math.random() * 2) + 2),
    timestamp: new Date().toISOString(),
    status: "success",
  };
}
