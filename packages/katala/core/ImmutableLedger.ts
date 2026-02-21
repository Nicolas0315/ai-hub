/**
 * ImmutableLedger — Hash-chain based immutable event ledger.
 * In-memory implementation; persistence is a future task.
 */

export interface LedgerEntry {
  id: string;
  timestamp: string;
  eventType: string;
  payload: Record<string, unknown>;
  previousHash: string;
  hash: string;
}

export class ImmutableLedger {
  private chain: LedgerEntry[] = [];

  /**
   * Compute SHA-256 hash of the given data string.
   */
  private async computeHash(data: string): Promise<string> {
    const encoded = new TextEncoder().encode(data);
    const buffer = await crypto.subtle.digest("SHA-256", encoded);
    return Array.from(new Uint8Array(buffer))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  /**
   * Build the hash input for a ledger entry (excluding the hash field itself).
   */
  private hashInput(entry: Omit<LedgerEntry, "hash">): string {
    return JSON.stringify({
      id: entry.id,
      timestamp: entry.timestamp,
      eventType: entry.eventType,
      payload: entry.payload,
      previousHash: entry.previousHash,
    });
  }

  /**
   * Append a new entry to the ledger.
   */
  async append(eventType: string, payload: Record<string, unknown>): Promise<LedgerEntry> {
    const previousHash = this.chain.length > 0 ? this.chain[this.chain.length - 1].hash : "0";

    const partial: Omit<LedgerEntry, "hash"> = {
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      eventType,
      payload,
      previousHash,
    };

    const hash = await this.computeHash(this.hashInput(partial));
    const entry: LedgerEntry = { ...partial, hash };
    this.chain.push(entry);
    return entry;
  }

  /**
   * Verify the integrity of the entire chain.
   * Returns true if all hashes are valid and linked correctly.
   */
  async verify(): Promise<boolean> {
    for (let i = 0; i < this.chain.length; i++) {
      const entry = this.chain[i];

      // Check previousHash linkage
      const expectedPrevious = i === 0 ? "0" : this.chain[i - 1].hash;
      if (entry.previousHash !== expectedPrevious) {
        return false;
      }

      // Check hash integrity
      const { hash, ...rest } = entry;
      const computed = await this.computeHash(this.hashInput(rest));
      if (computed !== hash) {
        return false;
      }
    }
    return true;
  }

  /**
   * Get ledger history, most recent first.
   */
  getHistory(limit?: number): LedgerEntry[] {
    const entries = [...this.chain].reverse();
    return limit !== undefined ? entries.slice(0, limit) : entries;
  }
}
