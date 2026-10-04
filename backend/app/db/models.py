import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False)  # STUDENT, STAFF, ADMIN, MESS
    roll_no = Column(String(50), nullable=True, index=True)
    branch = Column(String(50), nullable=True)  # CSE, ECE, MECH, CIVIL, etc.
    year = Column(Integer, nullable=True)       # 1, 2, 3, 4
    hostel = Column(String(50), nullable=True)  # Aryabhatta Hall, Gargi Hall, etc.
    room = Column(String(20), nullable=True)    # 302, 104, etc.
    phone = Column(String(20), nullable=True)
    preferred_language = Column(String(10), default="en") # en, hi, or
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    complaints = relationship("Complaint", foreign_keys="Complaint.student_id", back_populates="student")
    assigned_complaints = relationship("Complaint", foreign_keys="Complaint.assigned_to", back_populates="assignee")
    gate_passes = relationship("GatePass", back_populates="student")
    certificates = relationship("CertificateRequest", back_populates="student")
    attendances = relationship("Attendance", foreign_keys="Attendance.student_id", back_populates="student")
    read_receipts = relationship("NoticeReadReceipt", back_populates="student")
    feedbacks = relationship("MessFeedback", back_populates="student")


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String(50), nullable=False)  # Plumbing, Electrical, Mess, Cleanliness, IT, Other
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    photo_path = Column(String(255), nullable=True)
    place = Column(String(100), nullable=False)    # Hostel Block A, Academic Block, etc.
    room = Column(String(50), nullable=False)
    floor = Column(String(20), nullable=True)
    priority = Column(String(20), default="MEDIUM") # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(20), default="OPEN")     # OPEN, ASSIGNED, IN_PROGRESS, RESOLVED
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    student = relationship("User", foreign_keys=[student_id], back_populates="complaints")
    assignee = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_complaints")
    audit_trails = relationship("ComplaintAuditTrail", back_populates="complaint", cascade="all, delete-orphan")
    incident = relationship("Incident", back_populates="complaints")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)
    place = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="INVESTIGATING")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    severity = Column(String(5), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    affected_population = Column(Integer, default=0)
    service = Column(String(50), nullable=True)
    started_at = Column(DateTime, nullable=True)
    next_update = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    operational_case_id = Column(Integer, nullable=True)

    complaints = relationship("Complaint", back_populates="incident")
    owner = relationship("User", foreign_keys=[owner_id])


class ComplaintAuditTrail(Base):
    __tablename__ = "complaint_audit_trails"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    action = Column(String(100), nullable=False)
    performed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    previous_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=False)
    note = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    complaint = relationship("Complaint", back_populates="audit_trails")
    performer = relationship("User")


class GatePass(Base):
    __tablename__ = "gate_passes"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(String(255), nullable=False)
    destination = Column(String(255), nullable=False)
    departure_time = Column(DateTime, nullable=False)
    expected_return = Column(DateTime, nullable=False)
    # approver_chain JSON text e.g. [{"role": "faculty", "name": "Prof. Jena", "status": "APPROVED", "timestamp": "..."}, ...]
    approver_chain = Column(Text, nullable=False, default="[]")
    status = Column(String(20), default="PENDING") # PENDING, APPROVED, REJECTED, OUT, RETURNED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    student = relationship("User", back_populates="gate_passes")


class CertificateRequest(Base):
    __tablename__ = "certificate_requests"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(50), nullable=False) # BONAFIDE, TRANSCRIPT, MIGRATION
    purpose = Column(Text, nullable=False)
    status = Column(String(20), default="PENDING") # PENDING, PROCESSING, READY, COLLECTED
    requested_at = Column(DateTime, default=datetime.datetime.utcnow)
    ready_at = Column(DateTime, nullable=True)

    student = relationship("User", back_populates="certificates")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String(50), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False) # PRESENT, ABSENT
    marked_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    student = relationship("User", foreign_keys=[student_id], back_populates="attendances")
    marker = relationship("User", foreign_keys=[marked_by])


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String(50), nullable=False)
    course_name = Column(String(100), nullable=False)
    day_of_week = Column(String(20), nullable=False) # Monday, Tuesday, ...
    start_time = Column(String(10), nullable=False)  # 09:00
    end_time = Column(String(10), nullable=False)    # 10:00
    room = Column(String(50), nullable=False)
    instructor_name = Column(String(100), nullable=False)
    batch = Column(String(50), default="CSE-2023")


class Notice(Base):
    __tablename__ = "notices"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_type = Column(String(20), default="ALL") # ALL, BATCH, BRANCH, HOSTEL, YEAR
    target_value = Column(String(100), default="ALL")
    priority = Column(String(20), default="NORMAL") # NORMAL, URGENT, CRITICAL
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    auto_reminder_sent = Column(Boolean, default=False)
    sms_fallback_sent = Column(Boolean, default=False)

    author = relationship("User")
    read_receipts = relationship("NoticeReadReceipt", back_populates="notice", cascade="all, delete-orphan")


class NoticeReadReceipt(Base):
    __tablename__ = "notice_read_receipts"

    id = Column(Integer, primary_key=True, index=True)
    notice_id = Column(Integer, ForeignKey("notices.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    read_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)

    notice = relationship("Notice", back_populates="read_receipts")
    student = relationship("User", back_populates="read_receipts")


class MessHall(Base):
    __tablename__ = "mess_halls"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    hostel_id = Column(String(50), nullable=False)

    menu_items = relationship("MessMenuItem", back_populates="mess_hall")


class MessMenuItem(Base):
    __tablename__ = "mess_menu_items"

    id = Column(Integer, primary_key=True, index=True)
    mess_hall_id = Column(Integer, ForeignKey("mess_halls.id"), nullable=False)
    date = Column(Date, nullable=False)
    meal_type = Column(String(20), nullable=False) # BREAKFAST, LUNCH, SNACKS, DINNER
    name = Column(String(150), nullable=False)
    photo_path = Column(String(255), nullable=True)

    mess_hall = relationship("MessHall", back_populates="menu_items")
    feedbacks = relationship("MessFeedback", back_populates="menu_item")


class MessFeedback(Base):
    __tablename__ = "mess_feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("mess_menu_items.id"), nullable=False)
    rating = Column(Integer, nullable=False) # 1 - 5
    tags = Column(Text, nullable=True, default="[]") # JSON list: ["too_salty", "cold", "fresh"]
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    student = relationship("User", back_populates="feedbacks")
    menu_item = relationship("MessMenuItem", back_populates="feedbacks")


class VoiceSession(Base):
    __tablename__ = "voice_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    language = Column(String(10), default="en") # en, hi, or
    transcript = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")


class CampusMap(Base):
    __tablename__ = "campus_maps"

    id = Column(Integer, primary_key=True, index=True)
    glb_path = Column(String(255), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)

    pins = relationship("MapPin", back_populates="campus_map", cascade="all, delete-orphan")


class MapPin(Base):
    __tablename__ = "map_pins"

    id = Column(Integer, primary_key=True, index=True)
    campus_map_id = Column(Integer, ForeignKey("campus_maps.id"), nullable=False)
    label = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False)

    campus_map = relationship("CampusMap", back_populates="pins")


class AskRequest(Base):
    __tablename__ = "ask_requests"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    raw_text = Column(Text, nullable=False)
    intent = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    entities = Column(Text, nullable=False, default="{}") # JSON dict
    linked_complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=True)
    linked_gatepass_id = Column(Integer, ForeignKey("gate_passes.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    student = relationship("User")
