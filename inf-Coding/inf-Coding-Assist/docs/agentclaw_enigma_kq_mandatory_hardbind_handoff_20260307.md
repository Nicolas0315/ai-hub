# AgentClaw[Enigma] KQ Mandatory Hard-Bind (handoff for Nicolas)

Updated: 2026-03-07 JST  
Scope: **AgentClaw ingress + inf-Coding execution path** fail-close enforcement

---

## Goal
Guarantee that **all conversation paths** and **all execution paths** traverse KQ constraints.

Hard requirements:
1. Inbound chat message MUST generate/attach `KQ_INPUT_PACKET_JSON`.
2. If packet missing/invalid -> fail-close (no assistant response delivery).
3. Any command execution path without packet -> fail-close (`rc=74`).
4. Route telemetry must record ingress->KQ->Bridge->Model traversal flags.

---

## Current state (already done in Katala/inf-Coding)
- `inf-Coding/inf-Coding-Assist/ksi1-router.py`
  - `KQ_MANDATORY_GATE` support
  - block on input-layer violations
  - exports `KQ_INPUT_PACKET_JSON`
- `inf-Coding/katala-exec.sh`
  - fail-close if missing/invalid `KQ_INPUT_PACKET_JSON`
- route audit
  - `inf-Coding/inf-Coding-Assist/kq_route_audit_20260307.py`

Remaining gap:
- AgentClaw inbound chat ingress is not yet universally hard-bound.

---

## Nicolas patch plan (AgentClaw side)

### A) Inbound gate (message_received path)
Target area (OpenClaw dist/source equivalent): inbound dispatch around `message_received` handling.

Pseudo:
```ts
const packet = buildKqInputPacket(inboundText, meta)
if (!packet || !isValidJson(packet)) {
  log.warn("blocked: missing/invalid KQ packet at chat ingress")
  return BLOCK_NO_REPLY
}
ctx.kqInputPacketJson = JSON.stringify(packet)
ctx.kqMandatoryGateActive = true
```

### B) Response pre-delivery gate
Before sending assistant reply externally:
```ts
if (kqMandatoryGateActive && !ctx.kqInputPacketJson) {
  log.error("blocked: outbound reply without KQ packet")
  return BLOCK_NO_REPLY
}
```

### C) Tool/command bridge propagation
Any shell/tool launch from chat path must receive:
- `KQ_INPUT_PACKET_JSON`
- `KQ_MANDATORY_GATE_ACTIVE=1`

### D) Audit fields (required)
Persist in telemetry row:
- `ingress_kq_packet_created: true|false`
- `ingress_blocked_reason`
- `kq_packet_propagated_to_exec: true|false`
- `outbound_blocked_reason`

---

## Acceptance tests (must pass)
1. Normal inbound text -> packet created -> reply allowed.
2. Simulated missing packet at ingress -> blocked, no reply.
3. Simulated packet stripped before tool exec -> blocked rc74.
4. Simulated packet stripped before outbound send -> blocked.
5. Audit report shows `no1_chat_ingress_forced=true` and `no3_router_external_fail_close=true`.

---

## Notes
- Do **not** hot-edit `openclaw/dist/*.js` in production as primary method.
- Preferred: patch source layer, rebuild, deploy.
- Keep fail-close default ON (`KQ_MANDATORY_GATE=1`).
