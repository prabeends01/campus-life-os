# Campus Reliability Architecture
**For: Campus Life OS — BPUT Hackathon 2026**

---

## 1. DESIGN PHILOSOPHY

> "Every actionable campus workflow must have: a unique ID, a current owner, a time commitment, a breach consequence, and an escalation path."

This architecture introduces a **shared operational layer** that wraps existing entities (Complaint, GatePass, CertificateRequest) with SLA, ownership, escalation, and metrics — without rebuilding those entities from scratch.

**Key principles:**
- Do NOT migrate existing tables into one giant table
- Do NOT replace working complaint/gatepass/certificate flows
- Extend existing models with nullable foreign keys to new operational models
- Business rules live server-side (Python), not in React components
- Configurable policies, not hard-coded institution-specific hierarchies

---

## 2. CORE ABSTRACTION: OperationalCase

```
┌─────────────────────────────────────────────────────┐
│                 OperationalCase                     │
│  (NEW — links to existing domain entities)         │
├─────────────────────────────────────────────────────┤
│  id: int (PK)                                      │
│  domain: enum [ACADEMICS, ADMIN, HOSTEL, COMM, SAFETY]
│  service_type: str   # MAINTENANCE, GATE_PASS, etc │
│  requester_id: int   → User.id                    │
│  current_owner_id: int → User.id                   │
│  owning_role: str                                   │
│  owning_department: str                             │
│  priority: enum [P0, P1, P2, P3]                  │
│  impact: enum [INDIVIDUAL, ROOM, FLOOR, ...]       │
│  urgency: int (1-10)                               │
│  time_sensitivity: int (1-10)                      │
│  status: enum [SUBMITTED, ASSIGNED, ACKNOWLEDGED,  │
│                 IN_PROGRESS, INFO_REQUESTED,        │
│                 WORK_COMPLETED, VERIFICATION_PENDING│
│                 RESOLVED, CLOSED]                  │
│  blast_scope: enum                                 │
│  estimated_affected: int                           │
│  created_at: datetime                               │
│  acknowledged_at: datetime (nullable)              │
│  action_started_at: datetime (nullable)            │
│  completed_at: datetime (nullable)                 │
│  verified_at: datetime (nullable)                  │
│  resolved_at: datetime (nullable)                   │
│  closed_at: datetime (nullable)                     │
│  sla_policy_id: int → SLAPolicy.id (nullable)      │
│  student_follow_up_count: int = 0                 │
│  handoff_count: int = 0                           │
│  reopen_count: int = 0                             │
├─────────────────────────────────────────────────────┤
│  linked_entity_type: str  # "Complaint", "GatePass" │
│  linked_entity_id: int                             │
│  parent_case_id: int → OperationalCase.id (nullable)│
│  incident_id: int → Incident.id (nullable)         │
└─────────────────────────────────────────────────────┘
```

**Important:** `OperationalCase` does NOT duplicate complaint/gatepass data. It references existing entities via `linked_entity_type` + `linked_entity_id`. This preserves all existing functionality while adding operational overlay.

---

## 3. SLA ARCHITECTURE

### 3.1 SLA Policy Table

```
SLAPolicy
├── id: int (PK)
├── domain: str
├── service_type: str
├── priority: enum [P0, P1, P2, P3]
├── ack_sla_minutes: int
├── action_sla_minutes: int
├── resolution_sla_minutes: int
├── at_risk_threshold_pct: float  # 0.80 = warn at 80% elapsed
├── is_active: bool
└── created_at: datetime
```

**Example policies:**
```
domain=SAFETY, service_type=GATE_PASS, priority=P0:
  ack_sla_minutes=2, action_sla_minutes=5, resolution_sla_minutes=10

domain=HOSTEL, service_type=MAINTENANCE, priority=P1:
  ack_sla_minutes=30, action_sla_minutes=60, resolution_sla_minutes=240

domain=ADMIN, service_type=CERTIFICATE, priority=P2:
  ack_sla_minutes=120, action_sla_minutes=480, resolution_sla_minutes=1440
```

### 3.2 SLA Instance (Per-Case Clock)

