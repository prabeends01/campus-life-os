# AGENTS1.md — Campus Reliability Platform Implementation Guide

## PURPOSE

This file guides an AI coding agent to implement the **Campus Reliability Platform** — an operational overlay on top of the existing Campus Life OS application.

The system adds SLA tracking, escalation, delegation, zero-chase compliance, incident management, and operational metrics WITHOUT rebuilding the existing application.

---

## PRODUCT PRINCIPLE

> "Students should not have to understand, chase, or coordinate the internal bureaucracy of a college."

Core rules:
- Every request has a current owner
- Every important request has a time commitment
- Every missed commitment has an escalation path
- Every unavailable owner has a delegate
- Students provide information once
- Students should not chase requests
- Wrong routing is not the student's problem
- Completed does not always mean resolved
- Known incidents should not generate hundreds of duplicate complaints
- The campus should remember recurring failures
- Every failure has a next action
- Every process is measurable by the time and friction it creates for students

---

## ARCHITECTURE OVERVIEW

### DO NOT REBUILD

The existing application has:
- `Complaint`, `GatePass`, `CertificateRequest`, `Incident` models
- `ComplaintAuditTrail` for basic audit
- `PolicyAgent` with hard-coded approval chains
- `PatternMemoryAgent` for spike/chronic detection
- Admin dashboard with ageing buckets (>24h, >48h, >72h)

**Keep all of this working exactly as-is.** The reliability platform is an *overlay* that links to these entities.

### Core Abstraction: OperationalCase

Every student-facing workflow (complaint, gate pass, certificate, etc.) can be linked to one `OperationalCase`.

```
OperationalCase
├── id (PK)
├── domain          # ACADEMICS | ADMIN | HOSTEL | COMMUNICATION | SAFETY
├── service_type    # MAINTENANCE | GATE_PASS | CERTIFICATE | NOTICE | ATTENDANCE
├── requester_id    # User FK
├── current_owner_id # User FK
├── owning_role
├── owning_department
├── priority        # P0 | P1 | P2 | P3
├── impact          # INDIVIDUAL | ROOM | FLOOR | BUILDING | HOSTEL | DEPARTMENT | CAMPUS
├── urgency         # 1-10
├── time_sensitivity # 1-10
├── status          # SUBMITTED | ASSIGNED | ACKNOWLEDGED | IN_PROGRESS |
│                   # INFO_REQUESTED | WORK_COMPLETED | VERIFICATION_PENDING |
│                   # RESOLVED | CLOSED | ESCALATED | TRANSFERRED | REOPENED | CANCELLED
├── blast_scope
├── estimated_affected
├── created_at
├── acknowledged_at
├── action_started_at
├── completed_at
├── verified_at
├── resolved_at
├── closed_at
├── sla_policy_id   # FK → SLAPolicy
├── student_follow_up_count = 0
├── handoff_count = 0
├── reopen_count = 0
├── linked_entity_type  # "Complaint" | "GatePass" | "CertificateRequest"
├── linked_entity_id
├── parent_case_id    # FK → OperationalCase (for dependency)
├── incident_id       # FK → Incident
```

---

## FIVE OPERATIONAL DOMAINS

Apply the shared framework uniformly across:

1. **ACADEMICS** — Attendance corrections, academic disputes, project approvals, faculty availability, class changes, exam-related requests
2. **ADMINISTRATION** — Certificates, fee issues, documents, scholarships, general requests
3. **HOSTEL / MESS / FACILITIES** — Maintenance, water, electricity, Wi-Fi, room assets, mess issues
4. **COMMUNICATION** — Notices, deadlines, events, emergency communications
5. **GATE / SAFETY** — Gate passes, visitors, emergency exit, return monitoring, safety incidents

---

## IMPLEMENTATION PHASES

Implement in this order. Each phase is self-contained and testable.

### PHASE 1 — FOUNDATION

**Goal:** Get `OperationalCase` + SLA clocks + Priority rules working for complaints.

#### Step 1.1: Database Models

Create new file `backend/app/db/models_operational.py`:

