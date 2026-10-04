import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import User
from app.db.models_operational import Delegation, OperationalCase, OwnershipHistory, OperationalAuditEvent


def is_available(user: User) -> bool:
    return True


def get_delegate(db: Session, user_id: int, at: datetime.datetime) -> Optional[User]:
    delegation = db.query(Delegation).filter(
        Delegation.delegator_id == user_id,
        Delegation.start_time <= at,
        Delegation.end_time >= at,
        Delegation.is_active == True
    ).first()
    if delegation:
        return db.query(User).filter(User.id == delegation.delegate_id).first()
    return None


def resolve_owner(db: Session, case: OperationalCase) -> Optional[User]:
    owner_id = case.current_owner_id
    if not owner_id:
        return None

    owner = db.query(User).filter(User.id == owner_id).first()
    if not owner:
        return None

    if is_available(owner):
        return owner

    delegate = get_delegate(db, owner_id, datetime.datetime.utcnow())
    if delegate:
        return delegate

    return None


def transfer_ownership(case: OperationalCase, new_owner_id: int, reason: str, db: Session, transferred_by: int = 0):
    old_owner_id = case.current_owner_id
    case.current_owner_id = new_owner_id
    case.handoff_count += 1

    history = OwnershipHistory(
        operational_case_id=case.id,
        from_owner_id=old_owner_id,
        to_owner_id=new_owner_id,
        reason=reason,
        transferred_by=transferred_by,
        is_delegation=False
    )
    db.add(history)

    audit = OperationalAuditEvent(
        operational_case_id=case.id,
        event_type="OWNERSHIP_TRANSFERRED",
        actor_id=transferred_by,
        old_value=str(old_owner_id) if old_owner_id else None,
        new_value=str(new_owner_id),
        reason=reason
    )
    db.add(audit)
