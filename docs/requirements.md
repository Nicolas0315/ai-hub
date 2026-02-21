# Katala Requirements

## Overview

Katala is an AI-mediated social platform where personal AI agents act as catalysts for human connection. It leverages advanced profiling through dialogue and agent-to-agent mediation to foster deep, high-synergy relationships.

## Core Features

### 1. AI-Mediated Catalyst & Profiling

- **Dialogue-driven Profiling**: Move beyond static forms. The platform uses AI-driven conversations to discover user values, personality traits (evolution of MBTI), and goals.
- **Dynamic Updates**: Profiles are not fixed; they evolve based on ongoing interactions and feedback.
- **Multilingual Support**: Full support for English, Japanese, Spanish, and Chinese (Simplified/Traditional) to enable global synergy.

### 2. Agent-to-Agent Surface (The Mediation Protocol)

- **Pre-connection Interaction**: User agents (e.g., 'Sirokuma' and 'Kani') interact before users do.
- **Privacy-Preserving Discovery**: Agents evaluate compatibility and share relevant context without exposing full user data prematurely.
- **Mediation Protocol**: A standardized gRPC/Protobuf protocol for inter-agent communication.

### 3. Connection Modes

- **Nexus Mode**: Discovery of new, high-synergy connections based on the "Autonomous Synergy Scoring" algorithm.
- **Close Friends Mode**: High-fidelity synchronization between trusted circles. Priority mediation and deeper context sharing.

### 4. Authentication & Security

- **Vercel Auth**: Seamless, secure authentication using Auth.js (NextAuth) integrated with the Vercel ecosystem.
- **Tailscale Integration**: Secure, peer-to-peer connectivity for agent mediation (the 'Sirokuma-Kani' connection).

## Technical Requirements

- **Frontend**: Next.js (App Router), Tailwind CSS, Framer Motion.
- **Backend**: Rust-based core services for performance and safety, integrating `x-algorithm` logic.
- **AI**: Claude 3.5 Sonnet/Opus for high-reasoning mediation tasks.
- **Localization**: i18n support for the initial four languages.
