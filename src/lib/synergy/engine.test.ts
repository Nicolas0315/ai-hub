import { SynergyEngine, IdentityDimensions, XAlgorithmParams } from './engine';

describe('SynergyEngine', () => {
  const engine = new SynergyEngine();

  const mockIdentity1: IdentityDimensions = {
    IE: 1, SN: 1, TF: 1, JP: 1,
    EmotionalStability: 1, Openness: 1, Conscientiousness: 1, Agreeableness: 1,
    RiskTolerance: 1, Empathy: 1, SocialIntelligence: 1, Creativity: 1,
    Logic: 1, Ambition: 1, Adaptability: 1, Altruism: 1
  };

  const mockIdentity2: IdentityDimensions = {
    IE: 1, SN: 1, TF: 1, JP: 1,
    EmotionalStability: 1, Openness: 1, Conscientiousness: 1, Agreeableness: 1,
    RiskTolerance: 1, Empathy: 1, SocialIntelligence: 1, Creativity: 1,
    Logic: 1, Ambition: 1, Adaptability: 1, Altruism: 1
  };

  const xParams: XAlgorithmParams = {
    dwellTimeSeconds: 60,
    shareVelocity: 2,
    reciprocalInteraction: true
  };

  test('should calculate a high synergy score for identical profiles', () => {
    const score = engine.getCombinedSynergy(mockIdentity1, mockIdentity2, xParams);
    expect(score).toBeGreaterThan(100);
  });

  test('should increase score with higher dwell time', () => {
    const scoreLow = engine.calculateXRankerScore(100, { ...xParams, dwellTimeSeconds: 10 });
    const scoreHigh = engine.calculateXRankerScore(100, { ...xParams, dwellTimeSeconds: 1000 });
    expect(scoreHigh).toBeGreaterThan(scoreLow);
  });

  test('should increase score with reciprocal interaction', () => {
    const scoreNoRecip = engine.calculateXRankerScore(100, { ...xParams, reciprocalInteraction: false });
    const scoreRecip = engine.calculateXRankerScore(100, { ...xParams, reciprocalInteraction: true });
    expect(scoreRecip).toBeGreaterThan(scoreNoRecip);
  });
});