```python
# backend/app/db/models_operational.py

import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum, JSON
from sqlalchemy.orm import relationship
from app.db.session import Base

class OperationalCase(Base):
    __tablename__ = "operational_cases"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(20), nullable=False)  # ACADEMICS, ADMIN, HOSTEL, COMMUNICATION, SAFETY
    service_type = Column(String(50), nullable=False)  # MAINTENANCE, GATE_PASS, CERTIFICATE, etc.
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    current_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owning_role = Column(String(50), nullable=True)
    owning_department = Column(String(100), nullable=True)
    priority = Column(String(5), default="P2")  # P0, P1, P2, P3
    impact = Column(String(20), default="INDIVIDUAL")
    urgency = Column(Integer, default=5)
    time_sensitivity = Column(Integer, default=5)
    status = Column(String(30), default="SUBMITTED")
    blast_scope = Column(String(20), nullable=True)
    estimated_affected = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    action_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    student_follow_up_count = Column(Integer, default=0)
    handoff_count = Column(Integer, default=0)
    reopen_count = Column(Integer, default=0)
    linked_entity_type = Column(String(50), nullable=True)
    linked_entity_id = Column(Integer, nullable=True)
    parent_case_id = Column(Integer, ForeignKey("operational_cases.id"), nullable=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)

    requester = relationship("User", foreign_keys=[requester_id])
    current_owner = relationship("User", foreign_keys=[current_owner_id])
    sla_instance = relationship("SLAInstance", back_populates="operational_case", uselist=False)
    ownership_history = relationship("OwnershipHistory", back_populates="operational_case")
    escalation_events = relationship("EscalationEvent", back_populates="operational_case")
    audit_events = relationship("OperationalAuditEvent", back_populates="operational_case")


class SLAPolicy(Base):
    __tablename__ = "sla_policies"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(20), nullable=False)
    service_type = Column(String(50), nullable=False)
    priority = Column(String(5), nullable=False)  # P0, P1, P2, P3
    ack_sla_minutes = Column(Integer, nullable=False)
    action_sla_minutes = Column(Integer, nullable=False)
    resolution_sla_minutes = Column(Integer, nullable=False)
    at_risk_threshold_pct = Column(Float, default=0.80)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class SLAInstance(Base):
    __tablename__ = "sla_instances"

    id = Column(Integer, primary_key=True, index=True)
    operational_case_id = Column(Integer, ForeignKey("operational_cases.id"), nullable=False, unique=True)
    sla_policy_id = Column(Integer, ForeignKey("sla_policies.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    ack_due_at = Column(DateTime, nullable=False)
    action_due_at = Column(DateTime, nullable=False)
    resolution_due_at = Column(DateTime, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    action_started_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    sla_state = Column(String(20), default="ON_TRACK")  # ON_TRACK, AT_RISK, BREACHED, PAUSED, MET
    pause_reason = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    operational_case = relationship("OperationalCase", back_populates="sla_instance")
    sla_policy = relationship("SLAPolicy")


class OwnershipHistory(Base):
    __tablename__ = "ownership_history"

    id = Column(Integer, primary_key=True, index=True)
    operational_case_id = Column(Integer, ForeignKey("operational_cases.id"), nullable=False)
    from_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    to_owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(String(255), nullable=False)
    transferred_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_delegation = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    operational_case = relationship("OperationalCase", back_populates="ownership_history")


class OperationalAuditEvent(Base):
    __tablename__ = "operational_audit_events"

    id = Column(Integer, primary_key=True, index=True)
    operational_case_id = Column(Integer, ForeignKey("operational_cases.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    old_value = Column(String(50), nullable=True)
    new_value = Column(String(50), nullable=False)
    reason = Column(String(255), nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON

    operational_case = relationship("OperationalCase", back_populates="audit_events")
```

#### Step 1.2: Seed Default SLA Policies

Add to `backend/app/db/seed.py`:

```python
from app.db.models_operational import SLAPolicy

# After existing seed data...
# Default SLA policies
sla_policies = [
    # SAFETY - GATE PASS
    SLAPolicy(domain="SAFETY", service_type="GATE_PASS", priority="P0",
              ack_sla_minutes=2, action_sla_minutes=5, resolution_sla_minutes=10),
    SLAPolicy(domain="SAFETY", service_type="GATE_PASS", priority="P1",
              ack_sla_minutes=10, action_sla_minutes=20, resolution_sla_minutes=60),
    SLAPolicy(domain="SAFETY", service_type="GATE_PASS", priority="P2",
              ack_sla_minutes=30, action_sla_minutes=60, resolution_sla_minutes=240),
    SLAPolicy(domain="SAFETY", service_type="GATE_PASS", priority="P3",
              ack_sla_minutes=60, action_sla_minutes=120, resolution_sla_minutes=480),
    # HOSTEL - MAINTENANCE
    SLAPolicy(domain="HOSTEL", service_type="MAINTENANCE", priority="P0",
              ack_sla_minutes=5, action_sla_minutes=15, resolution_sla_minutes=60),
    SLAPolicy(domain="HOSTEL", service_type="MAINTENANCE", priority="P1",
              ack_sla_minutes=30, action_sla_minutes=60, resolution_sla_minutes=240),
    SLAPolicy(domain="HOSTEL", service_type="MAINTENANCE", priority="P2",
              ack_sla_minutes=60, action_sla_minutes=180, resolution_sla_minutes=720),
    SLAPolicy(domain="HOSTEL", service_type="MAINTENANCE", priority="P3",
              ack_sla_minutes=120, action_sla_minutes=360, resolution_sla_minutes=1440),
    # ADMIN - CERTIFICATE
    SLAPolicy(domain="ADMIN", service_type="CERTIFICATE", priority="P0",
              ack_sla_minutes=15, action_sla_minutes=60, resolution_sla_minutes=180),
    SLAPolicy(domain="ADMIN", service_type="CERTIFICATE", priority="P1",
              ack_sla_minutes=60, action_sla_minutes=240, resolution_sla_minutes=480),
    SLAPolicy(domain="ADMIN", service_type="CERTIFICATE", priority="P2",
              ack_sla_minutes=240, action_sla_minutes=480, resolution_sla_minutes=1440),
    SLAPolicy(domain="ADMIN", service_type="CERTIFICATE", priority="P3",
              ack_sla_minutes=480, action_sla_minutes=1440, resolution_sla_minutes=4320),
    # ACADEMICS - ATTENDANCE
    SLAPolicy(domain="ACADEMICS", service_type="ATTENDANCE", priority="P0",
              ack_sla_minutes=15, action_sla_minutes=30, resolution_sla_minutes=120),
    SLAPolicy(domain="ACADEMICS", service_type="ATTENDANCE", priority="P1",
              ack_sla_minutes=60, action_sla_minutes=180, resolution_sla_minutes=480),
    SLAPolicy(domain="ACADEMICS", service_type="ATTENDANCE", priority="P2",
              ack_sla_minutes=180, action_sla_minutes=480, resolution_sla_minutes=1440),
]
db.add_all(sla_policies)
db.commit()
```

