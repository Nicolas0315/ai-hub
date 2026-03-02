import { IdentityVector } from "./IdentityVector";
import { ProfilingEngine, ChatMessage } from "./ProfilingEngine";

export interface BatchItem {
  id: string;
  currentVector: IdentityVector;
  history: ChatMessage[];
}

export interface BatchResult {
  id: string;
  status: "success" | "error";
  vector?: IdentityVector;
  error?: string;
  retries: number;
}

export interface BatchProgress {
  processed: number;
  total: number;
  errors: number;
}

export interface BatchOptions {
  concurrency?: number;
  maxRetries?: number;
  onProgress?: (progress: BatchProgress) => void;
}

export class BatchProcessor {
  private engine: ProfilingEngine;

  constructor(engine: ProfilingEngine) {
    this.engine = engine;
  }

  async process(items: BatchItem[], options: BatchOptions = {}): Promise<BatchResult[]> {
    const { concurrency = 5, maxRetries = 3, onProgress } = options;
    const results: BatchResult[] = [];
    let processed = 0;
    let errors = 0;

    const queue = [...items];
    let idx = 0;

    const runOne = async (item: BatchItem): Promise<void> => {
      let lastError: string | undefined;
      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
          const vector = await this.engine.updateProfile(item.currentVector, item.history);
          results.push({ id: item.id, status: "success", vector, retries: attempt });
          processed++;
          onProgress?.({ processed, total: items.length, errors });
          return;
        } catch (e: unknown) {
          lastError = e.message ?? String(e);
          if (attempt < maxRetries) continue;
        }
      }
      errors++;
      processed++;
      results.push({ id: item.id, status: "error", error: lastError, retries: maxRetries });
      onProgress?.({ processed, total: items.length, errors });
    };

    const worker = async () => {
      while (idx < queue.length) {
        const item = queue[idx++];
        await runOne(item);
      }
    };

    const workers = Array.from({ length: Math.min(concurrency, queue.length) }, () => worker());
    await Promise.allSettled(workers);

    return results;
  }

  toJSON(results: BatchResult[]): string {
    return JSON.stringify(results, null, 2);
  }
}
