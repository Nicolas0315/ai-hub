/**
 * Example usage of Kani API Client
 *
 * This file demonstrates how to use the Kani client for mediation requests.
 * Run with: node -r esbuild-register src/lib/kani/example.ts
 */

import { kaniClient, getMediationData, sampleIdentities } from "./index";

async function exampleBasicUsage() {
  console.log("=== Basic Usage Example ===\n");

  // Use sample identities
  const data = {
    identityA: sampleIdentities.analytical,
    identityB: sampleIdentities.empathetic,
    xParams: {
      dwellTimeSeconds: 45,
      shareVelocity: 2.5,
      reciprocalInteraction: true,
    },
  };

  try {
    const result = await kaniClient.mediate(data);
    console.log("✓ Mediation Result:");
    console.log(`  - Score: ${result.mediationScore}`);
    console.log(`  - Synergy: ${result.synergyScore}`);
    console.log(`  - Recommendations: ${result.recommendations?.length ?? 0}`);
    console.log(`  - Status: ${result.status}\n`);
  } catch (error) {
    console.error("✗ Error:", error);
  }
}

async function exampleWithDataProvider() {
  console.log("=== Data Provider Example ===\n");

  try {
    // Get all data from data provider
    const data = await getMediationData("user-123", "user-456", {
      dwellTime: 60,
      interactions: 5,
      hasInteracted: true,
    });

    const result = await kaniClient.mediate(data);
    console.log("✓ Mediation Result:");
    console.log(`  - Score: ${result.mediationScore}`);
    console.log(`  - Timestamp: ${result.timestamp}\n`);
  } catch (error) {
    console.error("✗ Error:", error);
  }
}

async function exampleHealthCheck() {
  console.log("=== Health Check Example ===\n");

  try {
    const isHealthy = await kaniClient.healthCheck();
    console.log(`API Status: ${isHealthy ? "✓ Healthy" : "✗ Unhealthy"}\n`);
  } catch (error) {
    console.error("✗ Error:", error);
  }
}

// Main execution
if (require.main === module) {
  (async () => {
    await exampleHealthCheck();
    await exampleBasicUsage();
    await exampleWithDataProvider();
  })();
}
