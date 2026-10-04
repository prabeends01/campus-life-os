import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.session import Base


class OperationalCase(Base):
    __tablename__ = "operational_cases"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(20), nullable=False)
    service_type = Column(String(50), nullable=False)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    current_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owning_role = Column(String(50), nullable=True)
    owning_department = Column(String(100), nullable=True)
    priority = Column(String(5), default="P2")
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
    priority = Column(String(5), nullable=False)
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
    sla_state = Column(String(20), default="ON_TRACK")
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
    metadata_json = Column(Text, nullable=True)

    operational_case = relationship("OperationalCase", back_populates="audit_events")


class EscalationPolicy(Base):
    __tablename__ = "escalation_policies"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(20), nullable=False)
    service_type = Column(String(50), nullable=False)
    priority = Column(String(5), nullable=False)
    trigger = Column(String(20), nullable=False)
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
