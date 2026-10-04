import datetime
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.db.models import Incident
from app.db.models_operational import (
    OperationalCase, SLAInstance, OperationalAuditEvent,
    EscalationEvent
)
from app.db.models_incident import IncidentMember
from app.auth.security import require_role
from app.operational.sla import compute_sla_state, create_sla_instance, get_sla_policy
from app.operational.ownership import transfer_ownership, resolve_owner
from app.operational.escalation import execute_escalation
from app.operational.metrics import (
    calculate_campus_pulse, calculate_slo_compliance,
    calculate_zero_chase_compliance
)

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

    audit_events = db.query(OperationalAuditEvent).filter(
        OperationalAuditEvent.operational_case_id == case_id
    ).order_by(OperationalAuditEvent.timestamp.desc()).limit(50).all()

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


@router.post("/cases")
def create_case(
    domain: str,
    service_type: str,
    requester_id: int,
    linked_entity_type: str,
    linked_entity_id: int,
    priority: str = "P2",
    current_owner_id: Optional[int] = None,
    admin: User = Depends(require_role("ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    now = datetime.datetime.utcnow()

    oc = OperationalCase(
        domain=domain,
        service_type=service_type,
        requester_id=requester_id,
        current_owner_id=current_owner_id,
        owning_role="STAFF",
        priority=priority,
        status="SUBMITTED",
        estimated_affected=1,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
        created_at=now
    )
    db.add(oc)
    db.flush()

    sla = create_sla_instance(db, oc)
    if sla:
        db.add(sla)

    audit = OperationalAuditEvent(
        operational_case_id=oc.id,
        event_type="CREATED",
        actor_id=admin.id,
        new_value="SUBMITTED",
        reason="Operational case created"
    )
    db.add(audit)
    db.commit()

    return {"id": oc.id, "status": "SUBMITTED", "sla_state": "ON_TRACK"}


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


@router.post("/cases/{case_id}/start-action")
def start_action_case(
    case_id: int,
    admin: User = Depends(require_role("ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    case = db.query(OperationalCase).filter(OperationalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    now = datetime.datetime.utcnow()
    case.status = "IN_PROGRESS"
    case.action_started_at = now

    sla = db.query(SLAInstance).filter(
        SLAInstance.operational_case_id == case_id
    ).first()
    if sla:
        sla.action_started_at = now

    audit = OperationalAuditEvent(
        operational_case_id=case_id,
        event_type="ACTION_STARTED",
        actor_id=admin.id,
        old_value="ACKNOWLEDGED",
        new_value="IN_PROGRESS",
        reason="Work started on case"
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "case_id": case_id}


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

    transfer_ownership(case, new_owner_id, reason, db, transferred_by=admin.id)
    db.commit()

    return {"status": "success", "case_id": case_id, "new_owner_id": new_owner_id}


@router.post("/cases/{case_id}/complete")
def complete_case(
    case_id: int,
    note: Optional[str] = None,
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
        sla.sla_state = "MET"

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
        reason=f"Student confirmed={confirmed}"
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "case_id": case_id, "new_status": case.status}


@router.post("/cases/{case_id}/request-info")
def request_info_case(
    case_id: int,
    message: str,
    admin: User = Depends(require_role("ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    case = db.query(OperationalCase).filter(OperationalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = "INFO_REQUESTED"

    audit = OperationalAuditEvent(
        operational_case_id=case_id,
        event_type="INFO_REQUESTED",
        actor_id=admin.id,
        old_value="IN_PROGRESS",
        new_value="INFO_REQUESTED",
        reason=message
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "case_id": case_id}


@router.post("/cases/{case_id}/provide-info")
def provide_info_case(
    case_id: int,
    admin: User = Depends(require_role("ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    case = db.query(OperationalCase).filter(OperationalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = "IN_PROGRESS"

    audit = OperationalAuditEvent(
        operational_case_id=case_id,
        event_type="INFO_RECEIVED",
        actor_id=admin.id,
        old_value="INFO_REQUESTED",
        new_value="IN_PROGRESS",
        reason="Student provided requested information"
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "case_id": case_id}


@router.post("/cases/{case_id}/escalate")
def escalate_case(
    case_id: int,
    reason: str = "MANUAL",
    note: Optional[str] = None,
    admin: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db)
):
    case = db.query(OperationalCase).filter(OperationalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    sla = db.query(SLAInstance).filter(
        SLAInstance.operational_case_id == case_id
    ).first()

    if sla:
        execute_escalation(db, case, sla, reason)

    return {"status": "success", "case_id": case_id}


@router.get("/metrics/pulse")
def get_campus_pulse(admin: User = Depends(require_role("ADMIN")), db: Session = Depends(get_db)):
    return calculate_campus_pulse(db)


@router.get("/metrics/slo")
def get_slo_metrics(
    service_type: Optional[str] = None,
    domain: Optional[str] = None,
    admin: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db)
):
    return {"slo_compliance_pct": calculate_slo_compliance(db, service_type, domain)}


@router.get("/metrics/zero-chase")
def get_zero_chase(
    domain: Optional[str] = None,
    admin: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db)
):
    return {"zero_chase_compliance_pct": calculate_zero_chase_compliance(db, domain)}


@router.get("/incidents")
def list_incidents(
    admin: User = Depends(require_role("ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    incidents = db.query(Incident).order_by(Incident.created_at.desc()).limit(100).all()
    results = []
    for inc in incidents:
        member_count = db.query(IncidentMember).filter(
            IncidentMember.incident_id == inc.id
        ).count()
        results.append({
            "id": inc.id,
            "title": inc.title,
            "category": inc.category,
            "place": inc.place,
            "description": inc.description,
            "status": inc.status,
            "severity": inc.severity,
            "affected_population": inc.affected_population,
            "member_count": member_count,
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
        })
    return results


@router.get("/incidents/{incident_id}")
def get_incident(
    incident_id: int,
    admin: User = Depends(require_role("ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    members = db.query(IncidentMember).filter(
        IncidentMember.incident_id == incident_id
    ).all()

    return {
        "id": inc.id,
        "title": inc.title,
        "category": inc.category,
        "place": inc.place,
        "description": inc.description,
        "status": inc.status,
        "severity": inc.severity,
        "affected_population": inc.affected_population,
        "service": inc.service,
        "created_at": inc.created_at.isoformat() if inc.created_at else None,
        "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
        "members": [
            {
                "id": m.id,
                "student_id": m.student_id,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                "impact_statement": m.impact_statement
            }
            for m in members
        ]
    }


@router.post("/incidents")
def create_incident(
    title: str,
    category: str,
    place: str,
    description: Optional[str] = None,
    severity: str = "P1",
    service: Optional[str] = None,
    admin: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db)
):
    now = datetime.datetime.utcnow()

    inc = Incident(
        title=title,
        category=category,
        place=place,
        description=description or f"Incident declared by {admin.name}",
        status="INVESTIGATING",
        severity=severity,
        service=service,
        affected_population=0,
        started_at=now,
        created_at=now
    )
    db.add(inc)
    db.flush()

    owner = db.query(User).filter(User.role == "ADMIN").first()
    if owner:
        inc.owner_id = owner.id

    db.commit()
    return {"id": inc.id, "status": "INVESTIGATING"}


@router.post("/incidents/{incident_id}/affected")
def join_incident(
    incident_id: int,
    student_id: Optional[int] = None,
    linked_case_id: Optional[int] = None,
    impact_statement: Optional[str] = None,
    user: User = Depends(require_role("STUDENT", "ADMIN", "STAFF")),
    db: Session = Depends(get_db)
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    resolved_student_id = student_id or user.id

    existing = db.query(IncidentMember).filter(
        IncidentMember.incident_id == incident_id,
        IncidentMember.student_id == resolved_student_id
    ).first()

    if existing:
        return {"status": "already_joined", "member_id": existing.id}

    member = IncidentMember(
        incident_id=incident_id,
        student_id=resolved_student_id,
        linked_case_id=linked_case_id,
        impact_statement=impact_statement,
        joined_at=datetime.datetime.utcnow()
    )
    db.add(member)

    inc.affected_population = (inc.affected_population or 0) + 1
    db.commit()

    return {"status": "joined", "incident_id": incident_id, "affected_count": inc.affected_population}


@router.put("/incidents/{incident_id}/status")
def update_incident_status(
    incident_id: int,
    status: str,
    note: Optional[str] = None,
    admin: User = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db)
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    inc.status = status.upper()
    if status.upper() == "RESOLVED":
        inc.resolved_at = datetime.datetime.utcnow()

    db.commit()
    return {"status": "success", "incident_id": incident_id, "new_status": inc.status}
