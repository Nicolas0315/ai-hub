// ModeGate — Coding mode trigger and state management.
//
// When a message contains "Codingモード", the pipeline switches to:
//   LLM → KS → KCS → Approver → Execute
// Without the trigger, the existing flow is used unchanged.
//
// Design: Youta Hilono
// Implementation: Shirokuma, 2026-03-02

use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::audit_log::{AuditEvent, AuditEventKind, AuditLog};

// ══════════════════════════════════════════════
// MODE STATE
// ══════════════════════════════════════════════

/// The coding-mode trigger phrase.
const CODING_MODE_TRIGGER: &str = "Codingモード";

/// Per-channel mode state.
#[derive(Debug, Clone)]
pub struct ModeState {
    pub active: bool,
    pub channel: String,
    pub entered_at: Option<u64>,
    pub entered_by: Option<String>,
}

impl ModeState {
    pub fn new(channel: &str) -> Self {
        Self {
            active: false,
            channel: channel.to_string(),
            entered_at: None,
            entered_by: None,
        }
    }
}

/// ModeGate manages coding-mode activation per channel.
pub struct ModeGate {
    /// Channel → ModeState
    states: Arc<Mutex<std::collections::HashMap<String, ModeState>>>,
    /// Shared audit log
    audit: Arc<Mutex<AuditLog>>,
}

impl ModeGate {
    pub fn new(audit: Arc<Mutex<AuditLog>>) -> Self {
        Self {
            states: Arc::new(Mutex::new(std::collections::HashMap::new())),
            audit,
        }
    }

    /// Check if a message contains the coding-mode trigger.
    pub fn is_trigger(message: &str) -> bool {
        message.contains(CODING_MODE_TRIGGER)
    }

    /// Check if coding mode is currently active for a channel.
    pub fn is_active(&self, channel: &str) -> bool {
        let states = self.states.lock().unwrap();
        states.get(channel).map_or(false, |s| s.active)
    }

    /// Enter coding mode for a channel. Returns true if mode was newly activated.
    pub fn enter(&self, channel: &str, user_id: &str) -> bool {
        let mut states = self.states.lock().unwrap();
        let state = states.entry(channel.to_string()).or_insert_with(|| ModeState::new(channel));

        if state.active {
            return false; // Already active
        }

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        state.active = true;
        state.entered_at = Some(now);
        state.entered_by = Some(user_id.to_string());

        // Log mode_enter
        self.audit.lock().unwrap().log(AuditEvent {
            kind: AuditEventKind::ModeEnter,
            channel: channel.to_string(),
            user_id: user_id.to_string(),
            timestamp: now,
            details: None,
        });

        true
    }

    /// Exit coding mode for a channel. Returns true if mode was deactivated.
    pub fn exit(&self, channel: &str, user_id: &str) -> bool {
        let mut states = self.states.lock().unwrap();
        let state = match states.get_mut(channel) {
            Some(s) if s.active => s,
            _ => return false, // Not active
        };

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let duration = state.entered_at.map(|t| now.saturating_sub(t));

        state.active = false;
        state.entered_at = None;
        state.entered_by = None;

        // Log mode_exit
        self.audit.lock().unwrap().log(AuditEvent {
            kind: AuditEventKind::ModeExit,
            channel: channel.to_string(),
            user_id: user_id.to_string(),
            timestamp: now,
            details: duration.map(|d| format!("duration_secs={}", d)),
        });

        true
    }

    /// Get the current mode state for a channel.
    pub fn get_state(&self, channel: &str) -> ModeState {
        let states = self.states.lock().unwrap();
        states.get(channel).cloned().unwrap_or_else(|| ModeState::new(channel))
    }

    /// Process a message: detect trigger, manage mode, return routing decision.
    pub fn process_message(&self, message: &str, channel: &str, user_id: &str) -> PipelineRoute {
        // Check for trigger
        if Self::is_trigger(message) && !self.is_active(channel) {
            self.enter(channel, user_id);
        }

        if self.is_active(channel) {
            PipelineRoute::CodingMode
        } else {
            PipelineRoute::Normal
        }
    }
}

/// Pipeline routing decision.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PipelineRoute {
    /// Normal flow — existing pipeline, no gates.
    Normal,
    /// Coding mode — LLM → KS → KCS → Approver → Execute.
    CodingMode,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::audit_log::AuditLog;

    fn make_gate() -> ModeGate {
        let audit = Arc::new(Mutex::new(AuditLog::new()));
        ModeGate::new(audit)
    }

    #[test]
    fn test_trigger_detection() {
        assert!(ModeGate::is_trigger("Codingモードで実装して"));
        assert!(ModeGate::is_trigger("開始 Codingモード"));
        assert!(!ModeGate::is_trigger("通常の会話"));
        assert!(!ModeGate::is_trigger("coding mode")); // English doesn't trigger
    }

    #[test]
    fn test_enter_exit() {
        let gate = make_gate();
        assert!(!gate.is_active("dev-katala"));

        assert!(gate.enter("dev-katala", "youta"));
        assert!(gate.is_active("dev-katala"));
        assert!(!gate.enter("dev-katala", "youta")); // Already active

        assert!(gate.exit("dev-katala", "youta"));
        assert!(!gate.is_active("dev-katala"));
        assert!(!gate.exit("dev-katala", "youta")); // Already inactive
    }

    #[test]
    fn test_process_message_routing() {
        let gate = make_gate();

        let route = gate.process_message("普通の会話", "ch1", "user1");
        assert_eq!(route, PipelineRoute::Normal);

        let route = gate.process_message("Codingモードで実装開始", "ch1", "user1");
        assert_eq!(route, PipelineRoute::CodingMode);

        // Subsequent messages in coding mode stay in coding mode
        let route = gate.process_message("この関数を直して", "ch1", "user1");
        assert_eq!(route, PipelineRoute::CodingMode);
    }

    #[test]
    fn test_channel_isolation() {
        let gate = make_gate();
        gate.enter("ch1", "youta");

        assert!(gate.is_active("ch1"));
        assert!(!gate.is_active("ch2")); // Different channel, not active
    }

    #[test]
    fn test_audit_events_logged() {
        let audit = Arc::new(Mutex::new(AuditLog::new()));
        let gate = ModeGate::new(audit.clone());

        gate.enter("dev", "youta");
        gate.exit("dev", "youta");

        let log = audit.lock().unwrap();
        let events = log.events();
        assert_eq!(events.len(), 2);
        assert_eq!(events[0].kind, AuditEventKind::ModeEnter);
        assert_eq!(events[1].kind, AuditEventKind::ModeExit);
    }
}
