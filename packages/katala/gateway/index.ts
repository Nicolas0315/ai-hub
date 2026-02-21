import { KatalaClawGateway } from "./KatalaClawGateway";

// Entry point for the Katala-Claw Gateway
async function main() {
  const port = process.env.KATALA_GATEWAY_PORT ? parseInt(process.env.KATALA_GATEWAY_PORT) : 18789;
  const gateway = new KatalaClawGateway(port);

  console.log(`[Katala] Starting Secure Agent Gateway...`);

  try {
    gateway.start();

    // Handle termination
    process.on("SIGINT", () => {
      gateway.stop();
      process.exit(0);
    });

    process.on("SIGTERM", () => {
      gateway.stop();
      process.exit(0);
    });
  } catch (error) {
    console.error(`[Katala] ✕ Failed to start gateway:`, error);
    process.exit(1);
  }
}

// Run if this script is executed directly
if (require.main === module) {
  main();
}

export * from "./KatalaClawGateway";