```
SLAInstance
├── id: int (PK)
├── operational_case_id: int → OperationalCase.id
├── sla_policy_id: int → SLAPolicy.id
├── started_at: datetime
├── ack_due_at: datetime
├── action_due_at: datetime
├── resolution_due_at: datetime
├── acknowledged_at: datetime (nullable)
├── action_started_at: datetime (nullable)
├── resolved_at: datetime (nullable)
├── sla_state: enum [ON_TRACK, AT_RISK, BREACHED, PAUSED, MET]
├── pause_reason: str (nullable)
└── updated_at: datetime
```

### 3.3 SLA State Machine

```
created_at ──────────────────────────────────────────────────────► resolution_due_at
    │                                                              │
    ▼                                                              ▼
ack_due_at ◄───────── AT_RISK (80% elapsed, no ack) ◄───────────── BREACHED
    │                        │                                     │
    ▼                        ▼                                     ▼
ACKNOWLEDGED           ack_due_at exceeded                    SLA breached
    │                   → auto-escalate                         → flag for review
    ▼
action_due_at ◄──────── AT_RISK ◄─────────────────────────────── BREACHED
    │
    ▼
action_started_at ──► action_due_at ◄──── AT_RISK ────────────── BREACHED
    │
    ▼
resolution_due_at ◄── AT_RISK ──────────────────────────────── BREACHED
    │
    ▼
RESOLVED / CLOSED
```

**AT_RISK detection (deterministic, no ML):**
```python
def compute_sla_state(instance: SLAInstance, now: datetime) -> str:
    elapsed = (now - instance.started_at).total_seconds()
    if instance.pause_reason:
        return "PAUSED"

    if instance.resolved_at:
        return "MET"

    ack_deadline = (instance.ack_due_at - instance.started_at).total_seconds()
    if ack_deadline <= 0:
        # Acknowledgement deadline passed but not acknowledged
        return "BREACHED"

    if not instance.acknowledged_at:
        pct = elapsed / ack_deadline
        if pct >= 1.0:
            return "BREACHED"
        if pct >= 0.80:  # at_risk_threshold_pct
            return "AT_RISK"
        return "ON_TRACK"

    # Same logic for action phase...
    # Same logic for resolution phase...
    return "ON_TRACK"
```

---

## 4. OWNERSHIP ARCHITECTURE

### 4.1 Ownership History

```
OwnershipHistory
├── id: int (PK)
├── operational_case_id: int → OperationalCase.id
├── from_owner_id: int → User.id (nullable for initial)
├── to_owner_id: int → User.id
├── reason: str
├── transferred_by: int → User.id (system = 0 for auto)
├── created_at: datetime
└── is_delegation: bool
```

### 4.2 Ownership Resolution

```python
def resolve_current_owner(case: OperationalCase) -> User:
    # 1. Check if primary owner is available
    owner = get_user(case.current_owner_id)
    if is_available(owner):
        return owner

    # 2. Check delegation table
    delegate = get_delegate(owner.id, at=datetime.utcnow())
    if delegate and can_receive_work(delegate):
        return delegate

    # 3. Check acting authority (HOD on leave → Acting HOD)
    acting = get_acting_authority(owner.id, at=datetime.utcnow())
    if acting:
        return acting

    # 4. Escalate to next level (escalation engine handles this)
    return None  # signals escalation needed
```

### 4.3 Ownership Display (Student UI)

Instead of: "PENDING"

Show: "Pending with CSE HOD — 03m 42s"

Calculation: `now - case.ownership_assigned_at` formatted as mm:ss or hh:mm:ss

---

## 5. ESCALATION ARCHITECTURE

### 5.1 Escalation Policy

```
EscalationPolicy
├── id: int (PK)
├── domain: str
├── service_type: str
├── priority: str
├── trigger: enum [NO_ACK, NO_ACTION, SLA_BREACH, MANUAL, SAFETY]
├── delay_minutes: int  # Wait this long before escalating
├── from_role: str
├── to_role: str
├── to_user_id: int → User.id (nullable, role takes precedence)
├── is_active: bool
└── created_at: datetime
```

