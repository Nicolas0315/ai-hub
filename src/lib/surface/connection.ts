import { IdentityDimensions } from '../synergy/engine';

export type AgentHandle = 'sirokuma' | 'kani' | string;

export interface PublicIdentityVector {
  traits: Partial<IdentityDimensions>;
  timestamp: string;
}

export interface AgentSurfaceProfile {
  humanId: string;
  agent: AgentHandle;
  publicVector: PublicIdentityVector;
}

export type SurfaceConnectionState = 'agent_interaction' | 'synergy_confirmed';

export interface SurfaceConnection {
  id: string;
  participants: [AgentSurfaceProfile, AgentSurfaceProfile];
  state: SurfaceConnectionState;
  synergyScore: number;
  visibleToHumans: 'agent_interaction' | 'full_match';
  createdAt: string;
  updatedAt: string;
}

export interface SurfaceConnectionPolicy {
  synergyThreshold: number;
}

export interface SurfaceConnectionInput {
  profileA: AgentSurfaceProfile;
  profileB: AgentSurfaceProfile;
  synergyScore: number;
  now?: Date;
}

const DEFAULT_POLICY: SurfaceConnectionPolicy = {
  synergyThreshold: 75,
};

const toIso = (value: Date) => value.toISOString();

export function toPublicIdentityVector(
  identity: IdentityDimensions,
  allowedDimensions: (keyof IdentityDimensions)[],
  timestamp: Date = new Date()
): PublicIdentityVector {
  const traits = allowedDimensions.reduce((acc, key) => {
    acc[key] = identity[key];
    return acc;
  }, {} as Partial<IdentityDimensions>);

  return {
    traits,
    timestamp: toIso(timestamp),
  };
}

export function createSurfaceConnection(
  input: SurfaceConnectionInput,
  policy: SurfaceConnectionPolicy = DEFAULT_POLICY
): SurfaceConnection {
  const now = input.now ?? new Date();
  const state: SurfaceConnectionState =
    input.synergyScore >= policy.synergyThreshold ? 'synergy_confirmed' : 'agent_interaction';

  return {
    id: `${input.profileA.agent}-${input.profileA.humanId}:${input.profileB.agent}-${input.profileB.humanId}`,
    participants: [input.profileA, input.profileB],
    state,
    synergyScore: input.synergyScore,
    visibleToHumans: state === 'synergy_confirmed' ? 'full_match' : 'agent_interaction',
    createdAt: toIso(now),
    updatedAt: toIso(now),
  };
}

export function updateSurfaceConnectionState(
  connection: SurfaceConnection,
  synergyScore: number,
  policy: SurfaceConnectionPolicy = DEFAULT_POLICY,
  now: Date = new Date()
): SurfaceConnection {
  const nextState: SurfaceConnectionState =
    synergyScore >= policy.synergyThreshold ? 'synergy_confirmed' : 'agent_interaction';

  return {
    ...connection,
    state: nextState,
    synergyScore,
    visibleToHumans: nextState === 'synergy_confirmed' ? 'full_match' : 'agent_interaction',
    updatedAt: toIso(now),
  };
}
