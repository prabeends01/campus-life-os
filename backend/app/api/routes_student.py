import datetime
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.db.session import get_db
from app.db.models import (
    User, Complaint, ComplaintAuditTrail, GatePass, CertificateRequest,
    Attendance, ScheduleSlot, Notice, NoticeReadReceipt, MessHall, MessMenuItem
)
from app.auth.security import require_role
from app.schemas import (
    ComplaintCreate, ComplaintResponse, GatePassCreate, GatePassResponse,
    CertificateRequestCreate, CertificateRequestResponse, AttendanceOverview,
    AttendanceSubjectSummary, ScheduleSlotResponse, NoticeResponse
)
from app.agents.complaint_routing_agent import ComplaintRoutingAgent
from app.agents.pattern_memory_agent import PatternMemoryAgent
from app.agents.policy_agent import PolicyAgent
from app.operational.priority import calculate_priority
from app.operational.sla import create_sla_instance

router = APIRouter(prefix="/api/student", tags=["Student Portal"])
routing_agent = ComplaintRoutingAgent()
pattern_agent = PatternMemoryAgent()
policy_agent = PolicyAgent()

@router.get("/dashboard")
def get_student_dashboard(student: User = Depends(require_role("STUDENT")), db: Session = Depends(get_db)):
    today_name = datetime.datetime.now().strftime("%A")
    today_slots = db.query(ScheduleSlot).filter(
        ScheduleSlot.day_of_week == today_name,
        ScheduleSlot.batch == f"{student.branch}-{2026 - (student.year or 3)}"
    ).all()
    if not today_slots:
        # Fallback to Monday if today is weekend
        today_slots = db.query(ScheduleSlot).filter(ScheduleSlot.day_of_week == "Monday").all()

    # Notices targeting this student
    notices_query = db.query(Notice).filter(
        or_(
            Notice.target_type == "ALL",
            (Notice.target_type == "BRANCH") & (Notice.target_value == student.branch),
            (Notice.target_type == "HOSTEL") & (Notice.target_value == student.hostel),
            (Notice.target_type == "YEAR") & (Notice.target_value == str(student.year))
        )
    ).order_by(desc(Notice.created_at)).limit(5).all()

    # Read receipts
    read_ids = {r.notice_id for r in db.query(NoticeReadReceipt).filter(NoticeReadReceipt.student_id == student.id).all()}
    enriched_notices = []
    for n in notices_query:
        enriched_notices.append({
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "priority": n.priority,
            "target_type": n.target_type,
            "target_value": n.target_value,
            "created_at": n.created_at,
            "is_read": n.id in read_ids
        })

    # Stats
    open_complaints_count = db.query(Complaint).filter(Complaint.student_id == student.id, Complaint.status != "RESOLVED").count()
    pending_gatepass_count = db.query(GatePass).filter(GatePass.student_id == student.id, GatePass.status == "PENDING").count()
    pending_cert_count = db.query(CertificateRequest).filter(CertificateRequest.student_id == student.id, CertificateRequest.status != "COLLECTED").count()

    # Attendance overall
    records = db.query(Attendance).filter(Attendance.student_id == student.id).all()
    overall_pct = 0.0
    if records:
        present_count = sum(1 for r in records if r.status == "PRESENT")
        overall_pct = round((present_count / len(records)) * 100, 1)

    return {
        "student": {
            "name": student.name,
            "roll_no": student.roll_no,
            "hostel": student.hostel,
            "room": student.room,
            "branch": student.branch,
            "year": student.year
        },
        "timetable_today": today_slots,
        "notices": enriched_notices,
        "stats": {
            "attendance_percentage": overall_pct,
            "is_attendance_low": overall_pct < 75.0,
            "open_complaints": open_complaints_count,
            "pending_requests": pending_gatepass_count + pending_cert_count
        }
    }