**Example chains:**
```
# Emergency Gate Pass
domain=SAFETY, service_type=GATE_PASS, priority=P0:
  Step 1: NO_ACK, delay=2min, from_role=HOD, to_role=PRINCIPAL
  Step 2: NO_ACK, delay=5min, from_role=PRINCIPAL, to_role=EMERGENCY_AUTH

# Hostel Maintenance
domain=HOSTEL, service_type=MAINTENANCE, priority=P1:
  Step 1: SLA_BREACH, delay=0, from_role=ELECTRICIAN, to_role=MAINT_SUPERVISOR
  Step 2: SLA_BREACH, delay=30min, from_role=MAINT_SUPERVISOR, to_role=FACILITIES_MGR
  Step 3: SLA_BREACH, delay=60min, from_role=FACILITIES_MGR, to_role=WARDEN

# Certificate
domain=ADMIN, service_type=CERTIFICATE, priority=P2:
  Step 1: NO_ACTION, delay=240min, from_role=ACADEMIC_OFFICE, to_role=SUPERINTENDENT
  Step 2: NO_ACTION, delay=480min, from_role=SUPERINTENDENT, to_role=REGISTRAR
```

### 5.2 Escalation Event

```
EscalationEvent
├── id: int (PK)
├── operational_case_id: int → OperationalCase.id
├── from_owner_id: int → User.id (nullable)
├── from_role: str
├── to_owner_id: int → User.id (nullable)
├── to_role: str
├── reason: str  # NO_ACK, SLA_BREACH, MANUAL, etc.
├── sla_state_at_escalation: str
├── triggered_by_system: bool
├── created_at: datetime
└── note: str (nullable)
```

### 5.3 Escalation Engine (Deterministic)

```python
def evaluate_escalation(case: OperationalCase, sla_instance: SLAInstance):
    if case.status in [RESOLVED, CLOSED]:
        return  # No escalation for closed cases

    policy = get_escalation_policy(case.domain, case.service_type, case.priority)
    if not policy:
        return

    now = datetime.utcnow()
    for step in policy.steps:
        if should_escalate(step, case, sla_instance, now):
            execute_escalation(case, step, sla_instance)
            break  # One escalation per evaluation cycle

def should_escalate(step, case, sla, now):
    if step.trigger == "SLA_BREACH":
        return sla.sla_state == "BREACHED"
    if step.trigger == "NO_ACK":
        return sla.acknowledged_at is None and now > sla.ack_due_at
    if step.trigger == "NO_ACTION":
        return sla.action_started_at is None and now > sla.action_due_at
    if step.trigger == "MANUAL":
        return False  # Manual escalation only via API call
    return False
```

---

## 6. DELEGATION ARCHITECTURE

```
Delegation
├── id: int (PK)
├── delegator_id: int → User.id
├── delegate_id: int → User.id
├── start_time: datetime
├── end_time: datetime
├── reason: str
├── is_active: bool
└── created_at: datetime
```

**Rules:**
- Delegate must have same or higher role level
- Time-bounded with start/end
- Audit trail on every delegation use
- Delegation does not cascade (delegate cannot delegate further without explicit chain)

---

## 7. PRIORITY MODEL

### 7.1 Priority Calculation (Server-Side Only)

```python
# Deterministic priority rules — no ML, no randomness
PRIORITY_RULES = [
    # Safety overrides
    Rule(priority=P0, conditions=[
        Condition(field="safety_keyword", op="in", value=["spark", "fire", "shock", "exposed wire"]),
        Condition(field="context", op="eq", value="student_at_gate"),
    ]),
    Rule(priority=P0, conditions=[
        Condition(field="deadline_minutes", op="lte", value=30),
        Condition(field="service_type", op="eq", value="fee_discrepancy"),
    ]),
    # High population impact
    Rule(priority=P1, conditions=[
        Condition(field="affected_count", op="gte", value=50),
        Condition(field="blast_scope", op="in", value=["FLOOR", "BUILDING"]),
    ]),
    # Context-aware overrides
    Rule(priority=P1, conditions=[
        Condition(field="context", op="eq", value="student_physically_waiting"),
        Condition(field="service_type", op="eq", value="gate_pass"),
    ]),
]

def calculate_priority(service_type, context, affected_count, blast_scope, text) -> Priority:
    for rule in PRIORITY_RULES:
        if rule.matches(service_type, context, affected_count, blast_scope, text):
            return rule.priority
    return Priority.P2  # Default
```

### 7.2 Priority Override API

```
POST /operations/cases/{id}/override-priority
Body: { "new_priority": "P1", "reason": "Student at gate requires immediate handling" }
```

All overrides are logged in audit trail.

---

