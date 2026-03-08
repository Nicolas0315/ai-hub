export type IntakeStage = "intake" | "kq" | "ks" | "kl" | "inf-bridge" | "inf-coding" | "reply";

export type IntakeIntent = "chat" | "execute" | "analyze" | "route" | "reject" | "hold";

export interface IntakeEnvelope {
  surface: string;
  channelId?: string;
  guildId?: string;
  messageId?: string;
  replyToId?: string;
  authorId?: string;
  content: string;
  attachments?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
}

export interface IntakeRoutingResult {
  ok: boolean;
  status: number;
  mode: "short-circuit" | "full-pipeline";
  intent: IntakeIntent;
  route: IntakeStage[];
  nextStage: IntakeStage;
  bypassedStages: IntakeStage[];
  envelope: IntakeEnvelope;
  packets: {
    intake: Record<string, unknown>;
    kq?: Record<string, unknown>;
    ks?: Record<string, unknown>;
    kl?: Record<string, unknown>;
    infBridge?: Record<string, unknown>;
    infCoding?: Record<string, unknown>;
  };
  reply?: {
    message: string;
    replyToId?: string;
  };
  contract: {
    targetPipeline: IntakeStage[];
    activePipeline: IntakeStage[];
  };
}

const EXECUTE_RE = /\b(run|execute|implement|fix|build|create|patch|実装|実行|修正)\b/i;
const ANALYZE_RE = /\b(analyze|review|inspect|explain|解析|分析|確認|読んで|調べて)\b/i;
const ROUTE_RE = /\b(route|forward|handoff|delegate|ルート|振り分け|転送|委譲)\b/i;
const REJECT_RE = /(ignore|bypass|disable).{0,24}(guard|safety|rule|approval)|(安全|ルール|承認).{0,12}(無視|回避|解除)/i;

export class IntakeRouter {
  private readonly mode: "short-circuit" | "full-pipeline";

  constructor(mode: "short-circuit" | "full-pipeline" = "short-circuit") {
    this.mode = mode;
  }

  public routeDiscordMessage(envelope: IntakeEnvelope): IntakeRoutingResult {
    const normalized = this.normalizeEnvelope(envelope);
    const intent = this.classifyIntent(normalized.content);

    const targetPipeline: IntakeStage[] = ["intake", "kq", "ks", "kl", "inf-bridge", "inf-coding", "reply"];

    if (intent === "reject") {
      return {
        ok: false,
        status: 400,
        mode: this.mode,
        intent,
        route: ["intake", "reply"],
        nextStage: "reply",
        bypassedStages: ["kq", "ks", "kl", "inf-bridge", "inf-coding"],
        envelope: normalized,
        packets: {
          intake: this.buildIntakePacket(normalized, intent),
        },
        reply: {
          message: "安全側で reject した。",
          replyToId: normalized.messageId,
        },
        contract: {
          targetPipeline,
          activePipeline: ["intake", "reply"],
        },
      };
    }

    const intake = this.buildIntakePacket(normalized, intent);
    const kq = this.buildKQPacket(intake);
    const ks = this.buildKSPacket(kq);
    const kl = this.buildKLPacket(ks);
    const infBridge = this.buildInfBridgePacket(kl);
    const infCoding = this.buildInfCodingPacket(infBridge);

    const isShortCircuit = this.mode === "short-circuit";
    const route: IntakeStage[] = isShortCircuit
      ? ["intake", "inf-coding", "reply"]
      : targetPipeline;

    return {
      ok: true,
      status: 200,
      mode: this.mode,
      intent,
      route,
      nextStage: isShortCircuit ? "inf-coding" : "kq",
      bypassedStages: isShortCircuit ? ["kq", "ks", "kl", "inf-bridge"] : [],
      envelope: normalized,
      packets: {
        intake,
        kq,
        ks,
        kl,
        infBridge,
        infCoding,
      },
      reply: {
        message: `[${intent}] routed via ${route.join(" -> ")}`,
        replyToId: normalized.messageId,
      },
      contract: {
        targetPipeline,
        activePipeline: route,
      },
    };
  }

  private normalizeEnvelope(envelope: IntakeEnvelope): IntakeEnvelope {
    return {
      ...envelope,
      surface: envelope.surface || "discord",
      content: (envelope.content || "").replace(/<@!?\d+>/g, " ").replace(/\s+/g, " ").trim(),
      attachments: envelope.attachments || [],
      metadata: envelope.metadata || {},
    };
  }

  private classifyIntent(content: string): IntakeIntent {
    if (!content.trim()) return "reject";
    if (REJECT_RE.test(content)) return "reject";
    if (ROUTE_RE.test(content)) return "route";
    if (EXECUTE_RE.test(content)) return "execute";
    if (ANALYZE_RE.test(content)) return "analyze";
    if (content.trim().length <= 2) return "hold";
    return "chat";
  }

  private buildIntakePacket(envelope: IntakeEnvelope, intent: IntakeIntent): Record<string, unknown> {
    return {
      stage: "intake",
      sourceSurface: envelope.surface,
      intent,
      content: envelope.content,
      context: {
        channelId: envelope.channelId,
        guildId: envelope.guildId,
        messageId: envelope.messageId,
        replyToId: envelope.replyToId,
        authorId: envelope.authorId,
      },
      attachments: envelope.attachments,
      constraints: {
        mustEnterViaInfCoding: true,
        directDownstreamForbidden: true,
        ephemeral: true,
      },
    };
  }

  private buildKQPacket(intake: Record<string, unknown>): Record<string, unknown> {
    return {
      stage: "kq",
      upstream: "intake",
      normalizedInput: intake.content,
      boundary: {
        routePath: "intake -> kq -> ks -> kl -> inf-bridge -> inf-coding",
        failClosed: true,
      },
    };
  }

  private buildKSPacket(kq: Record<string, unknown>): Record<string, unknown> {
    return {
      stage: "ks",
      upstream: "kq",
      semanticIntent: kq.normalizedInput,
      policy: {
        classificationOwner: "ks",
        executionBias: "safe",
      },
    };
  }

  private buildKLPacket(ks: Record<string, unknown>): Record<string, unknown> {
    return {
      stage: "kl",
      upstream: "ks",
      deliberationInput: ks.semanticIntent,
      policy: {
        routeToInfBridge: true,
        preserveReplyContext: true,
      },
    };
  }

  private buildInfBridgePacket(kl: Record<string, unknown>): Record<string, unknown> {
    return {
      stage: "inf-bridge",
      upstream: "kl",
      inputText: kl.deliberationInput,
      normalized: true,
    };
  }

  private buildInfCodingPacket(infBridge: Record<string, unknown>): Record<string, unknown> {
    return {
      stage: "inf-coding",
      upstream: "inf-bridge",
      inputText: infBridge.inputText,
      mustEnterViaInfCoding: true,
      directDownstreamForbidden: true,
      ephemeral: true,
    };
  }
}
