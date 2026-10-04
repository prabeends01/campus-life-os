import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base


class IncidentMember(Base):
    __tablename__ = "incident_members"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    linked_case_id = Column(Integer, nullable=True)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)
    impact_statement = Column(Text, nullable=True)

    incident = relationship("Incident")
    student = relationship("User")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    asset_type = Column(String(50), nullable=False)
    location = Column(String(100), nullable=False)
    building = Column(String(100), nullable=True)
    floor = Column(String(20), nullable=True)
    installed_at = Column(DateTime, nullable=True)
    last_maintained_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AssetFailure(Base):
    __tablename__ = "asset_failures"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    operational_case_id = Column(Integer, ForeignKey("operational_cases.id"), nullable=True)
    failure_description = Column(Text, nullable=False)
    failure_type = Column(String(50), nullable=False)
    failed_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    downtime_hours = Column(Integer, default=0)
    affected_students = Column(Integer, default=0)
    repair_notes = Column(Text, nullable=True)

    asset = relationship("Asset")
