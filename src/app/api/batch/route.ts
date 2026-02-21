import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import {
  BatchProcessor,
  BatchItem,
  BatchProgress,
} from "../../../../packages/katala/core/BatchProcessor";
import { IdentityVectorSchema } from "../../../../packages/katala/core/IdentityVector";
import { ProfilingEngine } from "../../../../packages/katala/core/ProfilingEngine";

const ChatMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  timestamp: z.string(),
});

const BatchItemSchema = z.object({
  id: z.string().min(1),
  currentVector: IdentityVectorSchema,
  history: z.array(ChatMessageSchema).min(1),
});

const BatchRequestSchema = z.object({
  items: z.array(BatchItemSchema).min(1),
  concurrency: z.number().int().positive().optional(),
  maxRetries: z.number().int().min(0).optional(),
});

// In-memory job store (prototype; replace with DB/Redis in production)
const jobs = new Map<string, { status: string; progress: BatchProgress; results?: unknown }>();

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const parsed = BatchRequestSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json(
        { error: "Validation failed", details: parsed.error.issues },
        { status: 400 },
      );
    }

    const jobId = crypto.randomUUID();
    const progress: BatchProgress = { processed: 0, total: parsed.data.items.length, errors: 0 };
    jobs.set(jobId, { status: "running", progress });

    // Fire-and-forget async processing
    const engine = new ProfilingEngine();
    const processor = new BatchProcessor(engine);
    processor
      .process(parsed.data.items as BatchItem[], {
        concurrency: parsed.data.concurrency,
        maxRetries: parsed.data.maxRetries,
        onProgress: (p) => {
          const job = jobs.get(jobId);
          if (job) {
            job.progress = p;
          }
        },
      })
      .then((results) => {
        const job = jobs.get(jobId);
        if (job) {
          job.status = "completed";
          job.results = results;
        }
      })
      .catch((err) => {
        const job = jobs.get(jobId);
        if (job) {
          job.status = "failed";
        }
      });

    return NextResponse.json({ jobId, status: "accepted" }, { status: 202 });
  } catch (error) {
    console.error("[Batch API Error]", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const jobId = searchParams.get("jobId");

  if (!jobId) {
    return NextResponse.json({ error: "Missing jobId parameter" }, { status: 400 });
  }

  const job = jobs.get(jobId);
  if (!job) {
    return NextResponse.json({ error: "Job not found" }, { status: 404 });
  }

  return NextResponse.json({ jobId, ...job });
}