## 8. STATE MACHINE

### 8.1 Generic OperationalCase States

```
                    ┌──────────────────────────────────────────┐
                    │                                          │
                    ▼                                          │
SUBMITTED ──► ASSIGNED ──► ACKNOWLEDGED ──► IN_PROGRESS       │
                    │                    │                      │
                    │                    │                      │
                    │     ┌──────────────┴──────────────┐      │
                    │     │                             │      │
                    │     ▼                             ▼      │
                    │  INFO_REQUESTED ──────────► RESUMING      │
                    │       ▲                             │    │
                    │       │ info received               │    │
                    │       └─────────────────────────────┘    │
                    │                                          │
                    │                         ┌────────────────┘
                    │                         │
                    ▼                         ▼
              WORK_COMPLETED ───► VERIFICATION_PENDING
                    │                     │
                    │    ┌────────────────┘
                    │    │ student confirms
                    │    ▼
                    │  RESOLVED
                    │    │
                    │    │ no reopen within 48h
                    │    ▼
                    │  CLOSED
                    │
                    └────────────────────────────────────────► REOPENED ──► (back to ASSIGNED)
                         │ via escalation
                         ▼
                    ESCALATED
```

### 8.2 State Transition Rules

```python
LEGAL_TRANSITIONS = {
    "SUBMITTED": ["ASSIGNED", "ESCALATED", "CANCELLED"],
    "ASSIGNED": ["ACKNOWLEDGED", "TRANSFERRED", "ESCALATED", "CANCELLED"],
    "ACKNOWLEDGED": ["IN_PROGRESS", "INFO_REQUESTED", "ESCALATED"],
    "IN_PROGRESS": ["WORK_COMPLETED", "INFO_REQUESTED", "ESCALATED"],
    "INFO_REQUESTED": ["RESUMING"],  # Only student action exits this
    "RESUMING": ["IN_PROGRESS"],
    "WORK_COMPLETED": ["VERIFICATION_PENDING", "RESOLVED"],  # Auto-resolve if no verification needed
    "VERIFICATION_PENDING": ["RESOLVED", "REOPENED"],
    "RESOLVED": ["CLOSED", "REOPENED"],
    "CLOSED": ["REOPENED"],  # Rare; needs admin approval
    "REOPENED": ["ASSIGNED"],
    "ESCALATED": ["ASSIGNED"],  # After escalation resolves
    "CANCELLED": [],  # Terminal
}

def validate_transition(from_state: str, to_state: str) -> bool:
    return to_state in LEGAL_TRANSITIONS.get(from_state, [])
```

---

## 9. INCIDENT MODEL EXTENSION

```
Incident (extended)
├── id: int (PK)
├── title: str
├── category: str
├── place: str
├── description: str
├── status: enum [DETECTED, INVESTIGATING, IDENTIFIED, FIXING, MONITORING, RESOLVED]
├── severity: enum [P0, P1, P2, P3]
├── owner_id: int → User.id
├── owning_department: str
├── affected_population: int
├── service: str  # WATER_SUPPLY, ELECTRICAL, WIFI, etc.
├── started_at: datetime
├── next_update: datetime (nullable)
├── operational_case_id: int → OperationalCase.id (nullable)
└── resolved_at: datetime (nullable)

IncidentMember
├── id: int (PK)
├── incident_id: int → Incident.id
├── student_id: int → User.id
├── linked_case_id: int → OperationalCase.id (nullable)
├── joined_at: datetime
└── impact_statement: str (nullable)
```

---

## 10. DEPENDENCY ENGINE

```
WorkflowDependency
├── id: int (PK)
├── parent_case_id: int → OperationalCase.id
├── child_case_id: int → OperationalCase.id
├── dependency_type: enum [BLOCKED_BY, REQUIRES, TRIGGERS, PARALLEL_WITH, CHILD_OF]
├── execution_order: int  # 0 = parallel with siblings
├── is_active: bool
└── created_at: datetime
```

### 10.1 "Going Home" Example

