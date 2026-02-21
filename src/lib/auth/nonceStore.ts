const seenNonces = new Map<string, number>();
const TTL_MS = 1000 * 60 * 15; // 15 minutes

function gc() {
  const now = Date.now();
  for (const [nonce, ts] of seenNonces.entries()) {
    if (now - ts > TTL_MS) seenNonces.delete(nonce);
  }
}

export function consumeNonce(nonce: string): boolean {
  gc();
  if (seenNonces.has(nonce)) return false;
  seenNonces.set(nonce, Date.now());
  return true;
}

export function resetNonceStore() {
  seenNonces.clear();
}
