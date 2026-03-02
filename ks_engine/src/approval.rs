// Approval — Execution gating for coding mode.
//
// In coding mode, code changes require explicit approval from an authorized approver.
// Without approval, the system returns read-only responses only.
//
// Design: Youta Hilono
// Implementation: Shirokuma, 2026-03-02

use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::audit_log::{AuditEvent, AuditEventKind, AuditLog};

// ══════════════════════════════════════════════
// APPROVAL GATE
// ══════════════════════════════════════════════

/// Verification metadata required by KS output.
#[derive(Debug, Clone)]
pub struct VerificationMeta {
    pub confidence: f64,
    pub bias: f64,
    pub verdict: String,
    pub solver_pass_rate: f64,
}

/// KCS gate result for code/text.
#[derive(Debug, Clone)]
pub struct KcsGateResult {
    pub code_passed: bool,
    pub text_passed: bool,
    pub code_grade: String,
    pub text_grade: String,
    pub code_fidelity: f64,
    pub text_fidelity: f64,
}

/// A request for approval to execute code changes.
#[derive(Debug, Clone)]
pub struct ApprovalRequest {
    pub request_id: String,
    pub channel: String,
    pub requester: String,
    pub description: String,
    pub ks_meta: VerificationMeta,
    pub kcs_result: KcsGateResult,
    pub timestamp: u64,
}

/// Approval decision.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ApprovalDecision {
    /// Approved — proceed with execution.
    Granted,
    /// Denied — read-only response only.
    Denied { reason: String },
    /// Pending — waiting for approver.
    Pending,
}

/// Result of the full coding-mode pipeline gate.
#[derive(Debug, Clone)]
pub struct GateResult {
    pub ks_passed: bool,
    pub kcs_passed: bool,
    pub approval: ApprovalDecision,
    pub can_execute: bool,
    pub details: String,
}

/// The approval gate. Checks KS/KCS results and manages approval state.
pub struct ApprovalGate {
    /// Authorized approver user IDs (designers).
    approvers: Vec<String>,
    /// Pending approval requests.
    pending: Arc<Mutex<Vec<ApprovalRequest>>>,
    /// Shared audit log.
    audit: Arc<Mutex<AuditLog>>,
}

impl ApprovalGate {
    pub fn new(approvers: Vec<String>, audit: Arc<Mutex<AuditLog>>) -> Self {
        Self {
            approvers,
            pending: Arc::new(Mutex::new(Vec::new())),
            audit,
        }
    }

    /// Check if a user is an authorized approver.
    pub fn is_approver(&self, user_id: &str) -> bool {
        self.approvers.contains(&user_id.to_string())
    }

    /// Run the full gate check: KS → KCS → approval required.
    /// Returns a GateResult indicating whether execution is allowed.
    pub fn check(
        &self,
        channel: &str,
        requester: &str,
        description: &str,
        ks_meta: &VerificationMeta,
        kcs_result: &KcsGateResult,
    ) -> GateResult {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        // Gate 1: KS verification must pass
        let ks_passed = ks_meta.verdict == "PASS" && ks_meta.confidence >= 0.70;

        // Gate 2: KCS must pass for both code and text
        let kcs_passed = kcs_result.code_passed && kcs_result.text_passed;

        if !ks_passed {
            self.audit.lock().unwrap().log(AuditEvent {
                kind: AuditEventKind::ApprovalDenied,
                channel: channel.to_string(),
                user_id: requester.to_string(),
                timestamp: now,
                details: Some(format!(
                    "KS gate failed: verdict={}, confidence={:.3}",
                    ks_meta.verdict, ks_meta.confidence
                )),
            });

            return GateResult {
                ks_passed: false,
                kcs_passed,
                approval: ApprovalDecision::Denied {
                    reason: format!("KS verification failed (confidence={:.3})", ks_meta.confidence),
                },
                can_execute: false,
                details: "KS gate blocked execution".to_string(),
            };
        }

        if !kcs_passed {
            self.audit.lock().unwrap().log(AuditEvent {
                kind: AuditEventKind::ApprovalDenied,
                channel: channel.to_string(),
                user_id: requester.to_string(),
                timestamp: now,
                details: Some(format!(
                    "KCS gate failed: code={}/{:.3}, text={}/{:.3}",
                    kcs_result.code_grade, kcs_result.code_fidelity,
                    kcs_result.text_grade, kcs_result.text_fidelity
                )),
            });

            return GateResult {
                ks_passed: true,
                kcs_passed: false,
                approval: ApprovalDecision::Denied {
                    reason: format!(
                        "KCS gate failed (code={}, text={})",
                        kcs_result.code_grade, kcs_result.text_grade
                    ),
                },
                can_execute: false,
                details: "KCS gate blocked execution".to_string(),
            };
        }

        // Both gates passed — request approval from authorized user
        let request = ApprovalRequest {
            request_id: format!("req-{}-{}", channel, now),
            channel: channel.to_string(),
            requester: requester.to_string(),
            description: description.to_string(),
            ks_meta: ks_meta.clone(),
            kcs_result: kcs_result.clone(),
            timestamp: now,
        };

        self.audit.lock().unwrap().log(AuditEvent {
            kind: AuditEventKind::ApprovalRequired,
            channel: channel.to_string(),
            user_id: requester.to_string(),
            timestamp: now,
            details: Some(format!(
                "KS={:.3}/KCS=code:{}/text:{} — awaiting approver",
                ks_meta.confidence, kcs_result.code_grade, kcs_result.text_grade
            )),
        });

        self.pending.lock().unwrap().push(request);

        GateResult {
            ks_passed: true,
            kcs_passed: true,
            approval: ApprovalDecision::Pending,
            can_execute: false,
            details: "Awaiting approver authorization".to_string(),
        }
    }

