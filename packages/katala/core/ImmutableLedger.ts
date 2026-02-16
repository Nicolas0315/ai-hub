import * as crypto from 'crypto';
import { Fact } from './types';

export interface LedgerEntry {
  index: number;
  timestamp: string;
  fact: Fact;
  previousHash: string;
  hash: string;
  signature?: string;
}

export class ImmutableLedger {
  private chain: LedgerEntry[] = [];

  constructor() {
    // Genesis Block (最初のブロック)
    this.createGenesisBlock();
  }

  private createGenesisBlock() {
    const genesisFact: Fact = { category: 'system', value: 'Katala Genesis', confidence: 1.0, evidence: 'system launch' };
    const entry: LedgerEntry = {
      index: 0,
      timestamp: new Date().toISOString(),
      fact: genesisFact,
      previousHash: '0',
      hash: this.calculateHash(0, '0', JSON.stringify(genesisFact)),
    };
    this.chain.push(entry);
  }

  private calculateHash(index: number, previousHash: string, data: string): string {
    return crypto
      .createHash('sha256')
      .update(index + previousHash + data)
      .digest('hex');
  }

  /**
   * 事実を台帳に追記(Append)する。
   * 前のハッシュと連結することで鎖(Chain)を作る。
   */
  async addEntry(fact: Fact): Promise<LedgerEntry> {
    const previousBlock = this.chain[this.chain.length - 1];
    const newIndex = previousBlock.index + 1;
    const timestamp = new Date().toISOString();
    const data = JSON.stringify(fact);
    const hash = this.calculateHash(newIndex, previousBlock.hash, data);

    const newEntry: LedgerEntry = {
      index: newIndex,
      timestamp,
      fact,
      previousHash: previousBlock.hash,
      hash,
    };

    this.chain.push(newEntry);
    return newEntry;
  }

  /**
   * 台帳が改ざんされていないか検証する
   */
  verifyChain(): boolean {
    for (let i = 1; i < this.chain.length; i++) {
      const current = this.chain[i];
      const previous = this.chain[i - 1];

      // ハッシュが現在のデータと一致するか
      if (current.hash !== this.calculateHash(current.index, current.previousHash, JSON.stringify(current.fact))) {
        return false;
      }
      // 前のハッシュと繋がっているか
      if (current.previousHash !== previous.hash) {
        return false;
      }
    }
    return true;
  }

  getChain(): LedgerEntry[] {
    return this.chain;
  }
}
