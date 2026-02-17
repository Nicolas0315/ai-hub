import { describe, it, expect } from 'vitest';
import { MediationService } from '../MediationService';
import { SynergyRequestSchema, SynergyRequest } from '../types';
import { createDefaultVector } from '../IdentityVector';

describe('MediationService', () => {
  const service = new MediationService();

  it('should calculate synergy for a valid identity-vector request', async () => {
    const req: SynergyRequest = {
      user_a: { user_id: 'alice', identity_vector: createDefaultVector() },
      user_b: { user_id: 'bob', identity_vector: createDefaultVector() },
    };
    const res = await service.calculateSynergy(req);
    expect(res.synergy.agent_id_a).toBe('alice');
    expect(res.synergy.agent_id_b).toBe('bob');
    expect(res.synergy.method).toBe('identity-vector-zk');
    expect(typeof res.synergy.score).toBe('number');
  });

  it('should calculate synergy for a legacy interest-based request', async () => {
    const req: SynergyRequest = {
      user_a: {
        user_id: 'alice',
        interests: [{ category: 'tech', weight: 0.8 }, { category: 'art', weight: 0.5 }],
      },
      user_b: {
        user_id: 'bob',
        interests: [{ category: 'tech', weight: 0.6 }, { category: 'music', weight: 0.9 }],
      },
    };
    const res = await service.calculateSynergy(req);
    expect(res.synergy.method).toBe('legacy-interest-dot-product');
    expect(res.synergy.score).toBeGreaterThan(0);
    expect(res.synergy.breakdown.interest_match).toBeDefined();
  });

  it('should handle legacy request with empty interests', async () => {
    const req: SynergyRequest = {
      user_a: { user_id: 'alice', interests: [] },
      user_b: { user_id: 'bob', interests: [] },
    };
    const res = await service.calculateSynergy(req);
    expect(res.synergy.score).toBe(0);
    expect(res.synergy.method).toBe('legacy-interest-dot-product');
  });
});

describe('SynergyRequestSchema validation', () => {
  it('should accept a valid request', () => {
    const input = {
      user_a: { user_id: 'alice', interests: [{ category: 'tech', weight: 1.0 }] },
      user_b: { user_id: 'bob', interests: [{ category: 'tech', weight: 0.5 }] },
    };
    const result = SynergyRequestSchema.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('should reject a request missing user_id', () => {
    const input = {
      user_a: { interests: [{ category: 'tech', weight: 1.0 }] },
      user_b: { user_id: 'bob' },
    };
    const result = SynergyRequestSchema.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('should reject a request with invalid interest shape', () => {
    const input = {
      user_a: { user_id: 'alice', interests: [{ category: '', weight: 1.0 }] },
      user_b: { user_id: 'bob', interests: [] },
    };
    const result = SynergyRequestSchema.safeParse(input);
    expect(result.success).toBe(false);
  });
});