@router.get("/complaints", response_model=List[ComplaintResponse])
def get_my_complaints(student: User = Depends(require_role("STUDENT")), db: Session = Depends(get_db)):
    complaints = db.query(Complaint).filter(Complaint.student_id == student.id).order_by(desc(Complaint.created_at)).all()
    now = datetime.datetime.utcnow()
    results = []
    for c in complaints:
        age_hours = (now - c.created_at).total_seconds() / 3600.0 if c.created_at else 0
        bucket = "normal"
        if age_hours > 72:
            bucket = ">72h"
        elif age_hours > 48:
            bucket = ">48h"
        elif age_hours > 24:
            bucket = ">24h"
        
        c_dict = {
            "id": c.id,
            "student_id": c.student_id,
            "category": c.category,
            "title": c.title,
            "description": c.description,
            "photo_path": c.photo_path,
            "place": c.place,
            "room": c.room,
            "floor": c.floor,
            "priority": c.priority,
            "status": c.status,
            "assigned_to": c.assigned_to,
            "incident_id": c.incident_id,
            "created_at": c.created_at,
            "resolved_at": c.resolved_at,
            "audit_trails": c.audit_trails,
            "age_hours": round(age_hours, 1),
            "ageing_bucket": bucket
        }
        results.append(c_dict)
    return results

@router.post("/complaints", response_model=ComplaintResponse)
def create_complaint(data: ComplaintCreate, student: User = Depends(require_role("STUDENT")), db: Session = Depends(get_db)):
    # 1. Run ComplaintRoutingAgent
    agent_res = routing_agent.run({
        "category_text": data.category,
        "free_text": f"{data.title} {data.description}"
    })
    suggested_cat = agent_res.output.get("category", data.category)
    suggested_priority = agent_res.output.get("suggested_priority", "MEDIUM")

    # Find staff for hostel/department if available
    staff_assignee = db.query(User).filter(User.role == "STAFF").first()

    now = datetime.datetime.utcnow()
    new_complaint = Complaint(
        student_id=student.id,
        category=suggested_cat,
        title=data.title,
        description=data.description,
        photo_path=data.photo_path,
        place=data.place or student.hostel or "Aryabhatta Hall",
        room=data.room or student.room or "302",
        floor=data.floor,
        priority=suggested_priority,
        status="OPEN",
        assigned_to=staff_assignee.id if staff_assignee else None,
        created_at=now
    )
    db.add(new_complaint)
    db.commit()
    db.refresh(new_complaint)

    # Initial Audit Trail
    audit = ComplaintAuditTrail(
        complaint_id=new_complaint.id,
        action="CREATED",
        performed_by=student.id,
        previous_status=None,
        new_status="OPEN",
        note=f"Complaint lodged by student. Auto-routed to {agent_res.output.get('department')} with {suggested_priority} priority.",
        timestamp=now
    )
    db.add(audit)

    # Create OperationalCase for reliability tracking
    from app.db.models_operational import OperationalCase, OperationalAuditEvent

    op_priority = calculate_priority(
        service_type="MAINTENANCE",
        domain="HOSTEL",
        text=f"{data.title} {data.description}",
        context={}
    )

    oc = OperationalCase(
        domain="HOSTEL",
        service_type="MAINTENANCE",
        requester_id=student.id,
        current_owner_id=staff_assignee.id if staff_assignee else None,
        owning_role="MAINTENANCE_STAFF",
        priority=op_priority,
        status="SUBMITTED",
        estimated_affected=1,
        linked_entity_type="Complaint",
        linked_entity_id=new_complaint.id,
        created_at=now
    )
    db.add(oc)
    db.flush()

    sla = create_sla_instance(db, oc)
    if sla:
        db.add(sla)

    oc_audit = OperationalAuditEvent(
        operational_case_id=oc.id,
        event_type="CREATED",
        actor_id=student.id,
        new_value="SUBMITTED",
        reason="Complaint operational case created"
    )
    db.add(oc_audit)
    db.commit()

    # Check pattern memory agent
    pattern_res = pattern_agent.run({
        "db": db,
        "place": new_complaint.place,
        "category": new_complaint.category,
        "room": new_complaint.room
    })
    # If spike or chronic, add internal audit notice
    if pattern_res.output.get("is_immediate_spike") or pattern_res.output.get("is_chronic"):
        alert_note = f"PATTERN ALERT: {pattern_res.output.get('suggested_incident_title')}"
        alert_audit = ComplaintAuditTrail(
            complaint_id=new_complaint.id,
            action="RECURRING_ALERT_FLAGGED",
            performed_by=student.id,
            previous_status="OPEN",
            new_status="OPEN",
            note=alert_note,
            timestamp=now
        )
        db.add(alert_audit)
        db.commit()

    return {
        "id": new_complaint.id,
        "student_id": new_complaint.student_id,
        "category": new_complaint.category,
        "title": new_complaint.title,
        "description": new_complaint.description,
        "photo_path": new_complaint.photo_path,
        "place": new_complaint.place,
        "room": new_complaint.room,
        "floor": new_complaint.floor,
        "priority": new_complaint.priority,
        "status": new_complaint.status,
        "assigned_to": new_complaint.assigned_to,
        "incident_id": new_complaint.incident_id,
        "created_at": new_complaint.created_at,
        "resolved_at": new_complaint.resolved_at,
        "audit_trails": new_complaint.audit_trails,
        "age_hours": 0.0,
        "ageing_bucket": "normal"
    }

