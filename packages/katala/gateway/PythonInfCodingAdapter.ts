import { spawn } from "child_process";
import { IntakeEnvelope, IntakeRoutingResult } from "./IntakeRouter";

export interface PythonAdapterResult {
  ok: boolean;
  status: number;
  payload: Record<string, unknown>;
  stderr?: string;
}

export class PythonInfCodingAdapter {
  private readonly command: string[];

  constructor(command?: string[]) {
    this.command = command || [
      process.env.KATALA_INTAKE_PYTHON || "python3",
      "-m",
      "katala_samurai.visz_inf_coding_pipeline_entry",
    ];
  }

  public async handoffDiscordEnvelope(envelope: IntakeEnvelope, routed?: IntakeRoutingResult): Promise<PythonAdapterResult> {
    const [bin, ...args] = this.command;
    return await new Promise((resolve) => {
      const child = spawn(bin, args, {
        cwd: process.cwd(),
        env: {
          ...process.env,
          PYTHONPATH: [process.env.PYTHONPATH, "src"].filter(Boolean).join(":"),
        },
        stdio: ["pipe", "pipe", "pipe"],
      });

      let stdout = "";
      let stderr = "";
      child.stdout.on("data", (chunk) => {
        stdout += String(chunk);
      });
      child.stderr.on("data", (chunk) => {
        stderr += String(chunk);
      });
      child.on("error", (error) => {
        resolve({
          ok: false,
          status: 500,
          payload: {
            ok: false,
            error: { code: "SPAWN_FAILED", message: error.message },
          },
          stderr: error.message,
        });
      });
      child.on("close", (code) => {
        try {
          const payload = JSON.parse(stdout || "{}");
          resolve({
            ok: Boolean(payload.ok),
            status: code === 0 ? 200 : 400,
            payload,
            stderr: stderr || undefined,
          });
        } catch {
          resolve({
            ok: false,
            status: 500,
            payload: {
              ok: false,
              error: { code: "BAD_JSON", message: "python adapter returned non-json" },
              raw: stdout,
            },
            stderr: stderr || undefined,
          });
        }
      });

      child.stdin.write(JSON.stringify(this.toPythonEvent(envelope, routed)));
      child.stdin.end();
    });
  }

  private toPythonEvent(envelope: IntakeEnvelope, routed?: IntakeRoutingResult): Record<string, unknown> {
    return {
      id: envelope.messageId,
      channel_id: envelope.channelId,
      guild_id: envelope.guildId,
      content: envelope.content,
      attachments: envelope.attachments || [],
      reply_to_id: envelope.replyToId,
      timestamp: envelope.metadata?.timestamp,
      author: {
        id: envelope.authorId,
        username: envelope.metadata?.username,
        display_name: envelope.metadata?.displayName,
        bot: Boolean(envelope.metadata?.bot),
      },
      intake_route: routed ? {
        mode: routed.mode,
        route: routed.route,
        bypassed_stages: routed.bypassedStages,
        contract: routed.contract,
        intent: routed.intent,
      } : undefined,
    };
  }
}