```
Parent Case: "Student going home for 3 days"
  ├── Child 1: Leave Approval (BLOCKED_BY: parent) → SEQUENTIAL
  ├── Child 2: Hostel Status (REQUIRES: Leave Approval) → SEQUENTIAL
  ├── Child 3: Gate Authorization (REQUIRES: Leave Approval) → SEQUENTIAL
  ├── Child 4: Security Checkpoint (TRIGGERS: Gate Authorization) → PARALLEL
  ├── Child 5: Mess Count Adjustment (CHILD_OF: parent) → PARALLEL
  └── Child 6: Return Confirmation (BLOCKED_BY: all others) → FINAL
```

### 10.2 Dependency Resolution

```python
def get_runnable_cases(parent_id: int) -> List[OperationalCase]:
    """Return cases whose dependencies are satisfied."""
    children = get_child_cases(parent_id)
    runnable = []
    for child in children:
        deps = get_dependencies(child.id)
        if all(is_met(d) for d in deps):
            runnable.append(child)
    return runnable

def execute_parallel_cases(cases: List[OperationalCase]):
    """Execute cases marked PARALLEL_WITH simultaneously."""
    for case in cases:
        if case.dependency_type == "PARALLEL_WITH":
            assign_and_track(case)
```

---

## 11. METRICS ENGINE

### 11.1 Student Time Lost

```python
def calculate_student_time_lost(case: OperationalCase) -> dict:
    if not case.acknowledged_at:
        waiting_time = (datetime.utcnow() - case.created_at)
    elif not case.action_started_at:
        waiting_time = (case.acknowledged_at - case.created_at)
    elif not case.resolved_at:
        waiting_time = (datetime.utcnow() - case.action_started_at)
    else:
        waiting_time = (case.resolved_at - case.created_at)

    return {
        "case_id": case.id,
        "waiting_seconds": waiting_time.total_seconds(),
        "affected_students": case.estimated_affected or 1,
        "student_minutes": waiting_time.total_seconds() / 60 * (case.estimated_affected or 1)
    }

def aggregate_student_time(domain: str, since: datetime) -> dict:
    cases = get_cases(domain=domain, created_at__gte=since)
    total_minutes = sum(c.student_minutes for c in cases)
    return {
        "domain": domain,
        "total_student_minutes": total_minutes,
        "total_student_hours": total_minutes / 60,
        "case_count": len(cases)
    }
```

### 11.2 Friction Index

```python
def calculate_friction_score(case: OperationalCase) -> float:
    """
    Configurable weighted formula. Weights stored in config table.
    All inputs are integers/counts from the case record.
    """
    weights = get_friction_weights(case.service_type)

    components = {
        "waiting_score": min(case.total_waiting_hours / 24, 1.0) * weights.waiting,
        "handoff_score": min(case.handoff_count / 5, 1.0) * weights.handoffs,
        "escalation_score": min(case.escalation_count / 3, 1.0) * weights.escalations,
        "reopen_score": min(case.reopen_count / 2, 1.0) * weights.reopens,
        "followup_score": min(case.student_follow_up_count / 3, 1.0) * weights.followups,
    }

    total = sum(components.values())
    return round(total * 100, 1)  # 0-100 scale
```

### 11.3 Campus Pulse

```python
def calculate_campus_pulse() -> dict:
    """
    Composite 0-100 score. Formula is documented and configurable.
    Does NOT fabricate numbers. Uses real query results.
    """
    slo_pct = calculate_overall_slo_compliance()
    zero_chase_pct = calculate_zero_chase_compliance()
    first_touch_pct = calculate_first_touch_resolution()
    friction_score = calculate_average_friction()

    # Configurable weights
    W_SLO = 0.30
    W_ZERO_CHASE = 0.25
    W_FIRST_TOUCH = 0.25
    W_FRICTION = 0.20  # Inverted (lower is better)

    pulse = (
        slo_pct * W_SLO +
        zero_chase_pct * W_ZERO_CHASE +
        first_touch_pct * W_FIRST_TOUCH +
        (100 - friction_score) * W_FRICTION  # Invert friction
    )

    return {
        "overall": round(pulse, 1),
        "domains": {
            "ACADEMICS": calculate_domain_pulse("ACADEMICS"),
            "ADMIN": calculate_domain_pulse("ADMIN"),
            "HOSTEL": calculate_domain_pulse("HOSTEL"),
            "COMMUNICATION": calculate_domain_pulse("COMMUNICATION"),
            "SAFETY": calculate_domain_pulse("SAFETY"),
        },
        "breakdown": {
            "slo_pct": slo_pct,
            "zero_chase_pct": zero_chase_pct,
            "first_touch_pct": first_touch_pct,
            "friction_score": friction_score,
        }
    }
```