@router.get("/requests/gatepass", response_model=List[GatePassResponse])
def get_gate_passes(student: User = Depends(require_role("STUDENT")), db: Session = Depends(get_db)):
    passes = db.query(GatePass).filter(GatePass.student_id == student.id).order_by(desc(GatePass.created_at)).all()
    results = []
    for gp in passes:
        try:
            chain = json.loads(gp.approver_chain)
        except Exception:
            chain = []
        results.append({
            "id": gp.id,
            "student_id": gp.student_id,
            "reason": gp.reason,
            "destination": gp.destination,
            "departure_time": gp.departure_time,
            "expected_return": gp.expected_return,
            "approver_chain": chain,
            "status": gp.status,
            "created_at": gp.created_at
        })
    return results

@router.post("/requests/gatepass", response_model=GatePassResponse)
def request_gate_pass(data: GatePassCreate, student: User = Depends(require_role("STUDENT")), db: Session = Depends(get_db)):
    now = datetime.datetime.utcnow()
    policy_res = policy_agent.run({"policy_type": "GATE_PASS", "current_status": "PENDING"})
    chain = policy_res.output.get("approval_chain", [])

    new_gp = GatePass(
        student_id=student.id,
        reason=data.reason,
        destination=data.destination,
        departure_time=data.departure_time,
        expected_return=data.expected_return,
        approver_chain=json.dumps(chain),
        status="PENDING",
        created_at=now
    )
    db.add(new_gp)
    db.flush()

    # Determine context for priority — student at gate or future request?
    context = {}
    departure_delta = (data.departure_time - now).total_seconds() / 60
    if departure_delta < 60:
        context["student_at_gate"] = True

    op_priority = calculate_priority(
        service_type="GATE_PASS",
        domain="SAFETY",
        text=f"{data.reason} to {data.destination}",
        context=context
    )

    faculty = db.query(User).filter(User.role == "STAFF").first()

    from app.db.models_operational import OperationalCase, OperationalAuditEvent
    oc = OperationalCase(
        domain="SAFETY",
        service_type="GATE_PASS",
        requester_id=student.id,
        current_owner_id=faculty.id if faculty else None,
        owning_role="FACULTY",
        priority=op_priority,
        status="SUBMITTED",
        estimated_affected=1,
        linked_entity_type="GatePass",
        linked_entity_id=new_gp.id,
        created_at=now
    )
    db.add(oc)
    db.flush()

    sla = create_sla_instance(db, oc)
    if sla:
        db.add(sla)

    oc_audit = OperationalAuditEvent(
        operational_case_id=oc.id,
        event_type="CREATED",
        actor_id=student.id,
        new_value="SUBMITTED",
        reason="Gate pass operational case created"
    )
    db.add(oc_audit)
    db.commit()
    db.refresh(new_gp)

    return {
        "id": new_gp.id,
        "student_id": new_gp.student_id,
        "reason": new_gp.reason,
        "destination": new_gp.destination,
        "departure_time": new_gp.departure_time,
        "expected_return": new_gp.expected_return,
        "approver_chain": chain,
        "status": new_gp.status,
        "created_at": new_gp.created_at
    }

