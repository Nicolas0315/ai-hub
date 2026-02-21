import { describe, it, expect } from "vitest";
import { createDefaultVector } from "../../../../packages/katala/core/IdentityVector";

// Helper: build a NextRequest-like object
function makeRequest(body: unknown, url = "http://localhost:3000") {
  return new Request(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function makeGetRequest(url: string) {
  return new Request(url, { method: "GET" });
}

// We import the route handlers directly and call them
// Next.js App Router handlers accept a standard Request and return Response

describe("API: /api/profiling", () => {
  it("POST returns updated vector", async () => {
    const { POST } = await import("../profiling/route");
    const vector = createDefaultVector();
    const req = makeRequest({
      currentVector: vector,
      history: [{ role: "user", content: "Hello", timestamp: new Date().toISOString() }],
    });
    const res = await POST(req as any);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.status).toBe("success");
    expect(data.vector).toBeDefined();
  });

  it("POST rejects invalid body", async () => {
    const { POST } = await import("../profiling/route");
    const req = makeRequest({ bad: true });
    const res = await POST(req as any);
    expect(res.status).toBe(400);
  });

  it("POST tune mode works", async () => {
    const { POST } = await import("../profiling/route");
    const vector = createDefaultVector();
    const req = makeRequest(
      { currentVector: vector, instruction: "more outgoing" },
      "http://localhost:3000/api/profiling?mode=tune",
    );
    const res = await POST(req as any);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.vector.personality.extraversion).toBeGreaterThan(0.5);
  });
});

describe("API: /api/matchmaking", () => {
  it("POST returns matches", async () => {
    const { POST } = await import("../matchmaking/route");
    const source = createDefaultVector();
    const candidate = { ...createDefaultVector(), values: ["innovation"] };
    const req = makeRequest({
      source,
      candidates: [candidate],
      threshold: 0,
    });
    const res = await POST(req as any);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.status).toBe("success");
    expect(Array.isArray(data.matches)).toBe(true);
  });

  it("POST rejects empty candidates", async () => {
    const { POST } = await import("../matchmaking/route");
    const req = makeRequest({ source: createDefaultVector(), candidates: [] });
    const res = await POST(req as any);
    expect(res.status).toBe(400);
  });
});

describe("API: /api/import", () => {
  it("POST imports valid CSV", async () => {
    const { POST } = await import("../import/route");
    const csv = [
      "extraversion,intuition,thinking,judging,values,professionalFocus,battery,preferredTone,confidenceScore,lastUpdated",
      `0.8,0.6,0.7,0.4,innovation|design,TypeScript|React,75,casual,0.85,${new Date().toISOString()}`,
    ].join("\n");
    const req = makeRequest({ csv });
    const res = await POST(req as any);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.imported).toBe(1);
    expect(data.vectors).toHaveLength(1);
  });

  it("POST rejects empty csv", async () => {
    const { POST } = await import("../import/route");
    const req = makeRequest({ csv: "" });
    const res = await POST(req as any);
    expect(res.status).toBe(400);
  });
});

describe("API: /api/batch", () => {
  it("POST starts a batch job and returns jobId", async () => {
    const { POST } = await import("../batch/route");
    const vector = createDefaultVector();
    const req = makeRequest({
      items: [
        {
          id: "user-1",
          currentVector: vector,
          history: [{ role: "user", content: "Hi", timestamp: new Date().toISOString() }],
        },
      ],
    });
    const res = await POST(req as any);
    expect(res.status).toBe(202);
    const data = await res.json();
    expect(data.jobId).toBeDefined();
    expect(data.status).toBe("accepted");
  });

  it("GET returns 400 without jobId", async () => {
    const { GET } = await import("../batch/route");
    const req = makeGetRequest("http://localhost:3000/api/batch");
    const res = await GET(req as any);
    expect(res.status).toBe(400);
  });

  it("GET returns 404 for unknown jobId", async () => {
    const { GET } = await import("../batch/route");
    const req = makeGetRequest("http://localhost:3000/api/batch?jobId=nonexistent");
    const res = await GET(req as any);
    expect(res.status).toBe(404);
  });
});

describe("API: /api/ledger", () => {
  it("POST appends entry then GET retrieves it", async () => {
    const { POST, GET } = await import("../ledger/route");

    const postReq = makeRequest({ eventType: "test.event", payload: { foo: "bar" } });
    const postRes = await POST(postReq as any);
    expect(postRes.status).toBe(201);
    const postData = await postRes.json();
    expect(postData.entry.eventType).toBe("test.event");

    const getReq = makeGetRequest("http://localhost:3000/api/ledger?limit=10");
    const getRes = await GET(getReq as any);
    expect(getRes.status).toBe(200);
    const getData = await getRes.json();
    expect(getData.entries.length).toBeGreaterThan(0);
    expect(getData.chainValid).toBe(true);
  });

  it("POST rejects invalid payload", async () => {
    const { POST } = await import("../ledger/route");
    const req = makeRequest({ eventType: "", payload: {} });
    const res = await POST(req as any);
    expect(res.status).toBe(400);
  });
});

describe("API: /api/intent/normalize", () => {
  it("POST normalizes intent and infers priority", async () => {
    const { POST } = await import("../intent/normalize/route");
    const req = makeRequest({ text: "至急でこのタスクを終わらせたい", counterparty: "agent-b" });
    const res = await POST(req as any);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.status).toBe("success");
    expect(data.normalized.priority).toBe("high");
  });

  it("POST rejects invalid body", async () => {
    const { POST } = await import("../intent/normalize/route");
    const req = makeRequest({ text: "" });
    const res = await POST(req as any);
    expect(res.status).toBe(400);
  });
});

describe("API: /api/mediation", () => {
  it("POST /propose creates proposal", async () => {
    const { POST } = await import("../mediation/propose/route");
    const req = makeRequest({ fromAgentId: "a1", toAgentId: "a2", intent: "今すぐやれ" });
    const res = await POST(req as any);
    expect(res.status).toBe(201);
    const data = await res.json();
    expect(data.status).toBe("success");
    expect(data.proposal.proposalId).toBeDefined();
  });

  it("POST /resolve resolves proposal", async () => {
    process.env.HUMAN_LAYER_SIGNING_KEY = "test-secret";
    const { signHumanIntent } = await import("@/lib/auth/humanSignature");
    const { POST } = await import("../mediation/resolve/route");

    const payload = {
      proposalId: "prop_123",
      accepted: true,
      actorId: "human_1",
      nonce: "n1",
    };
    const signingMessage = `${payload.actorId}:${payload.proposalId}:${payload.accepted}:${payload.nonce}`;
    const signature = signHumanIntent(signingMessage, "test-secret");

    const req = makeRequest({ ...payload, signature });
    const res = await POST(req as any);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.resolution.status).toBe("agreed");
  });

  it("POST /resolve rejects invalid signature", async () => {
    process.env.HUMAN_LAYER_SIGNING_KEY = "test-secret";
    const { POST } = await import("../mediation/resolve/route");
    const req = makeRequest({
      proposalId: "prop_123",
      accepted: true,
      actorId: "human_1",
      nonce: "n1",
      signature: "deadbeef",
    });
    const res = await POST(req as any);
    expect(res.status).toBe(401);
  });
});
