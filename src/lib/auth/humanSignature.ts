import crypto from "crypto";

function hex(input: Buffer) {
  return input.toString("hex");
}

export function signHumanIntent(message: string, secret: string): string {
  return hex(crypto.createHmac("sha256", secret).update(message).digest());
}

export function verifyHumanIntentSignature(message: string, signature: string): boolean {
  const secret = process.env.HUMAN_LAYER_SIGNING_KEY;
  if (!secret) return false;

  const expected = signHumanIntent(message, secret);
  const a = Buffer.from(expected, "hex");
  const b = Buffer.from(signature, "hex");
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}
