import { describe, expect, test } from 'vitest';

import { IdentityDimensions } from '../synergy/engine';
import {
  AgentSurfaceProfile,
  createSurfaceConnection,
  toPublicIdentityVector,
  updateSurfaceConnectionState,
} from './connection';

const identity: IdentityDimensions = {
  IE: 0.2,
  SN: -0.1,
  TF: 0.7,
  JP: 0.4,
  EmotionalStability: 0.6,
  Openness: 0.9,
  Conscientiousness: 0.3,
  Agreeableness: 0.5,
  RiskTolerance: -0.2,
  Empathy: 0.8,
  SocialIntelligence: 0.4,
  Creativity: 0.9,
  Logic: 0.5,
  Ambition: 0.6,
  Adaptability: 0.2,
  Altruism: 0.7,
};

function buildProfile(humanId: string, agent: string): AgentSurfaceProfile {
  return {
    humanId,
    agent,
    publicVector: toPublicIdentityVector(identity, ['IE', 'TF']),
  };
}

describe('surface connection', () => {
  test('creates public identity vectors with only allowed dimensions', () => {
    const vector = toPublicIdentityVector(identity, ['IE', 'JP']);

    expect(vector.traits).toEqual({ IE: 0.2, JP: 0.4 });
    expect(vector.timestamp).toBeTypeOf('string');
  });

  test('keeps humans on agent interaction surface until synergy is confirmed', () => {
    const connection = createSurfaceConnection({
      profileA: buildProfile('nicolas', 'sirokuma'),
      profileB: buildProfile('shierra', 'kani'),
      synergyScore: 70,
      now: new Date('2026-02-24T00:00:00.000Z'),
    });

    expect(connection.state).toBe('agent_interaction');
    expect(connection.visibleToHumans).toBe('agent_interaction');
  });

  test('promotes to full match when synergy threshold is met', () => {
    const initial = createSurfaceConnection({
      profileA: buildProfile('nicolas', 'sirokuma'),
      profileB: buildProfile('shierra', 'kani'),
      synergyScore: 70,
      now: new Date('2026-02-24T00:00:00.000Z'),
    });

    const promoted = updateSurfaceConnectionState(
      initial,
      82,
      { synergyThreshold: 75 },
      new Date('2026-02-24T00:01:00.000Z')
    );

    expect(promoted.state).toBe('synergy_confirmed');
    expect(promoted.visibleToHumans).toBe('full_match');
    expect(promoted.updatedAt).toBe('2026-02-24T00:01:00.000Z');
  });
});
