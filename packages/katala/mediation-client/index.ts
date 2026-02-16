import { KatalaMediationClient } from './client';

export * from './client';

export const createDefaultClient = (target: string, token?: string) => {
    return new KatalaMediationClient({
        target,
        token,
        protocol: 'http'
    });
};
