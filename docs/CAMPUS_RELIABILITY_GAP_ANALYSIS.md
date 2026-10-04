# Campus Reliability Gap Analysis
**For: Campus Life OS — BPUT Hackathon 2026**

---

## 1. EXISTING CAPABILITY vs REQUESTED FRAMEWORKS

### FRAMEWORK 1 — PRIORITY MODEL

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Priority values | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` hard-coded in `Complaint.priority` | No context-aware rules. Student-selectable priority. No P0-P3 mapping. | HIGH |
| Rules engine | `ComplaintRoutingAgent._estimate_priority()` uses keyword matching only | No configurable policy table. Hard-coded in agent. | HIGH |
| Impact/Urgency/Safety scoring | None | No blast-radius, no safety conditions, no affected-population weighting | HIGH |
| P0-P3 naming | Uses `CRITICAL` instead of `P0` | Inconsistent with industry SRE vocabulary | MEDIUM |

**MISSING:** Configurable priority rules table; context-aware overrides (e.g., "student at gate" → P0); policy-driven priority calculation server-side.

---

### FRAMEWORK 2 — SLA ENGINE

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| SLA tracking | `ComplaintRoutingAgent.ROUTING_CONFIG_TABLE` has `sla_hours` per category | Not enforced. No clocks. No breach detection. | HIGH |
| Acknowledgement SLA | None | No `ack_due_at` timestamp. No acknowledgement tracking. | HIGH |
| Action SLA | None | No `action_due_at`. No action-started tracking. | HIGH |
| Resolution SLA | `config.AGEING_*_HOURS` only for display buckets | No actual due-time enforcement. No breach detection. | HIGH |
| AT-RISK detection | None | No 80%-elapsed warning. No proactive escalation. | HIGH |
| SLA states (ON_TRACK/AT_RISK/BREACHED/PAUSED/MET) | None | No state enumeration. No transitions. | HIGH |
| Multiple SLA clocks | None | No acknowledgement/action/resolution separation | MEDIUM |

**MISSING:** SLA policy table; clock start/stop logic; at-risk detection; breach detection; configurable thresholds per priority/domain/service.

---

### FRAMEWORK 3 — OLA (Operational Level Agreements)

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| OLA stages | None | No internal stage breakdown for external SLA visibility. | HIGH |
| Stage-level timing | `PolicyAgent` has step definitions but no timing | No per-step due times. No OLA clock. | HIGH |
| Failure attribution | None | Cannot identify which internal stage caused external SLA failure. | HIGH |

**MISSING:** OLA stage definitions with timing; stage-level SLA breach tracking; admin-visible OLA dashboard.

---

### FRAMEWORK 4 — OWNERSHIP

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Current owner | `Complaint.assigned_to` | No time-with-owner tracking. No ownership history. | HIGH |
| Ownership display | Basic assignee name | No "Pending with CSE HOD — 03m 42s" style display. | HIGH |
| Ownership history | `ComplaintAuditTrail` exists but not structured for ownership | No dedicated `ownership_history` table. | MEDIUM |
| Clear owner rule | `assigned_to` nullable; can be NULL | No enforcement that every active request must have owner. | MEDIUM |

**MISSING:** `OwnershipHistory` table; current owner display with elapsed time; ownership assignment validation.

---

### FRAMEWORK 5 — ESCALATION ENGINE

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Escalation | None | No automatic escalation. Manual status changes only. | HIGH |
| Escalation policies | None | No configurable chains. Hard-coded nowhere. | HIGH |
| Escalation triggers | None | No no-acknowledgement/no-action/SLA-breach triggers. | HIGH |
| Escalation audit | `ComplaintAuditTrail` has `ESCALATED` action but never used | No formal escalation event logging. | HIGH |

**MISSING:** `EscalationPolicy` table; `EscalationEvent` table; automated escalation logic; configurable chains per domain/service.

---

### FRAMEWORK 6 — DELEGATION

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Delegation | None | No delegate/absent-owner routing. | HIGH |
| Acting authority | None | No acting HOD or temporary authority. | HIGH |
| Time-bound delegation | None | No start_time/end_time for delegation. | HIGH |

**MISSING:** `Delegation` table; delegate lookup in ownership resolution; delegation audit trail.

---

### FRAMEWORK 7 — ZERO-CHASE

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Student follow-up | None | No `student_follow_up_count`. No zero-chase metric. | HIGH |
| Auto-reminder | Basic `auto_reminder_sent` flag on Notice only | No per-request reminder logic. No auto-escalation on silence. | HIGH |
| Chasing dashboard | None | No "Requests requiring student follow-up" view. | HIGH |

**MISSING:** Follow-up counter on requests; auto-reminder scheduler; zero-chase compliance dashboard; admin KPI.

---

### FRAMEWORK 8 — NO-DEAD-END

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Rejection handling | `REJECTED` status exists | No `INFORMATION_REQUIRED` state. No recovery workflow. | HIGH |
| Next action display | None | No "missing document" guidance. No resume workflow. | HIGH |
| Transfer logic | None | No internal transfer without student re-application. | MEDIUM |

**MISSING:** `INFO_REQUESTED` state; document request mechanism; bounce-protection logic; internal transfer API.

---

### FRAMEWORK 9 — BOUNCE PROTECTION

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Wrong-department handling | `REJECTED` ends workflow | No internal transfer. Student must resubmit. | HIGH |
| Handoff tracking | None | No `handoff_count`. No `department_transfer_count`. | HIGH |

**MISSING:** Internal transfer API; handoff counter; bounce audit trail.

---

### FRAMEWORK 10 — HANDOFF BUDGET

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Handoff limit | None | No configurable threshold per service type. | HIGH |
| Friction warning | None | No `PROCESS_FRICTION_WARNING` flag. | HIGH |

**MISSING:** Handoff budget configuration; friction warning logic; admin dashboard exposure.

---

### FRAMEWORK 11 — INCIDENT MANAGEMENT

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Incident model | `Incident` table exists | Limited fields. No severity, owner, affected_population tracking. | MEDIUM |
| Incident creation | `PatternMemoryAgent.merge_cluster_to_incident()` | Manual admin action. No auto-promotion from threshold. | MEDIUM |
| Incident statuses | `INVESTIGATING`, `RESOLVING`, `RESOLVED` | Missing `DETECTED`, `IDENTIFIED`, `FIXING`, `MONITORING`. | MEDIUM |
| Linked requests | `Complaint.incident_id` | Works. No `incident_members` table needed yet. | LOW |

**NEEDS EXTENSION:** Add severity, owner, affected_population, service, started_at, next_update to Incident model.

---

### FRAMEWORK 12 — "I'M AFFECTED TOO"

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Duplicate prevention | None | No "I'm affected too" mechanism on active incidents. | HIGH |
| Affected count | None | No population tracking on incidents. | HIGH |

**MISSING:** `IncidentMember` table; "I'm affected too" API; student link to incident without new ticket.

---

### FRAMEWORK 13 — BLAST RADIUS

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Affected scope | None | No `INDIVIDUAL/ROOM/FLOOR/BUILDING/HOSTEL/DEPARTMENT/CAMPUS` tracking. | HIGH |
| Affected population | None | No estimated/confirmed affected count. | HIGH |
| Scope influence on priority | None | Blast radius does not auto-adjust priority. | MEDIUM |

**MISSING:** Blast radius enum on requests/incidents; affected count field; scope-to-priority rule.

---

### FRAMEWORK 14 — RESOLUTION HANDSHAKE

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Completion ≠ Resolution | None | No `WORK_COMPLETED` vs `RESOLVED` distinction. Direct to RESOLVED. | HIGH |
| Student verification | None | No YES/NO verification step. No reopen flow. | HIGH |
| Verification tracking | None | No `reopen_count`. No resolution quality tracking. | MEDIUM |

**MISSING:** `VERIFICATION_PENDING` state; student verification API; reopen mechanism.

---

### FRAMEWORK 15 — RECURRENCE / INSTITUTIONAL MEMORY

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Pattern detection | `PatternMemoryAgent` exists | Works but operates on raw complaints. Not linked to assets. | LOW |
| Asset history | None | No `Asset` table. No water pump / asset failure history. | HIGH |
| Process history | None | No bonafide certificate process metrics. | HIGH |
| Recurrence linking | `incident_id` on complaints | Works. Extend to asset-level tracking. | MEDIUM |

**MISSING:** `Asset` table; asset failure history; process-level SLA breach rate / handoff metrics.

---

### FRAMEWORK 16 — STUDENT TIME LOST

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Time-loss calculation | None | No `waiting_time × affected_students` metric. | HIGH |
| Dashboard | None | No student-hours-lost breakdown by domain. | HIGH |

**MISSING:** Waiting time tracking per request; student-time-lost calculator; domain breakdown dashboard.

---

### FRAMEWORK 17 — CAMPUS FRICTION INDEX

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Friction score | None | No composite score. No configurable weights. | HIGH |
| Per-process friction | None | No bonafide certificate friction score. | HIGH |

**MISSING:** Friction metric components; weighted formula; admin dashboard.

---

### FRAMEWORK 18 — FIRST-TOUCH RESOLUTION

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| First-touch measurement | None | No first-touch resolution tracking. | MEDIUM |
| Dashboard | None | No first-touch % by service/department. | MEDIUM |

**MISSING:** First-touch flag on resolution; aggregation query; dashboard component.

---

### FRAMEWORK 19 — SLO

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| SLO targets | None | No configurable SLO per service. No actual vs target calculation. | HIGH |
| SLO compliance dashboard | None | No SLO % display. | HIGH |

**MISSING:** `ServiceObjective` table; SLO calculation from real data; SLO dashboard card.

---

### FRAMEWORK 20 — FRICTION BUDGET

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Error budget analogy | None | No `SERVICE_REVIEW_REQUIRED` state when budget exhausted. | HIGH |
| Budget tracking | None | No budget consumption tracking per service. | HIGH |

**MISSING:** Friction budget table; budget exhaustion logic; service review flag.

---

### FRAMEWORK 21 — DEPENDENCY ENGINE

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Parent/child workflows | None | No `OperationalCase` abstraction. No dependency relationships. | HIGH |
| "Going Home" orchestration | None | No multi-request coordination. Student submits 5 separate forms. | HIGH |
| Dependency types | None | No `BLOCKED_BY`, `REQUIRES`, `TRIGGERS`, `PARALLEL_WITH`. | HIGH |

**MISSING:** `WorkflowDependency` table; dependency resolution logic; parallel execution support; parent case model.

---

### FRAMEWORK 22 — CONTEXT-AWARE SLA

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Dynamic priority by context | None | No "student at gate" → P0 rule. No "30 min to deadline" override. | HIGH |
| Deterministic rules | None | No context injection into priority calculation. | HIGH |

**MISSING:** Context-aware priority override rules; deadline-aware SLA; location-aware (GPS?) priority.

---

### FRAMEWORK 23 — FAIRNESS / QUEUE TRANSPARENCY

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Queue position | None | No position tracking. No estimated wait. | MEDIUM |
| Priority override audit | None | No admin override reason logging. | MEDIUM |

**MISSING:** Queue position field; override audit trail; fairness monitoring.

---

### FRAMEWORK 24 — COMMUNICATION LIFECYCLE

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Notice lifecycle | `NoticeReadReceipt` tracks read | Missing `DELIVERED`, `ACKNOWLEDGED`, `ACTION_COMPLETED`, `EXPIRED` states. | MEDIUM |
| Communication categories | `priority` on Notice (NORMAL/URGENT/CRITICAL) | No `EMERGENCY`, `ACTION_REQUIRED`, `IMPORTANT`, `FYI` mapping. | MEDIUM |
| Mandatory acknowledgement | None | No enforce-ack logic. | MEDIUM |

**NEEDS EXTENSION:** Expand Notice read-receipt lifecycle; add communication category enum.

---

### FRAMEWORK 25 — ATTENTION BUDGET

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Notification batching | None | No digest mode. Every notice is immediate interrupt. | MEDIUM |
| Per-student notification metrics | None | No notifications-per-student tracking. | MEDIUM |

**MISSING:** Digest eligibility flag; notification frequency tracking; attention budget dashboard.

---

### FRAMEWORK 26 — POLICY/RULE ENGINE

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Policy storage | `PolicyAgent.CANONICAL_POLICY_CHAINS` hard-coded Python dict | No database-backed policy table. Not configurable without code change. | HIGH |
| Policy types | `GATE_PASS`, `CERTIFICATE_REQUEST`, `MAINTENANCE_COMPLAINT` only | No hostel, academics, safety policies. | MEDIUM |
| Policy evaluation | `PolicyAgent.run()` | Works. Should be extended to SLA/escalation/delegation policies. | MEDIUM |

**MISSING:** Database policy table; admin policy editor; SLA/escalation/delegation policy storage.

---

### FRAMEWORK 27 — AUDITABILITY

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Audit trail | `ComplaintAuditTrail` exists | Limited to complaints. No cross-entity audit. | MEDIUM |
| Audit events | CREATED, STATUS_CHANGED, MERGED_INTO_INCIDENT | Missing many event types (ASSIGNED, ESCALATED, DELEGATED, etc.) | MEDIUM |
| Structured audit | `action`, `previous_status`, `new_status`, `note` | Works. Extend with `reason`, `metadata` JSON. | LOW |

**NEEDS EXTENSION:** Expand audit events; generalize audit table for all operational entities.

---

### FRAMEWORK 28 — CAMPUS PULSE

| Aspect | Existing | Gap | Severity |
|--------|----------|-----|----------|
| Executive dashboard | `AdminDashboard` Control Tower has partial KPIs | Partial: ageing, workload, open tickets. Missing most operational metrics. | HIGH |
| Campus Pulse score | None | No 0-100 composite score. No domain breakdown. | HIGH |
| SLO compliance | None | No SLO % cards. | HIGH |
| Zero-chase compliance | None | No zero-chase % metric. | HIGH |
| Student hours lost | None | No metric displayed. | HIGH |

**MISSING:** Campus Pulse score formula; domain health scores; composite dashboard cards.

---

## 2. REUSABLE AS-IS

| Capability | Location | Reuse Strategy |
|------------|----------|----------------|
| `Complaint` model + `ComplaintAuditTrail` | `backend/app/db/models.py` | Extend with SLA fields, ownership fields. Keep existing. |
| `Incident` model | `backend/app/db/models.py` | Extend with severity, owner, affected_population, service, started_at, next_update |
| `PatternMemoryAgent` | `backend/app/agents/pattern_memory_agent.py` | Reuse spike/chronic detection logic. Extend for asset-level recurrence. |
| `ComplaintRoutingAgent` | `backend/app/agents/complaint_routing_agent.py` | Extend `_estimate_priority()` to call new PolicyEngine for context-aware rules. |
| `PolicyAgent` | `backend/app/agents/policy_agent.py` | Extend to SLA policies, escalation policies. Add database-backed policy storage. |
| `Notice` + `NoticeReadReceipt` | `backend/app/db/models.py` | Extend with communication lifecycle states. |
| `require_role` + `can()` | `backend/app/auth/security.py` | Reuse for new operational endpoints. Add new action constants. |
| Ageing buckets (`>24h`, `>48h`, `>72h`) | `routes_admin.py`, `routes_student.py` | Extend to SLA clock calculations. Replace with `AT_RISK`/`BREACHED` states. |
| `admin/dashboard/analytics` | `backend/app/api/routes_admin.py` | Extend with new metric queries (SLO %, zero-chase, friction, student time). |

---

## 3. PROPOSED CHANGE SUMMARY

### New Database Models (Extensions)

| New/Extended Model | Type | Purpose |
|-------------------|------|---------|
| `OperationalCase` | NEW | Abstract parent for cross-domain workflow tracking (links to existing Complaint, GatePass, Certificate, etc.) |
| `SLAPolicy` | NEW | Configurable SLA rules per domain/service/priority |
| `SLAInstance` | NEW | Per-request SLA clock tracking |
| `OwnershipHistory` | NEW | Ownership assignment/transfer history |
| `EscalationPolicy` | NEW | Configurable escalation chains per domain/service |
| `EscalationEvent` | NEW | Formal escalation audit |
| `Delegation` | NEW | Time-bound delegate assignments |
| `WorkflowDependency` | NEW | Parent/child dependency relationships |
| `IncidentMember` | NEW | "I'm affected too" student links |
| `VerificationEvent` | NEW | Resolution handshake tracking |
| `OperationalAuditEvent` | NEW | Generalized cross-entity audit |
| `ServiceObjective` | NEW | SLO targets per service |
| `Asset` | NEW | Physical asset registry for recurrence tracking |
| `AssetFailure` | NEW | Asset failure history |
| `Delegation` (extended) | EXTEND | Add to existing User model relationship |

### Extended Existing Models

| Model | Change |
|-------|--------|
| `Complaint` | Add: `operational_case_id`, `sla_instance_id`, `current_owner_id`, `ownership_assigned_at`, `blast_scope`, `affected_count`, `handoff_count`, `student_follow_up_count`, `reopen_count`, `context_tags` JSON |
| `Incident` | Add: `severity`, `owner_id`, `affected_population`, `service`, `started_at`, `next_update`, `operational_case_id` |
| `GatePass` | Add: `operational_case_id`, `sla_instance_id`, `context_urgency` |
| `CertificateRequest` | Add: `operational_case_id`, `sla_instance_id`, `handoff_count` |
| `User` | Add: `delegate_id`, `delegate_start`, `delegate_end`, `acting_for_id` |

---

## 4. FILES AFFECTED

### Backend Files to Modify

| File | Change |
|------|--------|
| `backend/app/db/models.py` | Add 8 new models; extend 4 existing models with new fields |
| `backend/app/schemas.py` | Add Pydantic schemas for all new models and API inputs/outputs |
| `backend/app/config.py` | Add SLA/priority configuration constants |
| `backend/app/api/routes_student.py` | Add operational case linking on create; add student timeline endpoint |
| `backend/app/api/routes_staff.py` | Add ownership assignment, SLA actions, escalation actions |
| `backend/app/api/routes_admin.py` | Add Campus Pulse endpoint, SLA metrics, friction metrics, zero-chase metrics |
| `backend/app/auth/security.py` | Add new action constants for operational endpoints |
| `backend/app/agents/complaint_routing_agent.py` | Delegate to new PolicyEngine for priority |
| `backend/app/agents/policy_agent.py` | Extend to SLA/escalation/delegation policies |
| `backend/app/main.py` | Register new routers; add background task scheduler for SLA checks |

### New Backend Files

| File | Purpose |
|------|---------|
| `backend/app/operational/` | New operational engine package |
| `backend/app/operational/engine.py` | Core OperationalCase state machine and SLA calculator |
| `backend/app/operational/sla.py` | SLA policy registry and clock logic |
| `backend/app/operational/escalation.py` | Escalation engine and policy evaluator |
| `backend/app/operational/ownership.py` | Ownership resolution with delegation lookup |
| `backend/app/operational/priority.py` | Context-aware priority calculator |
| `backend/app/operational/metrics.py` | Friction, student-time, SLO calculators |
| `backend/app/api/routes_operations.py` | New operational REST endpoints |
| `backend/app/background/sla_monitor.py` | Background SLA breach/at-risk checker |

### Frontend Files to Modify

| File | Change |
|------|--------|
| `frontend/src/admin/AdminDashboard.jsx` | Extend Control Tower with Campus Pulse, SLA cards, friction, zero-chase |
| `frontend/src/admin/IncidentPanel.jsx` | New incident detail with "I'm affected too" |
| `frontend/src/mobile/requests/StudentRequestsScreen.jsx` | Add student timeline component, resolution handshake UI |
| `frontend/src/staff/StaffDashboard.jsx` | Add ownership display, SLA at-risk indicators |
| `frontend/src/lib/api.js` | Add new operational API endpoints |

---

## 5. DATABASE IMPACT

- **New tables:** 12-15 new tables (see section 3)
- **Extended tables:** 4 existing tables with new nullable columns (backwards-compatible migration)
- **Migration strategy:** SQLAlchemy migration with `alembic` or manual migration script
- **No data destruction:** All existing data preserved
- **Index additions:** New indexes on `sla_instance_id`, `operational_case_id`, `current_owner_id`, `incident_id` for query performance

---

## 6. API IMPACT

### New Endpoints (proposed)

```
GET    /operations/cases                    # List operational cases
GET    /operations/cases/{id}              # Case detail with full timeline
POST   /operations/cases                   # Create operational case (links existing entities)
POST   /operations/cases/{id}/acknowledge  # Acknowledge case
POST   /operations/cases/{id}/transfer     # Transfer ownership
POST   /operations/cases/{id}/delegate     # Delegate to another user
POST   /operations/cases/{id}/escalate    # Manual escalation
POST   /operations/cases/{id}/complete    # Mark work complete
POST   /operations/cases/{id}/verify      # Student verification
POST   /operations/cases/{id}/reopen      # Reopen case
POST   /operations/cases/{id}/request-info # Request information from student

