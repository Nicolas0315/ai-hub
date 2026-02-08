import { KatalaClawGateway } from './KatalaClawGateway';

/**
 * CLI Entry point for the Katala-Claw Gateway.
 * Follows Apple HIG for clean and descriptive logging.
 */
async function main() {
    const port = parseInt(process.env.KATALA_GATEWAY_PORT || '18789', 10);
    const gateway = new KatalaClawGateway(port);

    console.log('Katala-Claw Gateway');
    console.log('───────────────────');
    
    try {
        gateway.start();

        // Handle process signals for graceful shutdown
        process.on('SIGINT', () => {
            console.log('\n[Gateway] Interrupt received...');
            gateway.stop();
            process.exit(0);
        });

        process.on('SIGTERM', () => {
            console.log('\n[Gateway] Termination received...');
            gateway.stop();
            process.exit(0);
        });

    } catch (error) {
        console.error('[Gateway] ✕ Critical failure during startup:');
        console.error(error);
        process.exit(1);
    }
}

main();