---

## 12. BOUNCE PROTECTION

When a case is received on the wrong entity:

```python
def handle_bounce(case: OperationalCase, correct_domain: str):
    """
    Internal transfer WITHOUT student re-application.
    Preserves request ID, attachments, history, SLA context.
    """
    audit = OperationalAuditEvent(
        event_type="BOUNCED",
        case_id=case.id,
        actor_id=0,  # System
        old_value=case.owning_department,
        new_value=correct_domain,
        reason="Wrong department routing",
        metadata_json=json.dumps({
            "original_entity": case.linked_entity_type,
            "original_entity_id": case.linked_entity_id,
            "transfer_count": case.handoff_count
        })
    )
    db.add(audit)

    case.owning_department = correct_domain
    case.handoff_count += 1
    case.department_transfer_count += 1

    # Re-trigger ownership resolution
    new_owner = resolve_current_owner(case)
    transfer_ownership(case, new_owner)
```

---

## 13. BACKGROUND PROCESSING

### 13.1 SLA Monitor

```python
# In backend/app/background/sla_monitor.py
import threading
import time

class SLAMonitor:
    def __init__(self, db_session_factory, interval_seconds=30):
        self.db_session_factory = db_session_factory
        self.interval = interval_seconds
        self._running = False

    def start(self):
        self._running = True
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            self._check_sla()
            time.sleep(self.interval)

    def _check_sla(self):
        db = self.db_session_factory()
        try:
            cases = db.query(OperationalCase).filter(
                OperationalCase.status.notin_(["RESOLVED", "CLOSED", "CANCELLED"])
            ).all()

            for case in cases:
                sla = get_sla_instance(case.id, db)
                if not sla:
                    continue

                old_state = sla.sla_state
                new_state = compute_sla_state(sla, datetime.utcnow())

                if new_state != old_state:
                    sla.sla_state = new_state
                    sla.updated_at = datetime.utcnow()

                    # Log transition
                    log_audit(
                        db=db,
                        event_type=f"SLA_STATE_CHANGE",
                        case_id=case.id,
                        old_value=old_state,
                        new_value=new_state
                    )

                    # Trigger escalation if breached
                    if new_state == "BREACHED":
                        trigger_escalation(case, sla, "SLA_BREACH")

            db.commit()
        finally:
            db.close()
```

**IMPORTANT:** No Celery, Kafka, or Redis. Uses Python threading with a `daemon=True` thread. On SQLite, this is safe for single-instance deployment. For production multi-instance, use `BackgroundTasks` from FastAPI or external scheduler.

---

## 14. API STRUCTURE

### 14.1 Operational Endpoints

```
GET    /operations/cases
       ?domain=HOSTEL
       &status=AT_RISK
       &owner_id=5
       &sla_state=BREACHED
       &from_date=2026-10-01
       &to_date=2026-10-04
       &limit=50&offset=0

POST   /operations/cases
Body: {
  "domain": "HOSTEL",
  "service_type": "MAINTENANCE",
  "linked_entity_type": "Complaint",
  "linked_entity_id": 12,
  "priority": "P1",
  "requester_id": 42
}

GET    /operations/cases/{id}

POST   /operations/cases/{id}/acknowledge
       → Sets acknowledged_at, SLA clock stops for ack

POST   /operations/cases/{id}/transfer
Body: { "new_owner_id": 7, "reason": "Electrical issue → Electrical team" }

POST   /operations/cases/{id}/delegate
Body: { "delegate_id": 8, "start_time": "...", "end_time": "..." }

POST   /operations/cases/{id}/escalate
Body: { "reason": "MANUAL", "note": "Student waiting too long" }

POST   /operations/cases/{id}/complete
Body: { "note": "Fan motor replaced and tested" }

POST   /operations/cases/{id}/verify
Body: { "confirmed": true }  # true = resolved, false = reopen

POST   /operations/cases/{id}/reopen
Body: { "reason": "Problem recurred after 2 hours" }

POST   /operations/cases/{id}/request-info
Body: { "message": "Please upload photo of the fuse box" }

GET    /operations/incidents
POST   /operations/incidents/{id}/affected
       → Student clicks "I'm affected too"

GET    /operations/services/health
GET    /operations/metrics/pulse
GET    /operations/metrics/slo?service_type=GATE_PASS
GET    /operations/metrics/friction?domain=ADMIN
GET    /operations/metrics/student-time?period=week
GET    /operations/metrics/zero-chase
```

