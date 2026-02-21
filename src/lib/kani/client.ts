import { generateMockResponse } from "./mockData";
import {
  KaniMediationRequest,
  KaniMediationResponse,
  KaniClientConfig,
  KaniAPIError,
} from "./types";

/**
 * Default client configuration
 */
const DEFAULT_CONFIG: KaniClientConfig = {
  baseUrl: "http://100.77.205.126:3000",
  timeout: 5000, // 5 seconds
  maxRetries: 3,
  retryDelay: 1000, // 1 second
  useMockData: false,
};

/**
 * Kani API Client with retry logic and timeout handling
 */
export class KaniClient {
  private config: KaniClientConfig;

  constructor(config: Partial<KaniClientConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Sleep utility for retry delays
   */
  private async sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Fetch with timeout
   */
  private async fetchWithTimeout(
    url: string,
    options: RequestInit,
    timeout: number,
  ): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof Error && error.name === "AbortError") {
        throw new KaniAPIError("Request timeout", 408, error);
      }
      throw error;
    }
  }

  /**
   * Make a mediation request with retry logic
   */
  async mediate(request: KaniMediationRequest): Promise<KaniMediationResponse> {
    // Use mock data if configured
    if (this.config.useMockData) {
      console.log("[Kani Client] Using mock data");
      await this.sleep(100); // Simulate network delay
      return generateMockResponse();
    }

    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= this.config.maxRetries; attempt++) {
      try {
        console.log(`[Kani Client] Attempt ${attempt}/${this.config.maxRetries}`);

        const response = await this.fetchWithTimeout(
          `${this.config.baseUrl}/api/v1/mediate`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(request),
          },
          this.config.timeout,
        );

        if (!response.ok) {
          throw new KaniAPIError(
            `API returned ${response.status}: ${response.statusText}`,
            response.status,
          );
        }

        const data: KaniMediationResponse = await response.json();

        console.log("[Kani Client] ✓ Request successful");
        return data;
      } catch (error) {
        lastError = error as Error;
        console.error(
          `[Kani Client] ✗ Attempt ${attempt} failed:`,
          error instanceof Error ? error.message : error,
        );

        // If this is not the last attempt, wait before retrying
        if (attempt < this.config.maxRetries) {
          const delay = this.config.retryDelay * attempt; // Exponential backoff
          console.log(`[Kani Client] Retrying in ${delay}ms...`);
          await this.sleep(delay);
        }
      }
    }

    // All retries exhausted - fall back to mock data
    console.warn("[Kani Client] All retries exhausted, falling back to mock data");
    console.warn("[Kani Client] Last error:", lastError?.message);
    return generateMockResponse();
  }

  /**
   * Health check endpoint
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.fetchWithTimeout(
        `${this.config.baseUrl}/health`,
        { method: "GET" },
        2000,
      );
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * Update client configuration
   */
  updateConfig(config: Partial<KaniClientConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * Get current configuration
   */
  getConfig(): KaniClientConfig {
    return { ...this.config };
  }
}

/**
 * Singleton instance for default usage
 */
export const kaniClient = new KaniClient();

/**
 * Convenience function for quick mediation requests
 */
export async function mediate(request: KaniMediationRequest): Promise<KaniMediationResponse> {
  return kaniClient.mediate(request);
}
