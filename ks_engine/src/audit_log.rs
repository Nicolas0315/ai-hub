// AuditLog — Append-only event log for coding mode lifecycle.
//
// Records: mode_enter, mode_exit, approval_required, approval_granted, approval_denied
// All events are timestamped, channel-scoped, and user-attributed.
//
// Design: Youta Hilono
// Implementation: Shirokuma, 2026-03-02

use serde::Serialize;

// ══════════════════════════════════════════════
// AUDIT EVENT TYPES
// ══════════════════════════════════════════════

/// The 5 audit event kinds specified by Youta.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub enum AuditEventKind {
    /// Coding mode activated.
    ModeEnter,
    /// Coding mode deactivated.
    ModeExit,
    /// Execution requires approver authorization.
    ApprovalRequired,
    /// Approver granted execution permission.
    ApprovalGranted,
    /// Approver denied execution permission (or gate auto-denied).
    ApprovalDenied,
}

impl AuditEventKind {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::ModeEnter => "mode_enter",
            Self::ModeExit => "mode_exit",
            Self::ApprovalRequired => "approval_required",
            Self::ApprovalGranted => "approval_granted",
            Self::ApprovalDenied => "approval_denied",
        }
    }
}

/// A single audit event.
#[derive(Debug, Clone, Serialize)]
pub struct AuditEvent {
    pub kind: AuditEventKind,
    pub channel: String,
    pub user_id: String,
    pub timestamp: u64,
    pub details: Option<String>,
}

// ══════════════════════════════════════════════
// AUDIT LOG (append-only)
// ══════════════════════════════════════════════

/// In-memory append-only audit log.
/// Events can only be added, never removed or modified.
pub struct AuditLog {
    events: Vec<AuditEvent>,
}

impl AuditLog {
    pub fn new() -> Self {
        Self { events: Vec::new() }
    }

    /// Append an event to the log. Append-only — no deletion.
    pub fn log(&mut self, event: AuditEvent) {
        self.events.push(event);
    }

    /// Get all events (read-only).
    pub fn events(&self) -> &[AuditEvent] {
        &self.events
    }

    /// Get events for a specific channel.
    pub fn events_for_channel(&self, channel: &str) -> Vec<&AuditEvent> {
        self.events.iter().filter(|e| e.channel == channel).collect()
    }

    /// Get events of a specific kind.
    pub fn events_of_kind(&self, kind: &AuditEventKind) -> Vec<&AuditEvent> {
        self.events.iter().filter(|e| &e.kind == kind).collect()
    }

    /// Total event count.
    pub fn len(&self) -> usize {
        self.events.len()
    }

    pub fn is_empty(&self) -> bool {
        self.events.is_empty()
    }

    /// Serialize all events to JSON.
    pub fn to_json(&self) -> String {
        serde_json::to_string_pretty(&self.events).unwrap_or_else(|_| "[]".to_string())
    }
}

impl Default for AuditLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_append_only() {
        let mut log = AuditLog::new();
        assert!(log.is_empty());

        log.log(AuditEvent {
            kind: AuditEventKind::ModeEnter,
            channel: "dev".to_string(),
            user_id: "youta".to_string(),
            timestamp: 1000,
            details: None,
        });

        assert_eq!(log.len(), 1);
        assert_eq!(log.events()[0].kind, AuditEventKind::ModeEnter);
    }

    #[test]
    fn test_all_event_kinds() {
        let mut log = AuditLog::new();

        let kinds = vec![
            AuditEventKind::ModeEnter,
            AuditEventKind::ModeExit,
            AuditEventKind::ApprovalRequired,
            AuditEventKind::ApprovalGranted,
            AuditEventKind::ApprovalDenied,
        ];

        for (i, kind) in kinds.iter().enumerate() {
            log.log(AuditEvent {
                kind: kind.clone(),
                channel: "dev".to_string(),
                user_id: "test".to_string(),
                timestamp: 1000 + i as u64,
                details: None,
            });
        }

        assert_eq!(log.len(), 5);

        // Verify as_str
        assert_eq!(AuditEventKind::ModeEnter.as_str(), "mode_enter");
        assert_eq!(AuditEventKind::ModeExit.as_str(), "mode_exit");
        assert_eq!(AuditEventKind::ApprovalRequired.as_str(), "approval_required");
        assert_eq!(AuditEventKind::ApprovalGranted.as_str(), "approval_granted");
        assert_eq!(AuditEventKind::ApprovalDenied.as_str(), "approval_denied");
    }

    #[test]
    fn test_channel_filter() {
        let mut log = AuditLog::new();

        log.log(AuditEvent {
            kind: AuditEventKind::ModeEnter,
            channel: "dev".to_string(),
            user_id: "a".to_string(),
            timestamp: 1000,
            details: None,
        });
        log.log(AuditEvent {
            kind: AuditEventKind::ModeEnter,
            channel: "prod".to_string(),
            user_id: "b".to_string(),
            timestamp: 1001,
            details: None,
        });

        let dev_events = log.events_for_channel("dev");
        assert_eq!(dev_events.len(), 1);
        assert_eq!(dev_events[0].user_id, "a");
    }

    #[test]
    fn test_kind_filter() {
        let mut log = AuditLog::new();

        log.log(AuditEvent {
            kind: AuditEventKind::ModeEnter,
            channel: "dev".to_string(),
            user_id: "a".to_string(),
            timestamp: 1000,
            details: None,
        });
        log.log(AuditEvent {
            kind: AuditEventKind::ApprovalGranted,
            channel: "dev".to_string(),
            user_id: "b".to_string(),
            timestamp: 1001,
            details: Some("approved".to_string()),
        });

        let grants = log.events_of_kind(&AuditEventKind::ApprovalGranted);
        assert_eq!(grants.len(), 1);
        assert_eq!(grants[0].user_id, "b");
    }

    #[test]
    fn test_json_output() {
        let mut log = AuditLog::new();
        log.log(AuditEvent {
            kind: AuditEventKind::ModeEnter,
            channel: "dev".to_string(),
            user_id: "youta".to_string(),
            timestamp: 1000,
            details: Some("test".to_string()),
        });

        let json = log.to_json();
        assert!(json.contains("mode_enter") || json.contains("ModeEnter"));
        assert!(json.contains("youta"));
    }
}