---

## 15. INTEGRATION WITH EXISTING MODULES

### 15.1 Complaint Flow (Extended)

```
Student submits complaint
        │
        ▼
ComplaintRoutingAgent classifies ──► Creates OperationalCase
        │                                    │
        │                           Links to Complaint.id
        │                                    │
        ▼                           Assigns current_owner
ComplaintRoutingAgent sets priority ◄────────│
        │                                    │
        ▼                           Creates SLAInstance
ComplaintRoutingAgent returns suggestion     │
                                           ▼
                               Submits with linked_entity_type="Complaint"
                                           │
                                           ▼
                               SLA clock starts (ack_due_at calculated)
                                           │
                                           ▼
                               Case visible in admin dashboard
                                           │
                                           ▼
                               Staff acknowledges ──► SLA ack clock stops
```

### 15.2 Gate Pass Flow (Extended)

```
Student requests gate pass
        │
        ▼
PolicyAgent returns approval chain
        │
        ▼
Creates OperationalCase with service_type="GATE_PASS"
        │
        ▼
Priority context check:
  - Student at physical gate? → P0
  - Regular request? → P2
        │
        ▼
Creates SLAInstance:
  - P0: ack=2min, action=5min, resolution=10min
        │
        ▼
HOD does not respond ──► 80% of 2min elapsed ──► AT_RISK
        │
        ▼
2min passes, no ack ──► BREACHED ──► Auto-escalate to Principal
        │
        ▼
Principal approves ──► Case RESOLVED
        │
        ▼
Security sees valid pass in system
```

### 15.3 Incident "I'm Affected Too"

```
Facilities receives water outage reports
        │
        ▼
Admin creates Incident: "Hostel C Water Supply Failure"
        │
        ▼
Students see banner on their dashboard:
  "Known water outage at Hostel C — 183 students affected"
  [ I'M AFFECTED TOO ]
        │
        ▼
Student clicks button ──► POST /operations/incidents/{id}/affected
        │
        ▼
IncidentMember created:
  - student_id = student.id
  - incident_id = incident.id
  - linked_case_id = student's complaint.id (if exists)
        │
        ▼
incident.affected_population += 1
        │
        ▼
If affected_population > threshold ──► Auto-escalate severity
```

---

## 16. FRONTEND INTEGRATION

### 16.1 Student Request Timeline (Reusable Component)

```jsx
// Reusable timeline for student request status
function StudentRequestTimeline({ caseId }) {
  const { data } = useSWR(`/operations/cases/${caseId}`);

  if (!data) return <LoadingSkeleton />;

  return (
    <div className="timeline">
      {data.audit_events.map(event => (
        <div key={event.id} className={`timeline-event ${event.event_type.toLowerCase()}`}>
          <div className="event-time">{formatTime(event.created_at)}</div>
          <div className="event-icon">{getIcon(event.event_type)}</div>
          <div className="event-content">
            <span className="event-action">{event.event_type.replace('_', ' ')}</span>
            {event.note && <p className="event-note">{event.note}</p>}
            <span className="event-actor">by {event.actor_name}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
```

### 16.2 Student Status Line

```jsx
// Instead of showing complex operational data, show simple status line
function StudentStatusLine({ operationalCase }) {
  const owner = operationalCase.current_owner;
  const elapsed = now() - operationalCase.ownership_assigned_at;

  if (operationalCase.status === 'RESOLVED') {
    return <span className="status-resolved">✓ Completed</span>;
  }

  return (
    <div className="student-status-line">
      <span className="status-label">
        {getStatusLabel(operationalCase.status)}
      </span>
      {owner && (
        <>
          <span className="separator">·</span>
          <span className="owner">
            {owner.role}
          </span>
          <span className="separator">·</span>
          <span className="wait-time">
            Waiting: {formatDuration(elapsed)}
          </span>
        </>
      )}
      {!operationalCase.sla_is_on_track && (
        <span className="sla-warning">
          Expected: {formatTime(operationalCase.sla_due_at)}
        </span>
      )}
    </div>
  );
}
```