    /// An approver grants approval for a pending request.
    pub fn grant(&self, request_id: &str, approver_id: &str) -> Result<(), String> {
        if !self.is_approver(approver_id) {
            return Err(format!("User {} is not an authorized approver", approver_id));
        }

        let mut pending = self.pending.lock().unwrap();
        let pos = pending.iter().position(|r| r.request_id == request_id);

        match pos {
            Some(idx) => {
                let req = pending.remove(idx);
                let now = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs();

                self.audit.lock().unwrap().log(AuditEvent {
                    kind: AuditEventKind::ApprovalGranted,
                    channel: req.channel,
                    user_id: approver_id.to_string(),
                    timestamp: now,
                    details: Some(format!("Approved request {} from {}", request_id, req.requester)),
                });

                Ok(())
            }
            None => Err(format!("No pending request with id {}", request_id)),
        }
    }

    /// An approver denies a pending request.
    pub fn deny(&self, request_id: &str, approver_id: &str, reason: &str) -> Result<(), String> {
        if !self.is_approver(approver_id) {
            return Err(format!("User {} is not an authorized approver", approver_id));
        }

        let mut pending = self.pending.lock().unwrap();
        let pos = pending.iter().position(|r| r.request_id == request_id);

        match pos {
            Some(idx) => {
                let req = pending.remove(idx);
                let now = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs();

                self.audit.lock().unwrap().log(AuditEvent {
                    kind: AuditEventKind::ApprovalDenied,
                    channel: req.channel,
                    user_id: approver_id.to_string(),
                    timestamp: now,
                    details: Some(format!("Denied request {}: {}", request_id, reason)),
                });

                Ok(())
            }
            None => Err(format!("No pending request with id {}", request_id)),
        }
    }

    /// List pending approval requests.
    pub fn pending_requests(&self) -> Vec<ApprovalRequest> {
        self.pending.lock().unwrap().clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::audit_log::AuditLog;

    fn make_gate() -> ApprovalGate {
        let audit = Arc::new(Mutex::new(AuditLog::new()));
        let approvers = vec!["youta".to_string(), "nicolas".to_string()];
        ApprovalGate::new(approvers, audit)
    }

    fn good_ks() -> VerificationMeta {
        VerificationMeta {
            confidence: 0.85,
            bias: 0.02,
            verdict: "PASS".to_string(),
            solver_pass_rate: 0.88,
        }
    }

    fn bad_ks() -> VerificationMeta {
        VerificationMeta {
            confidence: 0.45,
            bias: 0.30,
            verdict: "FAIL".to_string(),
            solver_pass_rate: 0.40,
        }
    }

    fn good_kcs() -> KcsGateResult {
        KcsGateResult {
            code_passed: true,
            text_passed: true,
            code_grade: "B".to_string(),
            text_grade: "B".to_string(),
            code_fidelity: 0.75,
            text_fidelity: 0.72,
        }
    }

    fn bad_kcs() -> KcsGateResult {
        KcsGateResult {
            code_passed: false,
            text_passed: true,
            code_grade: "D".to_string(),
            text_grade: "B".to_string(),
            code_fidelity: 0.35,
            text_fidelity: 0.72,
        }
    }

    #[test]
    fn test_approver_check() {
        let gate = make_gate();
        assert!(gate.is_approver("youta"));
        assert!(gate.is_approver("nicolas"));
        assert!(!gate.is_approver("random_user"));
    }

    #[test]
    fn test_ks_fail_blocks() {
        let gate = make_gate();
        let result = gate.check("dev", "shirokuma", "fix bug", &bad_ks(), &good_kcs());
        assert!(!result.ks_passed);
        assert!(!result.can_execute);
        assert!(matches!(result.approval, ApprovalDecision::Denied { .. }));
    }

    #[test]
    fn test_kcs_fail_blocks() {
        let gate = make_gate();
        let result = gate.check("dev", "shirokuma", "fix bug", &good_ks(), &bad_kcs());
        assert!(result.ks_passed);
        assert!(!result.kcs_passed);
        assert!(!result.can_execute);
    }

    #[test]
    fn test_both_pass_pending() {
        let gate = make_gate();
        let result = gate.check("dev", "shirokuma", "fix bug", &good_ks(), &good_kcs());
        assert!(result.ks_passed);
        assert!(result.kcs_passed);
        assert_eq!(result.approval, ApprovalDecision::Pending);
        assert!(!result.can_execute); // Still needs approver
        assert_eq!(gate.pending_requests().len(), 1);
    }

    #[test]
    fn test_grant_approval() {
        let gate = make_gate();
        gate.check("dev", "shirokuma", "fix bug", &good_ks(), &good_kcs());

        let pending = gate.pending_requests();
        assert_eq!(pending.len(), 1);

        let req_id = &pending[0].request_id;
        assert!(gate.grant(req_id, "youta").is_ok());
        assert_eq!(gate.pending_requests().len(), 0);
    }

    #[test]
    fn test_deny_approval() {
        let gate = make_gate();
        gate.check("dev", "shirokuma", "fix bug", &good_ks(), &good_kcs());

        let pending = gate.pending_requests();
        let req_id = &pending[0].request_id;
        assert!(gate.deny(req_id, "nicolas", "not ready").is_ok());
        assert_eq!(gate.pending_requests().len(), 0);
    }

    #[test]
    fn test_non_approver_rejected() {
        let gate = make_gate();
        gate.check("dev", "shirokuma", "fix bug", &good_ks(), &good_kcs());

        let pending = gate.pending_requests();
        let req_id = &pending[0].request_id;
        assert!(gate.grant(req_id, "random_user").is_err());
    }
}