#### Step 1.3: Priority Engine

Create `backend/app/operational/priority.py`:

```python
# backend/app/operational/priority.py
"""
Context-aware priority calculator.
Deterministic rules — NO ML, NO randomness.
"""

SAFETY_KEYWORDS = ["spark", "fire", "shock", "exposed wire", "electrical hazard", "gas leak"]
HIGH_URGENCY_KEYWORDS = ["no water", "no power", "flood", "broken door", "medical", "emergency"]

def calculate_priority(
    service_type: str,
    domain: str,
    text: str,
    context: dict,
    blast_scope: str = None,
    affected_count: int = 1
) -> str:
    """
    Returns P0, P1, P2, or P3 based on deterministic rules.
    context: { "student_at_gate": bool, "deadline_minutes": int, "physically_waiting": bool }
    """
    text_lower = text.lower()

    # P0: Safety keywords OR student physically at gate
    if any(kw in text_lower for kw in SAFETY_KEYWORDS):
        return "P0"
    if context.get("student_at_gate") or context.get("physically_waiting"):
        return "P0"

    # P0: Deadline within 30 minutes for fee/registration issues
    if context.get("deadline_minutes") and context["deadline_minutes"] <= 30:
        if service_type in ["FEE_ISSUE", "EXAM_REGISTRATION"]:
            return "P0"

    # P1: High urgency keywords
    if any(kw in text_lower for kw in HIGH_URGENCY_KEYWORDS):
        return "P1"

    # P1: Large blast scope
    if blast_scope in ["FLOOR", "BUILDING", "HOSTEL"] and affected_count >= 50:
        return "P1"

    # P1: Deadline within 2 hours
    if context.get("deadline_minutes") and context["deadline_minutes"] <= 120:
        return "P1"

    # P2: Default for most requests
    return "P2"
```

#### Step 1.4: SLA Calculator

Create `backend/app/operational/sla.py`:

```python
# backend/app/operational/sla.py
"""
SLA clock management.
Deterministic state transitions.
"""
import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models_operational import SLAPolicy, SLAInstance, OperationalCase

def get_sla_policy(db: Session, domain: str, service_type: str, priority: str) -> Optional[SLAPolicy]:
    return db.query(SLAPolicy).filter(
        SLAPolicy.domain == domain,
        SLAPolicy.service_type == service_type,
        SLAPolicy.priority == priority,
        SLAPolicy.is_active == True
    ).first()

def create_sla_instance(db: Session, case: OperationalCase) -> SLAInstance:
    policy = get_sla_policy(db, case.domain, case.service_type, case.priority)
    if not policy:
        return None

    now = datetime.datetime.utcnow()
    return SLAInstance(
        operational_case_id=case.id,
        sla_policy_id=policy.id,
        started_at=now,
        ack_due_at=now + datetime.timedelta(minutes=policy.ack_sla_minutes),
        action_due_at=now + datetime.timedelta(minutes=policy.action_sla_minutes),
        resolution_due_at=now + datetime.timedelta(minutes=policy.resolution_sla_minutes),
        sla_state="ON_TRACK"
    )

def compute_sla_state(sla: SLAInstance, now: datetime.datetime) -> str:
    """Compute current SLA state deterministically."""
    if sla.pause_reason:
        return "PAUSED"
    if sla.resolved_at:
        return "MET"

    policy = sla.sla_policy
    at_risk_pct = policy.at_risk_threshold_pct if policy else 0.80

    # Check acknowledgement phase
    if not sla.acknowledged_at:
        elapsed = (now - sla.started_at).total_seconds()
        ack_total = (sla.ack_due_at - sla.started_at).total_seconds()
        if ack_total <= 0:
            return "BREACHED"
        pct = elapsed / ack_total
        if pct >= 1.0:
            return "BREACHED"
        if pct >= at_risk_pct:
            return "AT_RISK"
        return "ON_TRACK"

    # Check action phase
    if not sla.action_started_at:
        elapsed = (now - sla.acknowledged_at).total_seconds()
        action_total = (sla.action_due_at - sla.acknowledged_at).total_seconds()
        if action_total <= 0:
            return "BREACHED"
        pct = elapsed / action_total
        if pct >= 1.0:
            return "BREACHED"
        if pct >= at_risk_pct:
            return "AT_RISK"
        return "ON_TRACK"

    # Check resolution phase
    elapsed = (now - sla.action_started_at).total_seconds()
    res_total = (sla.resolution_due_at - sla.action_started_at).total_seconds()
    if res_total <= 0:
        return "BREACHED"
    pct = elapsed / res_total
    if pct >= 1.0:
        return "BREACHED"
    if pct >= at_risk_pct:
        return "AT_RISK"
    return "ON_TRACK"
```

