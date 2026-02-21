import { IdentityDimensions, XAlgorithmParams } from "../synergy/engine";

/**
 * Kani API Request Types
 */
export interface KaniMediationRequest {
  identityA: IdentityDimensions;
  identityB: IdentityDimensions;
  xParams: XAlgorithmParams;
}

/**
 * Kani API Response Types
 */
export interface KaniMediationResponse {
  mediationScore: number;
  synergyScore?: number;
  recommendations?: string[];
  timestamp: string;
  status: "success" | "error";
}

/**
 * Client Configuration
 */
export interface KaniClientConfig {
  baseUrl: string;
  timeout: number; // milliseconds
  maxRetries: number;
  retryDelay: number; // milliseconds
  useMockData?: boolean;
}

/**
 * Error Types
 */
export class KaniAPIError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public originalError?: Error,
  ) {
    super(message);
    this.name = "KaniAPIError";
  }
}
