import { SynergyEngine, EngagementMetrics } from "./SynergyEngine";
import { IdentityVector, MBTIPlusPlus } from "./types";

function createMockPersonality(value: number): MBTIPlusPlus {
  return {
    extraversion_introversion: value,
    sensing_intuition: value,
    thinking_feeling: value,
    judging_perceiving: value,
    assertive_turbulent: value,
    systematic_adaptive: value,
    direct_diplomatic: value,
    individualism_collectivism: value,
    practical_theoretical: value,
    fast_deliberate: value,
    cautious_bold: value,
    micro_macro: value,
    internal_external: value,
    task_people: value,
    proactive_reactive: value,
    mode_specialist_generalist: value,
  };
}

function createMockVector(personalityValue: number, confidence: number): IdentityVector {
  return {
    personality: createMockPersonality(personalityValue),
    values: ["growth", "autonomy"],
    professionalFocus: ["typescript", "ai"],
    socialEnergy: {
      battery: 0.8,
      preferredTone: "professional",
    },
    meta: {
      confidenceScore: confidence,
      lastUpdated: new Date().toISOString(),
    },
  };
}

const engine = new SynergyEngine();

// Test 1: Perfect Alignment
const v1 = createMockVector(1.0, 1.0);
const v2 = createMockVector(1.0, 1.0);
console.log("--- Test 1: Perfect Alignment ---");
const res1 = engine.calculateSynergy(v1, v2);
engine.logMetrics(res1);

// Test 2: Complete Opposites
const v3 = createMockVector(0.0, 1.0);
console.log("\n--- Test 2: Complete Opposites ---");
const res2 = engine.calculateSynergy(v1, v3);
engine.logMetrics(res2);

// Test 3: High Engagement Boost
console.log("\n--- Test 3: High Engagement Boost ---");
const engagement: EngagementMetrics = {
  dwellTimeSeconds: 300,
  shareVelocity: 0.8,
  reciprocalInteraction: 0.9,
  clickProbability: 0.7,
  negativeFeedback: 0,
};
const res3 = engine.calculateSynergy(v1, v2, engagement);
engine.logMetrics(res3);

// Test 4: Negative Feedback Impact
console.log("\n--- Test 4: Negative Feedback Impact ---");
const negativeEngagement: EngagementMetrics = {
  dwellTimeSeconds: 5,
  shareVelocity: 0,
  reciprocalInteraction: 0,
  clickProbability: 0.1,
  negativeFeedback: 1.0,
};
const res4 = engine.calculateSynergy(v1, v2, negativeEngagement);
engine.logMetrics(res4);