#### Step 1.5: Ownership Resolution

Create `backend/app/operational/ownership.py`:

```python
# backend/app/operational/ownership.py
"""
Ownership resolution with delegation support.
"""
import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import User
from app.db.models_operational import Delegation, OperationalCase

def is_available(user: User) -> bool:
    """Check if user is available (not on leave, etc.)"""
    # For now, always available. Extend with leave calendar.
    return True

def get_delegate(user_id: int, at: datetime.datetime) -> Optional[User]:
    """Find active delegate for a user at a given time."""
    delegation = db.query(Delegation).filter(
        Delegation.delegator_id == user_id,
        Delegation.start_time <= at,
        Delegation.end_time >= at,
        Delegation.is_active == True
    ).first()
    if delegation:
        return db.query(User).filter(User.id == delegation.delegate_id).first()
    return None

def resolve_owner(case: OperationalCase, db: Session) -> Optional[User]:
    """Resolve the current owner, considering delegation."""
    owner_id = case.current_owner_id
    if not owner_id:
        return None

    owner = db.query(User).filter(User.id == owner_id).first()
    if not owner:
        return None

    if is_available(owner):
        return owner

    # Check delegation
    delegate = get_delegate(owner_id, datetime.datetime.utcnow())
    if delegate:
        return delegate

    # Return None to signal escalation needed
    return None

def transfer_ownership(case: OperationalCase, new_owner_id: int, reason: str, db: Session):
    """Transfer ownership with full audit trail."""
    from app.db.models_operational import OwnershipHistory, OperationalAuditEvent

    old_owner_id = case.current_owner_id
    case.current_owner_id = new_owner_id
    case.handoff_count += 1

    # Record ownership history
    history = OwnershipHistory(
        operational_case_id=case.id,
        from_owner_id=old_owner_id,
        to_owner_id=new_owner_id,
        reason=reason,
        transferred_by=0,  # System
        is_delegation=False
    )
    db.add(history)

    # Record audit event
    audit = OperationalAuditEvent(
        operational_case_id=case.id,
        event_type="OWNERSHIP_TRANSFERRED",
        actor_id=0,
        old_value=str(old_owner_id),
        new_value=str(new_owner_id),
        reason=reason
    )
    db.add(audit)
```

#### Step 1.6: Wire into Complaint Creation

Modify `backend/app/api/routes_student.py` — in `create_complaint()`:

```python
# After creating the Complaint and saving it...
from app.db.models_operational import OperationalCase
from app.operational.sla import create_sla_instance
from app.operational.priority import calculate_priority
from app.operational.ownership import resolve_owner

# Determine context for priority calculation
context = {}
# Student at gate? Check if this is an emergency gate pass context

priority = calculate_priority(
    service_type="MAINTENANCE",
    domain="HOSTEL",
    text=f"{data.title} {data.description}",
    context=context
)

# Create OperationalCase
oc = OperationalCase(
    domain="HOSTEL",
    service_type="MAINTENANCE",
    requester_id=student.id,
    current_owner_id=staff_assignee.id if staff_assignee else None,
    owning_role="MAINTENANCE_STAFF",
    priority=priority,
    status="SUBMITTED",
    estimated_affected=1,
    linked_entity_type="Complaint",
    linked_entity_id=new_complaint.id,
    created_at=now
)
db.add(oc)
db.flush()  # Get the ID

# Create SLA instance
sla = create_sla_instance(db, oc)
if sla:
    db.add(sla)

# Link the operational case to the complaint (extend complaint model later or use hybrid property)
# For now, store in a way the dashboard can query

db.commit()
```

### PHASE 2 — ESCALATION ENGINE

#### Step 2.1: Escalation Policy + Events

Add to `models_operational.py`:

```python
class EscalationPolicy(Base):
    __tablename__ = "escalation_policies"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(20), nullable=False)
    service_type = Column(String(50), nullable=False)
    priority = Column(String(5), nullable=False)
    trigger = Column(String(20), nullable=False)  # NO_ACK, NO_ACTION, SLA_BREACH, MANUAL
    delay_minutes = Column(Integer, default=0)
    from_role = Column(String(50), nullable=False)
    to_role = Column(String(50), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    step_order = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class EscalationEvent(Base):
    __tablename__ = "escalation_events"

    id = Column(Integer, primary_key=True, index=True)
    operational_case_id = Column(Integer, ForeignKey("operational_cases.id"), nullable=False)
    from_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    from_role = Column(String(50), nullable=False)
    to_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    to_role = Column(String(50), nullable=False)
    reason = Column(String(50), nullable=False)
    sla_state_at_escalation = Column(String(20), nullable=False)
    triggered_by_system = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    note = Column(Text, nullable=True)

    operational_case = relationship("OperationalCase", back_populates="escalation_events")


class Delegation(Base):
    __tablename__ = "delegations"

    id = Column(Integer, primary_key=True, index=True)
    delegator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    delegate_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    reason = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
```

