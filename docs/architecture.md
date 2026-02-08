# Katala Architecture

## System Overview
Katala is built on a distributed agent architecture. Each user is represented by a persistent AI agent that handles discovery, mediation, and interaction on their behalf.

## The 'Sirokuma-Kani' Connection
The mediation layer utilizes **Tailscale** to create a secure, private mesh network between user agent instances.

- **Private Peer-to-Peer**: Agents communicate over encrypted WireGuard tunnels provided by Tailscale.
- **Service Discovery**: Tailscale (MagicDNS) allows agents like 'Sirokuma' (representing User A) and 'Kani' (representing User B) to locate each other securely regardless of their physical network location.
- **Identity-Bound Connectivity**: Connections are authenticated via Tailscale identity, ensuring only authorized agents can initiate a handshake.

## Mediation Protocol (gRPC & Protobuf)
Agent-to-agent communication is standardized via a high-performance mediation protocol.

### Protobuf Definition
The interface is defined in `synergy.proto`, covering:
- **Handshake**: Identity verification and capability exchange.
- **Context Sharing**: Sharing abstracted profile summaries and synergy goals.
- **Proposal**: Suggesting potential connection points or topics of conversation for the humans.

### gRPC Implementation
- **Performance**: Low-latency communication essential for real-time mediation.
- **Strong Typing**: Ensures consistent data structures across different agent implementations (Rust backend vs Node.js clients).
- **Streaming**: Supports long-lived streams for collaborative profiling and multi-agent negotiation.

## Data Flow
1. **User Interaction**: User talks to their agent (Next.js Frontend -> Rust Backend).
2. **Discovery**: Backend identifies potential synergies using the `x-algorithm` based scorer.
3. **Mediation**: The local agent initiates a gRPC call over the Tailscale tunnel to the target agent.
4. **Scoring**: Agents exchange Protobuf messages to refine the synergy score.
5. **Notification**: If a threshold is met, both users are notified of the "Catalyst" event.
