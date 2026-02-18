// Stub types for gRPC synergy protocol — will be generated from .proto later

export interface UserProfile {
  user_id: string;
  vector?: number[];
  metadata?: Record<string, unknown>;
}

export interface SynergyResult {
  score: number;
  dimensions?: Record<string, number>;
  confidence?: number;
}

export interface SynergyRequest {
  user_a?: UserProfile;
  user_b?: UserProfile;
  vectorA?: number[];
  vectorB?: number[];
  soulConstraints?: Record<string, number>;
}

export interface SynergyResponse {
  synergy?: SynergyResult;
  score?: number;
  dimensions?: Record<string, number>;
  confidence?: number;
}