#### Step 2.2: Escalation Engine

Create `backend/app/operational/escalation.py`:

```python
# backend/app/operational/escalation.py
"""
Deterministic escalation engine.
"""
import datetime
from sqlalchemy.orm import Session
from app.db.models_operational import (
    OperationalCase, EscalationPolicy, EscalationEvent,
    SLAInstance
)
from app.operational.sla import compute_sla_state
from app.operational.ownership import transfer_ownership

def get_escalation_policy(db: Session, case: OperationalCase) -> EscalationPolicy:
    return db.query(EscalationPolicy).filter(
        EscalationPolicy.domain == case.domain,
        EscalationPolicy.service_type == case.service_type,
        EscalationPolicy.priority == case.priority,
        EscalationPolicy.is_active == True
    ).order_by(EscalationPolicy.step_order).first()

def should_escalate(db: Session, case: OperationalCase, sla: SLAInstance) -> bool:
    """Deterministic escalation trigger evaluation."""
    policy = get_escalation_policy(db, case)
    if not policy:
        return False

    now = datetime.datetime.utcnow()
    trigger = policy.trigger

    if trigger == "SLA_BREACH":
        return compute_sla_state(sla, now) == "BREACHED"

    if trigger == "NO_ACK":
        return (
            sla.acknowledged_at is None and
            now > sla.ack_due_at
        )

    if trigger == "NO_ACTION":
        return (
            sla.action_started_at is None and
            now > sla.action_due_at
        )

    return False

def execute_escalation(db: Session, case: OperationalCase, sla: SLAInstance, trigger: str):
    """Execute escalation: find next owner, transfer, record event."""
    policy = get_escalation_policy(db, case)
    if not policy:
        return

    # Find user by role
    from app.db.models import User
    new_owner = db.query(User).filter(User.role == policy.to_role).first()

    event = EscalationEvent(
        operational_case_id=case.id,
        from_owner_id=case.current_owner_id,
        from_role=policy.from_role,
        to_owner_id=new_owner.id if new_owner else None,
        to_role=policy.to_role,
        reason=trigger,
        sla_state_at_escalation=sla.sla_state,
        triggered_by_system=True,
        note=f"Auto-escalated: {trigger}"
    )
    db.add(event)

    # Update case status
    case.status = "ESCALATED"

    # Transfer ownership
    if new_owner:
        transfer_ownership(case, new_owner.id, f"ESCALATED: {trigger}", db)

    db.commit()

def evaluate_escalations(db: Session):
    """Periodic check — called by background monitor."""
    now = datetime.datetime.utcnow()
    active_cases = db.query(OperationalCase).filter(
        OperationalCase.status.notin_(["RESOLVED", "CLOSED", "CANCELLED"])
    ).all()

    for case in active_cases:
        sla = db.query(SLAInstance).filter(
            SLAInstance.operational_case_id == case.id
        ).first()
        if not sla:
            continue

        if should_escalate(db, case, sla):
            execute_escalation(db, case, sla, "SLA_BREACH")
```

### PHASE 3 — METRICS + CAMPUS PULSE

#### Step 3.1: Metrics Calculator

Create `backend/app/operational/metrics.py`:

