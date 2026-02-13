/**
 * Kani API Client Module
 *
 * Provides client interface for Katala-Claw bridge mediation API
 * with retry logic, timeout handling, and mock data fallback.
 */

export {
  KaniClient,
  kaniClient,
  mediate,
} from './client';

export type {
  KaniMediationRequest,
  KaniMediationResponse,
  KaniClientConfig,
  KaniAPIError,
} from './types';

export {
  sampleIdentities,
  getDefaultIdentity,
  getIdentityByUserId,
  getCurrentUserIdentity,
  generateXParams,
  getMediationData,
} from './dataProvider';

export {
  mockMediationResponse,
  generateMockResponse,
} from './mockData';