@router.get("/requests/certificates", response_model=List[CertificateRequestResponse])
def get_certificate_requests(student: User = Depends(require_role("STUDENT")), db: Session = Depends(get_db)):
    return db.query(CertificateRequest).filter(CertificateRequest.student_id == student.id).order_by(desc(CertificateRequest.requested_at)).all()

@router.post("/requests/certificates", response_model=CertificateRequestResponse)
def request_certificate(data: CertificateRequestCreate, student: User = Depends(require_role("STUDENT")), db: Session = Depends(get_db)):
    clean_type = data.type.upper().strip()
    if clean_type not in ["BONAFIDE", "TRANSCRIPT", "MIGRATION"]:
        clean_type = "BONAFIDE"
    
    new_cert = CertificateRequest(
        student_id=student.id,
        type=clean_type,
        purpose=data.purpose,
        status="PENDING",
        requested_at=datetime.datetime.utcnow()
    )
    db.add(new_cert)
    db.commit()
    db.refresh(new_cert)
    return new_cert

@router.get("/schedule")
def get_student_schedule(student: User = Depends(require_role("STUDENT")), db: Session = Depends(get_db)):
    # 1. Timetable slots
    batch_name = f"{student.branch}-{2026 - (student.year or 3)}"
    slots = db.query(ScheduleSlot).order_by(ScheduleSlot.day_of_week, ScheduleSlot.start_time).all()

    # 2. Attendance summary
    records = db.query(Attendance).filter(Attendance.student_id == student.id).all()
    subject_map = {}
    for r in records:
        if r.course_id not in subject_map:
            subject_map[r.course_id] = {"total": 0, "attended": 0}
        subject_map[r.course_id]["total"] += 1
        if r.status == "PRESENT":
            subject_map[r.course_id]["attended"] += 1

    course_names = {
        "CS301": "Database Management Systems",
        "CS302": "Computer Networks",
        "CS303": "Operating Systems",
        "CS304": "Design & Analysis of Algorithms"
    }

    subjects = []
    total_classes = 0
    total_attended = 0
    for cid, counts in subject_map.items():
        pct = round((counts["attended"] / counts["total"]) * 100, 1) if counts["total"] > 0 else 0.0
        total_classes += counts["total"]
        total_attended += counts["attended"]
        subjects.append({
            "course_id": cid,
            "course_name": course_names.get(cid, cid),
            "total_classes": counts["total"],
            "attended_classes": counts["attended"],
            "percentage": pct,
            "is_low": pct < 75.0
        })

    overall_pct = round((total_attended / total_classes) * 100, 1) if total_classes > 0 else 0.0

    return {
        "slots": slots,
        "attendance": {
            "overall_percentage": overall_pct,
            "is_overall_low": overall_pct < 75.0,
            "subjects": subjects
        }
    }

@router.get("/notices", response_model=List[NoticeResponse])
def get_student_notices(student: User = Depends(require_role("STUDENT")), db: Session = Depends(get_db)):
    notices = db.query(Notice).filter(
        or_(
            Notice.target_type == "ALL",
            (Notice.target_type == "BRANCH") & (Notice.target_value == student.branch),
            (Notice.target_type == "HOSTEL") & (Notice.target_value == student.hostel),
            (Notice.target_type == "YEAR") & (Notice.target_value == str(student.year))
        )
    ).order_by(desc(Notice.created_at)).all()

    read_ids = {r.notice_id for r in db.query(NoticeReadReceipt).filter(NoticeReadReceipt.student_id == student.id).all()}
    results = []
    for n in notices:
        results.append({
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "author_id": n.author_id,
            "author_name": n.author.name if n.author else "Dean Office",
            "target_type": n.target_type,
            "target_value": n.target_value,
            "priority": n.priority,
            "created_at": n.created_at,
            "is_read": n.id in read_ids
        })
    return results