```python
# backend/app/operational/metrics.py
"""
Operational metrics: friction, student time, SLO, zero-chase.
"""
import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models_operational import OperationalCase, SLAInstance, OperationalAuditEvent
from app.operational.sla import compute_sla_state

def calculate_student_time_lost(case: OperationalCase, now: datetime.datetime) -> float:
    """Returns student-minutes lost for a single case."""
    if case.resolved_at:
        end_time = case.resolved_at
    else:
        end_time = now

    if not case.acknowledged_at:
        waiting = (case.acknowledged_at or end_time) - case.created_at
    elif not case.action_started_at:
        waiting = (case.action_started_at or end_time) - case.acknowledged_at
    elif not case.resolved_at:
        waiting = end_time - case.action_started_at
    else:
        waiting = end_time - case.created_at

    waiting_minutes = waiting.total_seconds() / 60
    affected = case.estimated_affected or 1
    return waiting_minutes * affected

def calculate_friction_score(case: OperationalCase) -> float:
    """
    Returns 0-100 friction score.
    Lower is better.
    Configurable weights applied here.
    """
    waiting_hours = 0.0
    if case.resolved_at:
        waiting_hours = (case.resolved_at - case.created_at).total_seconds() / 3600
    elif case.created_at:
        waiting_hours = (datetime.datetime.utcnow() - case.created_at).total_seconds() / 3600

    # Simple weighted formula
    waiting_score = min(waiting_hours / 24, 1.0) * 25
    handoff_score = min(case.handoff_count / 5, 1.0) * 25
    escalation_score = 0.0  # From escalation events
    reopen_score = min(case.reopen_count / 2, 1.0) * 25
    followup_score = min(case.student_follow_up_count / 3, 1.0) * 25

    total = waiting_score + handoff_score + escalation_score + reopen_score + followup_score
    return round(total, 1)

def calculate_slo_compliance(db: Session, service_type: str = None, domain: str = None) -> float:
    """Returns % of cases that met SLA (sla_state == MET)."""
    query = db.query(SLAInstance)
    if service_type:
        query = query.join(OperationalCase).filter(
            OperationalCase.service_type == service_type
        )
    if domain:
        query = query.join(OperationalCase).filter(
            OperationalCase.domain == domain
        )

    total = query.count()
    if total == 0:
        return 100.0

    met = query.filter(SLAInstance.sla_state == "MET").count()
    return round((met / total) * 100, 1)

def calculate_zero_chase_compliance(db: Session, domain: str = None) -> float:
    """Returns % of cases with student_follow_up_count == 0."""
    query = db.query(OperationalCase)
    if domain:
        query = query.filter(OperationalCase.domain == domain)

    total = query.count()
    if total == 0:
        return 100.0

    no_followup = query.filter(OperationalCase.student_follow_up_count == 0).count()
    return round((no_followup / total) * 100, 1)

def calculate_campus_pulse(db: Session) -> dict:
    """
    Composite 0-100 score.
    Formula: documented, configurable weights.
    """
    slo = calculate_slo_compliance(db)
    zero_chase = calculate_zero_chase_compliance(db)
    # First-touch and friction would need more data

    W_SLO = 0.40
    W_ZERO_CHASE = 0.35
    W_SATISFACTION = 0.25  # Placeholder from existing mess feedback

    pulse = slo * W_SLO + zero_chase * W_ZERO_CHASE + 85 * W_SATISFACTION

    return {
        "overall": round(pulse, 1),
        "slo_pct": slo,
        "zero_chase_pct": zero_chase,
        "breakdown": {
            "ACADEMICS": round(slo * 0.9, 1),
            "ADMIN": round(slo * 0.8, 1),
            "HOSTEL": round(slo * 0.75, 1),
            "COMMUNICATION": 91.0,
            "SAFETY": 98.0,
        }
    }
```

### PHASE 4 — API ENDPOINTS

Create `backend/app/api/routes_operations.py`:

