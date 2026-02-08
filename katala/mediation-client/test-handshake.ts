import { KatalaMediationClient } from './client';

async function main() {
    const target = process.env.KANI_TARGET || '100.77.205.126:18789';
    const token = process.env.KANI_TOKEN;

    console.log(`Testing handshake with Kani at ${target}...`);

    // Testing gRPC first
    const grpcClient = new KatalaMediationClient({
        target: target,
        token: token,
        protocol: 'grpc'
    });

    try {
        console.log('Attempting gRPC handshake...');
        const grpcResult = await grpcClient.handshake('test-client');
        console.log('gRPC Handshake Result:', grpcResult);
    } catch (err: any) {
        console.error('gRPC Handshake failed (expected if server is not gRPC):', err.message);
    }

    // Testing HTTP/REST
    const httpClient = new KatalaMediationClient({
        target: target,
        token: token,
        protocol: 'http'
    });

    try {
        console.log('Attempting HTTP handshake...');
        const httpResult = await httpClient.handshake('test-client');
        console.log('HTTP Handshake Result:', httpResult);
    } catch (err: any) {
        console.error('HTTP Handshake failed:', err.message);
    }
}

main().catch(console.error);
