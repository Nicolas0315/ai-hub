# discord-kq-bot

1-file Discord bot template with KQ mandatory gate.

## Overview
This file is a minimal template for a Discord bot that:
- builds a KQ packet at ingress,
- fail-closes on invalid or missing packet data,
- propagates packet lineage downstream,
- re-verifies right before outbound,
- writes an audit log.

## Requirements
- Node.js 18+
- npm
- Discord Bot Token
- KQ shared secret

## Setup
1. Save the code block below as `discord-kq-bot.ts`
2. Install dependencies:
   - `npm init -y`
   - `npm i discord.js`
   - `npm i -D typescript tsx`
3. Run:
   - `DISCORD_TOKEN=your_token_here KQ_SHARED_SECRET=your_secret_here npx tsx discord-kq-bot.ts`

## Behavior
- `/ping` -> `pong`
- `/diag` -> diagnostic info
- other messages -> simple echo response

## Code

```ts
import crypto from "node:crypto";
import {
  Client,
  GatewayIntentBits,
  Partials,
} from "discord.js";

type Platform = "discord";
type IngressDecision = "accepted" | "rejected";

interface KQPacket {
  schemaVersion: "1";
  packetId: string;
  traceId: string;
  platform: Platform;
  chatId: string;
  userId: string;
  messageId: string;
  text: string;
  timestamp: string;
  signature: string;
}

interface AuditTrail {
  packetId: string;
  traceId: string;
  ingressDecision: IngressDecision;
  kqTraversalVerified: boolean;
  responseReleased: boolean;
  reason?: string;
}

interface ProcessContext {
  packet: KQPacket;
  ingressDecision: IngressDecision;
  kqTraversalVerified: boolean;
  responseReleased: boolean;
  downstreamEnv: Record<string, string>;
  auditTrail: AuditTrail;
}

const DISCORD_TOKEN = process.env.DISCORD_TOKEN;
const KQ_SHARED_SECRET = process.env.KQ_SHARED_SECRET || "dev-secret";
const MAX_TEXT_LENGTH = 4000;

if (!DISCORD_TOKEN) {
  throw new Error("Missing DISCORD_TOKEN");
}

class KQGateError extends Error {
  code: number;
  reason: string;

  constructor(reason: string, code = 74) {
    super(reason);
    this.name = "KQGateError";
    this.reason = reason;
    this.code = code;
  }
}

function stablePacketPayload(packet: Omit<KQPacket, "signature">): string {
  return JSON.stringify({
    schemaVersion: packet.schemaVersion,
    packetId: packet.packetId,
    traceId: packet.traceId,
    platform: packet.platform,
    chatId: packet.chatId,
    userId: packet.userId,
    messageId: packet.messageId,
    text: packet.text,
    timestamp: packet.timestamp,
  });
}

function signPayload(payload: string): string {
  return crypto
    .createHmac("sha256", KQ_SHARED_SECRET)
    .update(payload)
    .digest("hex");
}

function safeEqualString(a: string, b: string): boolean {
  const aBuf = Buffer.from(a, "utf8");
  const bBuf = Buffer.from(b, "utf8");
  if (aBuf.length !== bBuf.length) return false;
  return crypto.timingSafeEqual(aBuf, bBuf);
}

function writeAuditLog(audit: AuditTrail) {
  const record = {
    event: "message.processed",
    packetId: audit.packetId,
    traceId: audit.traceId,
    ingressDecision: audit.ingressDecision,
    kqTraversalVerified: audit.kqTraversalVerified,
    responseReleased: audit.responseReleased,
    reason: audit.reason ?? null,
    ts: new Date().toISOString(),
  };

  console.log(JSON.stringify(record));
}

function buildKQPacketFromMessage(input: {
  channelId: string;
  authorId: string;
  messageId: string;
  content: string;
  createdTimestamp: number;
}): KQPacket {
  const timestamp = new Date(input.createdTimestamp).toISOString();

  const base: Omit<KQPacket, "signature"> = {
    schemaVersion: "1",
    packetId: crypto.randomUUID(),
    traceId: crypto.randomUUID(),
    platform: "discord",
    chatId: input.channelId,
    userId: input.authorId,
    messageId: input.messageId,
    text: input.content.slice(0, MAX_TEXT_LENGTH),
    timestamp,
  };

  return {
    ...base,
    signature: signPayload(stablePacketPayload(base)),
  };
}

function verifyKQPacket(packet: KQPacket): boolean {
  const { signature, ...rest } = packet;
  const expected = signPayload(stablePacketPayload(rest));
  return safeEqualString(signature, expected);
}

function enforceIngress(packet: KQPacket): ProcessContext {
  if (!packet) {
    throw new KQGateError("missing_packet");
  }

  if (!packet.packetId) {
    throw new KQGateError("missing_packet_id");
  }

  if (!packet.traceId) {
    throw new KQGateError("missing_trace_id");
  }

  if (!packet.text || !packet.text.trim()) {
    throw new KQGateError("missing_text");
  }

  if (!packet.signature) {
    throw new KQGateError("missing_signature");
  }

  if (!verifyKQPacket(packet)) {
    throw new KQGateError("invalid_signature");
  }

  return {
    packet,
    ingressDecision: "accepted",
    kqTraversalVerified: true,
    responseReleased: false,
    downstreamEnv: {
      KQ_MANDATORY_GATE_ACTIVE: "true",
      KQ_INPUT_PACKET_JSON: JSON.stringify(packet),
      KQ_PACKET_ID: packet.packetId,
      KQ_TRACE_ID: packet.traceId,
    },
    auditTrail: {
      packetId: packet.packetId,
      traceId: packet.traceId,
      ingressDecision: "accepted",
      kqTraversalVerified: true,
      responseReleased: false,
    },
  };
}

function enforceOutbound(ctx: ProcessContext): void {
  if (!ctx?.packet?.packetId) {
    throw new KQGateError("missing_packet_at_outbound");
  }

  if (!ctx.kqTraversalVerified) {
    throw new KQGateError("kq_traversal_not_verified");
  }

  if (ctx.downstreamEnv.KQ_MANDATORY_GATE_ACTIVE !== "true") {
    throw new KQGateError("mandatory_gate_flag_missing");
  }

  if (!ctx.downstreamEnv.KQ_INPUT_PACKET_JSON) {
    throw new KQGateError("missing_downstream_packet_json");
  }

  const inheritedPacket = JSON.parse(ctx.downstreamEnv.KQ_INPUT_PACKET_JSON) as KQPacket;
  if (inheritedPacket.packetId !== ctx.packet.packetId) {
    throw new KQGateError("packet_lineage_mismatch");
  }
}

async function runAgent(ctx: ProcessContext): Promise<string> {
  const text = ctx.packet.text.trim();

  if (text === "/ping") {
    return "pong";
  }

  if (text === "/diag") {
    return [
      "KQ self-check:",
      `- packetId: ${ctx.packet.packetId}`,
      `- traceId: ${ctx.packet.traceId}`,
      `- ingressDecision: ${ctx.ingressDecision}`,
      `- kqTraversalVerified: ${ctx.kqTraversalVerified}`,
      `- mandatoryGate: ${ctx.downstreamEnv.KQ_MANDATORY_GATE_ACTIVE}`,
    ].join("\n");
  }

  return `受信したよ: ${text}`;
}

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.DirectMessages,
    GatewayIntentBits.MessageContent,
  ],
  partials: [Partials.Channel],
});

client.once("ready", () => {
  console.log(`Logged in as ${client.user?.tag}`);
});

client.on("messageCreate", async (msg) => {
  if (msg.partial) return;
  if (msg.author.bot) return;
  if (!msg.content?.trim()) return;

  // mention時だけ動かしたいなら下を有効化
  // const isMentioned = client.user ? msg.mentions.has(client.user.id) : false;
  // if (!isMentioned) return;

  try {
    const packet = buildKQPacketFromMessage({
      channelId: msg.channelId,
      authorId: msg.author.id,
      messageId: msg.id,
      content: msg.content,
      createdTimestamp: msg.createdTimestamp,
    });

    const ctx = enforceIngress(packet);
    const responseText = await runAgent(ctx);
    enforceOutbound(ctx);

    await msg.reply({
      content: responseText,
      allowedMentions: { repliedUser: false },
    });

    ctx.responseReleased = true;
    ctx.auditTrail.responseReleased = true;
    writeAuditLog(ctx.auditTrail);
  } catch (err) {
    if (err instanceof KQGateError) {
      console.error(JSON.stringify({
        event: "message.fail_close",
        reason: err.reason,
        code: err.code,
        ts: new Date().toISOString(),
      }));
      return;
    }

    console.error(err);
  }
});

client.login(DISCORD_TOKEN);
```

## Notes
- For production, add replay protection, timestamp drift checks, persistent audit logs, and a route-audit script.
- To restrict replies to mentions only, uncomment the mention guard in `messageCreate`.
- To swap in an LLM, replace the contents of `runAgent()`.
