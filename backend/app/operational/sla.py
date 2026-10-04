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


def create_sla_instance(db: Session, case: OperationalCase) -> Optional[SLAInstance]:
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
    if sla.pause_reason:
        return "PAUSED"
    if sla.resolved_at:
        return "MET"

    policy = sla.sla_policy
    at_risk_pct = policy.at_risk_threshold_pct if policy else 0.80

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