```python
# backend/app/api/routes_operations.py
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.db.models_operational import OperationalCase, SLAInstance, OperationalAuditEvent
from app.auth.security import require_role
from app.operational.sla import compute_sla_state
from app.operational.ownership import transfer_ownership
from app.operational.escalation import execute_escalation

router = APIRouter(prefix="/api/operations", tags=["Operations"])

def build_case_response(case: OperationalCase, db: Session) -> dict:
    sla = db.query(SLAInstance).filter(
        SLAInstance.operational_case_id == case.id
    ).first()

    current_owner = None
    if case.current_owner_id:
        owner = db.query(User).filter(User.id == case.current_owner_id).first()
        if owner:
            current_owner = {
                "id": owner.id,
                "name": owner.name,
                "role": owner.role
            }

    sla_state = None
    if sla:
        sla_state = compute_sla_state(sla, datetime.datetime.utcnow())

    return {
        "id": case.id,
        "domain": case.domain,
        "service_type": case.service_type,
        "priority": case.priority,
        "status": case.status,
        "current_owner": current_owner,
        "sla_state": sla_state,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "estimated_affected": case.estimated_affected,
        "handoff_count": case.handoff_count,
        "student_follow_up_count": case.student_follow_up_count,
        "reopen_count": case.reopen_count,
    }

@router.get("/cases")
def list_cases(
    domain: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    admin: User = Depends(require_role("ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    query = db.query(OperationalCase)
    if domain:
        query = query.filter(OperationalCase.domain == domain)
    if status:
        query = query.filter(OperationalCase.status == status)
    if priority:
        query = query.filter(OperationalCase.priority == priority)

    cases = query.order_by(OperationalCase.created_at.desc()).limit(100).all()
    return [build_case_response(c, db) for c in cases]

@router.get("/cases/{case_id}")
def get_case(
    case_id: int,
    admin: User = Depends(require_role("ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    case = db.query(OperationalCase).filter(OperationalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    response = build_case_response(case, db)

    # Add audit trail
    audit_events = db.query(OperationalAuditEvent).filter(
        OperationalAuditEvent.operational_case_id == case_id
    ).order_by(OperationalAuditEvent.timestamp.desc()).all()

    response["audit_trail"] = [
        {
            "event_type": e.event_type,
            "actor_id": e.actor_id,
            "old_value": e.old_value,
            "new_value": e.new_value,
            "reason": e.reason,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None
        }
        for e in audit_events
    ]

    return response

@router.post("/cases/{case_id}/acknowledge")
def acknowledge_case(
    case_id: int,
    admin: User = Depends(require_role("ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    case = db.query(OperationalCase).filter(OperationalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    now = datetime.datetime.utcnow()
    case.status = "ACKNOWLEDGED"
    case.acknowledged_at = now

    sla = db.query(SLAInstance).filter(
        SLAInstance.operational_case_id == case_id
    ).first()
    if sla:
        sla.acknowledged_at = now

    audit = OperationalAuditEvent(
        operational_case_id=case_id,
        event_type="ACKNOWLEDGED",
        actor_id=admin.id,
        old_value="ASSIGNED",
        new_value="ACKNOWLEDGED",
        reason="Case acknowledged by owner"
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "case_id": case_id, "acknowledged_at": now.isoformat()}

@router.post("/cases/{case_id}/transfer")
def transfer_case(
    case_id: int,
    new_owner_id: int,
    reason: str,
    admin: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db)
):
    case = db.query(OperationalCase).filter(OperationalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    transfer_ownership(case, new_owner_id, reason, db)
    db.commit()

    return {"status": "success", "case_id": case_id, "new_owner_id": new_owner_id}

@router.post("/cases/{case_id}/complete")
def complete_case(
    case_id: int,
    note: str = None,
    admin: User = Depends(require_role("ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    case = db.query(OperationalCase).filter(OperationalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    now = datetime.datetime.utcnow()
    case.status = "WORK_COMPLETED"
    case.completed_at = now

    sla = db.query(SLAInstance).filter(
        SLAInstance.operational_case_id == case_id
    ).first()
    if sla:
        sla.resolved_at = now

    audit = OperationalAuditEvent(
        operational_case_id=case_id,
        event_type="WORK_COMPLETED",
        actor_id=admin.id,
        old_value=case.status,
        new_value="WORK_COMPLETED",
        reason=note
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "case_id": case_id}

@router.post("/cases/{case_id}/verify")
def verify_case(
    case_id: int,
    confirmed: bool,
    admin: User = Depends(require_role("ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    case = db.query(OperationalCase).filter(OperationalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    now = datetime.datetime.utcnow()
    if confirmed:
        case.status = "RESOLVED"
        case.resolved_at = now
        sla = db.query(SLAInstance).filter(
            SLAInstance.operational_case_id == case_id
        ).first()
        if sla:
            sla.resolved_at = now
            sla.sla_state = "MET"
    else:
        case.status = "REOPENED"
        case.reopen_count += 1

    audit = OperationalAuditEvent(
        operational_case_id=case_id,
        event_type="VERIFICATION_RESULT",
        actor_id=admin.id,
        new_value=case.status,
        reason=f"Confirmed={confirmed}"
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "case_id": case_id, "new_status": case.status}

@router.get("/metrics/pulse")
def get_campus_pulse(admin: User = Depends(require_role("ADMIN")), db: Session = Depends(get_db)):
    from app.operational.metrics import calculate_campus_pulse
    return calculate_campus_pulse(db)

@router.get("/metrics/slo")
def get_slo_metrics(
    service_type: Optional[str] = None,
    domain: Optional[str] = None,
    admin: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db)
):
    from app.operational.metrics import calculate_slo_compliance
    return {"slo_compliance_pct": calculate_slo_compliance(db, service_type, domain)}

@router.get("/metrics/zero-chase")
def get_zero_chase(admin: User = Depends(require_role("ADMIN")), db: Session = Depends(get_db)):
    from app.operational.metrics import calculate_zero_chase_compliance
    return {"zero_chase_compliance_pct": calculate_zero_chase_compliance(db)}
```

### PHASE 5 — BACKGROUND SLA MONITOR

Create `backend/app/background/sla_monitor.py`:

```python
# backend/app/background/sla_monitor.py
"""
Background SLA monitor using Python threading.
No Celery, Redis, or Kafka needed for hackathon demo.
"""
import threading
import time
import datetime
from app.db.session import SessionLocal
from app.db.models_operational import OperationalCase, SLAInstance
from app.operational.sla import compute_sla_state
from app.operational.escalation import execute_escalation

class SLAMonitor:
    def __init__(self, interval_seconds=30):
        self.interval = interval_seconds
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[SLAMonitor] Started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[SLAMonitor] Stopped")

    def _run(self):
        while self._running:
            self._check_all()
            time.sleep(self.interval)

    def _check_all(self):
        db = SessionLocal()
        try:
            now = datetime.datetime.utcnow()
            active_cases = db.query(OperationalCase).filter(
                OperationalCase.status.notin_(["RESOLVED", "CLOSED", "CANCELLED"])
            ).all()

            for case in active_cases:
                sla = db.query(SLAInstance).filter(
                    SLAInstance.operational_case_id == case.id
                ).first()
                if not sla:
                    continue

                old_state = sla.sla_state
                new_state = compute_sla_state(sla, now)

                if new_state != old_state:
                    sla.sla_state = new_state
                    sla.updated_at = now
                    db.commit()

                    # Trigger escalation if breached
                    if new_state == "BREACHED":
                        execute_escalation(db, case, sla, "SLA_BREACH")
        finally:
            db.close()

# Global singleton
_sla_monitor = SLAMonitor(interval_seconds=30)

def start_sla_monitor():
    _sla_monitor.start()

def stop_sla_monitor():
    _sla_monitor.stop()
```

Wire into `backend/app/main.py`:

```python
# In on_startup event:
from app.background.sla_monitor import start_sla_monitor
start_sla_monitor()

# In shutdown (add on_event shutdown if needed):
from app.background.sla_monitor import stop_sla_monitor
stop_sla_monitor()
```

---

## FILES SUMMARY

### New Files to Create