GET    /operations/incidents               # List incidents
GET    /operations/incidents/{id}          # Incident detail
POST   /operations/incidents/{id}/affected # "I'm affected too"

GET    /operations/services/health         # Service health scores
GET    /operations/metrics/pulse          # Campus Pulse score
GET    /operations/metrics/slo            # SLO compliance
GET    /operations/metrics/friction       # Friction index
GET    /operations/metrics/student-time    # Student time lost
GET    /operations/metrics/zero-chase      # Zero-chase compliance
```

### Modified Endpoints

- `POST /student/complaints` — add `operational_case_id` to response
- `POST /student/requests/gatepass` — add `operational_case_id` to response
- `GET /admin/dashboard/analytics` — add new metric fields
- `GET /staff/tickets` — add ownership time, SLA at-risk fields

---

## 7. FRONTEND IMPACT

### Student UI (Minimal Change)
- Add simple status line on requests: "Waiting: 04:12 · Owner: CSE HOD · Expected: 10:42 AM"
- Add resolution handshake: YES/NO buttons when status = WORK_COMPLETED
- Add "I'm affected too" button on incident banner
- NO new screens; just status line additions

### Admin UI (Major Extension)
- Extend Control Tower with Campus Pulse score card
- Add SLA At Risk / SLA Breached count cards
- Add Zero-Chase Compliance % card
- Add First-Touch Resolution % card
- Add Student Hours Lost dashboard
- Add Friction Index per service
- Add Friction Budget status (SERVICE_REVIEW_REQUIRED badges)
- Add Incident detail panel with timeline
- Add "I'm affected too" count on incidents
- Extend X-Ray view to show operational data (SLA status, owner, affected count)

### Staff UI
- Add "Pending with {Owner} — {time}" display instead of just "PENDING"
- Add SLA at-risk warning badges
- Add ownership time display

---

## 8. RISK

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing complaint flow | MEDIUM | HIGH | Only add nullable columns; never modify existing column meanings |
| SLA background scheduler complexity | MEDIUM | MEDIUM | Use simple polling thread; no Celery/Redis dependency |
| State machine proliferation | HIGH | MEDIUM | Keep generic `OperationalCase` simple; reuse for all domains |
| Over-engineering | HIGH | HIGH | Implement Phase 1-2 only; judge usability not feature count |
| Database migration on live system | LOW | HIGH | Use SQLAlchemy `alter()` for nullable additions; test on seed data |
| Frontend scope creep | HIGH | MEDIUM | Keep student UI minimal; only admin/Control Tower gets new views |
| Performance degradation from new queries | MEDIUM | MEDIUM | Add indexes on foreign keys; avoid N+1 queries |
| Concurrency: escalation vs approval race | MEDIUM | HIGH | Use database transactions with row-level locking for state transitions |
| Too many new tables | MEDIUM | LOW | Reuse existing tables where possible (extend rather than create) |

---

## 9. IMPLEMENTATION PRIORITY

### Phase 1 — Foundation (CRITICAL)
1. `OperationalCase` abstraction linking existing entities
2. `SLAPolicy` + `SLAInstance` models
3. Priority rules table (`PriorityPolicy`)
4. Basic SLA clock (created_at → ack_due_at → action_due_at → resolution_due_at)
5. `AT_RISK` / `BREACHED` state detection
6. Ownership assignment on complaint create

### Phase 2 — Reliability
7. Escalation policy + engine
8. Delegation model + resolution
9. Zero-chase follow-up counter
10. Operational audit events
11. Admin SLA dashboard cards

### Phase 3 — Incident Operations
12. Extend Incident model
13. "I'm affected too" API
14. Blast radius tracking
15. Resolution handshake (WORK_COMPLETED → VERIFIED → RESOLVED)
16. Recurrence / institutional memory (Asset table)

### Phase 4 — Orchestration
17. WorkflowDependency model
18. Parent case creation
19. Parallel/sequential dependency execution
20. "Going Home" demo scenario

### Phase 5 — Metrics
21. Student time lost calculator
22. Friction index
23. First-touch resolution
24. SLO compliance calculation
25. Campus Pulse score

### Phase 6 — Control Tower
26. Full Campus Pulse dashboard
27. Service health cards
28. Friction budget display
29. X-Ray operational integration

---

## 10. WHAT NOT TO IMPLEMENT (Yet)

| Framework | Reason to Defer |
|-----------|-----------------|
| Full BPMN engine | Overkill for hackathon demo. Generic state machine + SQL is sufficient. |
| Real-time WebSocket updates | Polling with 2.5s interval already works. Add WebSocket only if judges specifically ask. |
| Kafka/celery background jobs | Adds infrastructure complexity. Simple threading or FastAPI `BackgroundTasks` sufficient for demo. |
| Asset QR/barcode scanning | Nice-to-have. Core operational frameworks take priority. |
| Full mobile redesign | Current mobile UI works. Only add status line updates. |
| Advanced ML/AI anomaly detection | `PatternMemoryAgent` does deterministic detection. Sufficient for demo. |
| Complete policy editor UI | Admin can edit policy JSON directly. Full CRUD UI not needed for Phase 1. |
