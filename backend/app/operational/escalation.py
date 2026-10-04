import datetime
from sqlalchemy.orm import Session
from app.db.models_operational import (
    OperationalCase, EscalationPolicy, EscalationEvent, SLAInstance
)
from app.operational.sla import compute_sla_state
from app.operational.ownership import transfer_ownership
from app.db.models import User


def get_escalation_policy(db: Session, case: OperationalCase) -> EscalationPolicy:
    return db.query(EscalationPolicy).filter(
        EscalationPolicy.domain == case.domain,
        EscalationPolicy.service_type == case.service_type,
        EscalationPolicy.priority == case.priority,
        EscalationPolicy.is_active == True
    ).order_by(EscalationPolicy.step_order).first()


def should_escalate(db: Session, case: OperationalCase, sla: SLAInstance) -> bool:
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
    policy = get_escalation_policy(db, case)
    if not policy:
        return

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

    case.status = "ESCALATED"

    if new_owner:
        transfer_ownership(case, new_owner.id, f"ESCALATED: {trigger}", db)


def evaluate_escalations(db: Session):
    active_cases = db.query(OperationalCase).filter(
        OperationalCase.status.notin_(["RESOLVED", "CLOSED", "CANCELLED"])
    ).all()

    escalated = []
    for case in active_cases:
        sla = db.query(SLAInstance).filter(
            SLAInstance.operational_case_id == case.id
        ).first()
        if not sla:
            continue

        if should_escalate(db, case, sla):
            execute_escalation(db, case, sla, "SLA_BREACH")
            escalated.append(case.id)

    if escalated:
        db.commit()
