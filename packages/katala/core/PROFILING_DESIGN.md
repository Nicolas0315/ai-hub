# Dynamic Profiling Engine: Design & Dialogue Tuning

## Overview

The Katala Dynamic Profiling Engine is designed to maintain a living "Identity Vector" for every user. Unlike static profiles, this engine evolves based on both passive observation (chat history) and active dialogue tuning.

## The Identity Vector

The core data structure is a multi-dimensional JSON object:

- **Personality:** 0.0-1.0 scales for MBTI-style traits.
- **Values:** List of abstract motivators.
- **Professional Focus:** Technical and industry interests.
- **Social Energy:** Real-time state of the user's interaction capacity.

## Dialogue Tuning Flow

Dialogue Tuning allows users to "steer" their own profile.

### The Process:

1. **User Intent:** The user sends a meta-instruction (e.g., "I'm trying to be more decisive" or "I need to focus more on coding and less on management").
2. **Intent Extraction:** The `ProfilingEngine` identifies this as a "Tuning Request" rather than standard chat content.
3. **Vector Adjustment:**
   - For "decisive", the `judging` and `thinking` scores are adjusted upward.
   - For "focus on coding", the `professionalFocus` array is updated, and the `socialEnergy.preferredTone` might shift to "concise".
4. **Confirmation:** Katala acknowledges the shift: _"Got it. I'll adjust our interactions to support that focus."_

## Confidence Scoring

The engine maintains a `confidenceScore` (0.0 - 1.0):

- **Passive Analysis:** Gains ~0.02 per message, capped at 0.8.
- **Direct Tuning:** User corrections provide a +0.2 boost as they are "ground truth".
- **Decay:** Confidence slightly decays over long periods of inactivity, as user interests may have shifted.