### 16.3 Admin Campus Pulse Card

```jsx
function CampusPulseCard({ pulse }) {
  return (
    <div className="pulse-card">
      <div className="pulse-score" style={{ color: getPulseColor(pulse.overall) }}>
        {pulse.overall}/100
      </div>
      <div className="pulse-label">Campus Pulse</div>
      <div className="domain-bars">
        {Object.entries(pulse.domains).map(([domain, score]) => (
          <div key={domain} className="domain-bar">
            <span>{domain}</span>
            <div className="bar-bg">
              <div
                className="bar-fill"
                style={{ width: `${score}%`, backgroundColor: getPulseColor(score) }}
              />
            </div>
            <span>{score}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 17. MIGRATION STRATEGY

### 17.1 Phase 1 Migration (Zero-Downtime)

```python
# Add nullable columns to existing tables (backwards-compatible)
ALTER TABLE complaints ADD COLUMN operational_case_id INTEGER REFERENCES operational_cases(id);
ALTER TABLE complaints ADD COLUMN current_owner_id INTEGER REFERENCES users(id);
ALTER TABLE complaints ADD COLUMN sla_instance_id INTEGER REFERENCES sla_instances(id);
ALTER TABLE complaints ADD COLUMN blast_scope VARCHAR(20);
ALTER TABLE complaints ADD COLUMN affected_count INTEGER DEFAULT 1;

ALTER TABLE gate_passes ADD COLUMN operational_case_id INTEGER REFERENCES operational_cases(id);
ALTER TABLE gate_passes ADD COLUMN context_urgency VARCHAR(20);
```

### 17.2 Data Backfill

```python
def backfill_operational_cases():
    """One-time backfill of existing records."""
    db = SessionLocal()
    try:
        # Create OperationalCase for each existing Complaint
        for complaint in db.query(Complaint).all():
            if not complaint.operational_case_id:
                case = OperationalCase(
                    domain="HOSTEL",  # Default for maintenance
                    service_type="MAINTENANCE",
                    requester_id=complaint.student_id,
                    current_owner_id=complaint.assigned_to,
                    priority=map_priority(complaint.priority),
                    status=map_status(complaint.status),
                    linked_entity_type="Complaint",
                    linked_entity_id=complaint.id,
                    created_at=complaint.created_at,
                    estimated_affected=1
                )
                db.add(case)
                db.flush()

                complaint.operational_case_id = case.id
                complaint.current_owner_id = complaint.assigned_to

        db.commit()
    finally:
        db.close()
```

---

## 18. CONCURRENCY SAFETY

```python
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

def safe_state_transition(db: Session, case_id: int, from_status: str, to_status: str):
    """
    Uses SELECT FOR UPDATE to prevent race conditions.
    Only one thread/process can transition a case at a time.
    """
    try:
        case = db.query(OperationalCase).filter(
            OperationalCase.id == case_id
        ).with_for_update().first()

        if case is None:
            raise ValueError(f"Case {case_id} not found")

        if case.status != from_status:
            raise ValueError(
                f"Cannot transition: expected status={from_status}, actual={case.status}"
            )

        case.status = to_status
        db.commit()
        return case

    except OperationalError as e:
        db.rollback()
        raise ConcurrencyError(f"Case {case_id} is being modified by another process")
```

---

## 19. RELATIONSHIP TO EXISTING AGENTS

| Existing Agent | Extended Role |
|----------------|---------------|
| `ComplaintRoutingAgent` | Calls `PriorityEngine.calculate()` before returning suggestion |
| `PolicyAgent` | Extended to load SLA/escalation policies from DB instead of Python dict |
| `PatternMemoryAgent` | Results linked to `Incident` + `Asset` for institutional memory |

The operational engine does NOT replace existing agents. It provides infrastructure they can leverage.

---

## 20. WHAT REMAINS UNCHANGED

- All existing `POST /api/student/*` endpoints work identically
- All existing `GET /api/staff/*` endpoints work identically
- All existing `GET /api/admin/*` endpoints work identically
- Database schema for existing tables unchanged (only additions)
- Frontend components for student/staff/admin portals unchanged for Phase 1
- Authentication and RBAC unchanged
- Seed data unchanged

The operational layer is an **overlay** that enhances without disrupting.