@router.post("/notices/{notice_id}/read")
def mark_notice_read(notice_id: int, student: User = Depends(require_role("STUDENT")), db: Session = Depends(get_db)):
    receipt = db.query(NoticeReadReceipt).filter(
        NoticeReadReceipt.notice_id == notice_id,
        NoticeReadReceipt.student_id == student.id
    ).first()
    now = datetime.datetime.utcnow()
    if not receipt:
        receipt = NoticeReadReceipt(
            notice_id=notice_id,
            student_id=student.id,
            read_at=now,
            acknowledged_at=now
        )
        db.add(receipt)
    else:
        receipt.read_at = now
    db.commit()
    return {"status": "success", "notice_id": notice_id, "read_at": now.isoformat()}


@router.post("/verify-case/{operational_case_id}")
def verify_case(
    operational_case_id: int,
    confirmed: bool,
    student: User = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db)
):
    from app.db.models_operational import OperationalCase, OperationalAuditEvent, SLAInstance

    oc = db.query(OperationalCase).filter(
        OperationalCase.id == operational_case_id,
        OperationalCase.requester_id == student.id
    ).first()
    if not oc:
        raise HTTPException(status_code=404, detail="Case not found")

    now = datetime.datetime.utcnow()
    if confirmed:
        oc.status = "RESOLVED"
        oc.resolved_at = now
        oc.verified_at = now

        sla = db.query(SLAInstance).filter(
            SLAInstance.operational_case_id == oc.id
        ).first()
        if sla:
            sla.resolved_at = now
            sla.sla_state = "MET"

        reason = "Student confirmed resolution"
    else:
        oc.status = "REOPENED"
        oc.reopen_count += 1
        reason = "Student disputed resolution - problem persists"

    audit = OperationalAuditEvent(
        operational_case_id=oc.id,
        event_type="STUDENT_VERIFICATION",
        actor_id=student.id,
        new_value=oc.status,
        reason=reason
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "case_id": operational_case_id, "new_status": oc.status}


@router.get("/my-cases")
def get_my_cases(
    student: User = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db)
):
    from app.db.models_operational import OperationalCase, SLAInstance
    from app.operational.sla import compute_sla_state

    cases = db.query(OperationalCase).filter(
        OperationalCase.requester_id == student.id
    ).order_by(desc(OperationalCase.created_at)).limit(50).all()

    results = []
    for case in cases:
        sla = db.query(SLAInstance).filter(
            SLAInstance.operational_case_id == case.id
        ).first()
        sla_state = None
        if sla:
            sla_state = compute_sla_state(sla, datetime.datetime.utcnow())

        results.append({
            "id": case.id,
            "domain": case.domain,
            "service_type": case.service_type,
            "priority": case.priority,
            "status": case.status,
            "sla_state": sla_state,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "resolved_at": case.resolved_at.isoformat() if case.resolved_at else None,
            "linked_entity_type": case.linked_entity_type,
            "linked_entity_id": case.linked_entity_id,
            "student_follow_up_count": case.student_follow_up_count,
        })
    return results


@router.post("/cases/{operational_case_id}/follow-up")
def follow_up_case(
    operational_case_id: int,
    note: Optional[str] = None,
    student: User = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db)
):
    from app.db.models_operational import OperationalCase, OperationalAuditEvent

    oc = db.query(OperationalCase).filter(
        OperationalCase.id == operational_case_id,
        OperationalCase.requester_id == student.id
    ).first()
    if not oc:
        raise HTTPException(status_code=404, detail="Case not found")

    oc.student_follow_up_count += 1

    audit = OperationalAuditEvent(
        operational_case_id=oc.id,
        event_type="STUDENT_FOLLOW_UP",
        actor_id=student.id,
        old_value=str(oc.student_follow_up_count - 1),
        new_value=str(oc.student_follow_up_count),
        reason=note or "Student follow-up"
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "case_id": operational_case_id, "follow_up_count": oc.student_follow_up_count}