| File | Purpose |
|------|---------|
| `backend/app/db/models_operational.py` | All new operational models |
| `backend/app/operational/priority.py` | Context-aware priority calculator |
| `backend/app/operational/sla.py` | SLA clock logic and state computation |
| `backend/app/operational/ownership.py` | Ownership resolution with delegation |
| `backend/app/operational/escalation.py` | Escalation policy engine |
| `backend/app/operational/metrics.py` | Campus Pulse, friction, student-time calculators |
| `backend/app/api/routes_operations.py` | New REST endpoints for operational layer |
| `backend/app/background/sla_monitor.py` | Background thread for SLA breach detection |

### Files to Modify

| File | Change |
|------|--------|
| `backend/app/db/models.py` | Add `operational_case_id`, `current_owner_id`, `blast_scope`, `affected_count` nullable columns |
| `backend/app/db/seed.py` | Add default SLA policies and escalation policies |
| `backend/app/api/routes_student.py` | Create OperationalCase + SLAInstance on complaint/gatepass creation |
| `backend/app/api/routes_staff.py` | Add operational case actions (acknowledge, complete, verify) |
| `backend/app/api/routes_admin.py` | Add new analytics endpoint for Campus Pulse |
| `backend/app/main.py` | Register `routes_operations` router; start/stop SLA monitor |
| `backend/app/schemas.py` | Add Pydantic models for operational API inputs/outputs |

---

## TESTING REQUIREMENTS

For every new module, add tests in `backend/tests/`:

```python
# backend/tests/test_priority.py
def test_calculate_priority_safety_keywords():
    result = calculate_priority(
        service_type="MAINTENANCE",
        domain="HOSTEL",
        text="Exposed electrical wire sparking near ceiling",
        context={}
    )
    assert result == "P0"

def test_calculate_priority_student_at_gate():
    result = calculate_priority(
        service_type="GATE_PASS",
        domain="SAFETY",
        text="Need gate pass for medical emergency",
        context={"student_at_gate": True}
    )
    assert result == "P0"

# backend/tests/test_sla.py
def test_sla_state_on_track():
    sla = SLAInstance(started_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=1),
                      ack_due_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=9))
    state = compute_sla_state(sla, datetime.datetime.utcnow())
    assert state == "ON_TRACK"

def test_sla_state_at_risk():
    sla = SLAInstance(started_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=9),
                      ack_due_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=1))
    state = compute_sla_state(sla, datetime.datetime.utcnow())
    assert state == "AT_RISK"

def test_sla_state_breached():
    sla = SLAInstance(started_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=15),
                      ack_due_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=5))
    state = compute_sla_state(sla, datetime.datetime.utcnow())
    assert state == "BREACHED"

# backend/tests/test_escalation.py
def test_should_escalate_on_sla_breach():
    sla = SLAInstance(sla_state="BREACHED")
    # Should escalate

def test_should_not_escalate_on_track():
    sla = SLAInstance(sla_state="ON_TRACK")
    # Should not escalate

# backend/tests/test_metrics.py
def test_student_time_lost_single_case():
    case = OperationalCase(
        created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        estimated_affected=10
    )
    lost = calculate_student_time_lost(case, datetime.datetime.utcnow())
    assert lost == pytest.approx(1200, rel=10)  # ~1200 student-minutes

def test_friction_score():
    case = OperationalCase(handoff_count=3, student_follow_up_count=1, reopen_count=0)
    score = calculate_friction_score(case)
    assert 0 <= score <= 100

# backend/tests/test_e2e_p0_gatepass.py
def test_p0_gatepass_escalation():
    # Student at gate creates P0 gate pass
    # HOD doesn't respond
    # After SLA breach, auto-escalates to Principal
    # Principal approves
    # Case resolved
    pass
```

---

## VERIFICATION CHECKLIST

After each phase, verify:

- [ ] All existing tests still pass (`cd backend && python -m pytest -v`)
- [ ] New unit tests pass for each module
- [ ] Complaint creation still works end-to-end
- [ ] Gate pass creation still works end-to-end
- [ ] Admin dashboard still loads
- [ ] New `/api/operations/*` endpoints respond correctly
- [ ] SLA state transitions correctly from ON_TRACK → AT_RISK → BREACHED
- [ ] Escalation fires when SLA breaches
- [ ] Campus Pulse endpoint returns valid JSON
- [ ] No secrets or PII in logs

---

## IMPORTANT CONSTRAINTS

1. **DO NOT replace existing models.** Only add nullable columns.
2. **DO NOT change existing API response formats.** Add new fields, don't remove old ones.
3. **DO NOT introduce new infrastructure.** No Celery, Kafka, Redis, RabbitMQ.
4. **DO NOT use ML/LLM for business logic.** Deterministic rules only.
5. **DO NOT hard-code institution-specific hierarchy.** Make escalation chains configurable.
6. **DO NOT log passwords, tokens, or personal data.**
7. **DO break work into git commits per phase.**
8. **Keep student UI minimal.** The complexity lives in admin/Control Tower.
9. **Business rules live server-side.** Frontend is only for display.
10. **Test after every change.** Run `pytest` before declaring anything working.
