import datetime
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.db.models import User, Complaint, ComplaintAuditTrail, Attendance, ScheduleSlot, GatePass, MessMenuItem, MessHall
from app.auth.security import require_role
from app.schemas import (
    ComplaintStatusUpdate, ComplaintResponse, AttendanceMark,
    AttendanceRecordResponse, GatePassAction, GatePassResponse, MessMenuItemCreate
)

router = APIRouter(prefix="/api/staff", tags=["Staff & Warden Portal"])

@router.get("/dashboard")
def get_staff_dashboard(staff: User = Depends(require_role("STAFF", "ADMIN")), db: Session = Depends(get_db)):
    assigned_count = db.query(Complaint).filter(Complaint.assigned_to == staff.id, Complaint.status != "RESOLVED").count()
    all_open_tickets = db.query(Complaint).filter(Complaint.status.in_(["OPEN", "ASSIGNED", "IN_PROGRESS"])).count()
    pending_gatepass = db.query(GatePass).filter(GatePass.status == "PENDING").count()

    return {
        "staff": {
            "name": staff.name,
            "role": staff.role,
            "hostel": staff.hostel,
            "branch": staff.branch
        },
        "stats": {
            "my_assigned_tickets": assigned_count,
            "campus_open_tickets": all_open_tickets,
            "pending_gatepasses": pending_gatepass
        }
    }

@router.get("/tickets", response_model=List[ComplaintResponse])
def get_assigned_tickets(staff: User = Depends(require_role("STAFF", "ADMIN")), db: Session = Depends(get_db)):
    query = db.query(Complaint)
    if staff.role == "ADMIN":
        pass
    elif staff.hostel:
        query = query.filter((Complaint.assigned_to == staff.id) | (Complaint.place == staff.hostel))
    else:
        query = query.filter(Complaint.assigned_to == staff.id)

    tickets = query.order_by(desc(Complaint.created_at)).all()
    now = datetime.datetime.utcnow()
    results = []
    for c in tickets:
        age_hours = (now - c.created_at).total_seconds() / 3600.0 if c.created_at else 0
        bucket = "normal"
        if age_hours > 72:
            bucket = ">72h"
        elif age_hours > 48:
            bucket = ">48h"
        elif age_hours > 24:
            bucket = ">24h"

        results.append({
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
        })
    return results

@router.put("/tickets/{complaint_id}/status")
def update_ticket_status(
    complaint_id: int,
    data: ComplaintStatusUpdate,
    staff: User = Depends(require_role("STAFF", "ADMIN")),
    db: Session = Depends(get_db)
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    prev_status = complaint.status
    new_status = data.status.upper()
    complaint.status = new_status
    now = datetime.datetime.utcnow()

    if new_status == "RESOLVED":
        complaint.resolved_at = now
    if data.assigned_to:
        complaint.assigned_to = data.assigned_to

    audit = ComplaintAuditTrail(
        complaint_id=complaint.id,
        action=f"STATUS_UPDATED_TO_{new_status}",
        performed_by=staff.id,
        previous_status=prev_status,
        new_status=new_status,
        note=data.note or f"Status transitioned by {staff.name}",
        timestamp=now
    )
    db.add(audit)

    # Sync OperationalCase status
    from app.db.models_operational import OperationalCase, OperationalAuditEvent, SLAInstance
    oc = db.query(OperationalCase).filter(
        OperationalCase.linked_entity_type == "Complaint",
        OperationalCase.linked_entity_id == complaint_id
    ).first()

    if oc:
        status_map = {
            "ASSIGNED": "ASSIGNED",
            "IN_PROGRESS": "IN_PROGRESS",
            "RESOLVED": "WORK_COMPLETED",
        }
        oc_status = status_map.get(new_status, new_status)
        oc.status = oc_status
        if new_status == "RESOLVED":
            oc.resolved_at = now
        if data.assigned_to:
            oc.current_owner_id = data.assigned_to

        sla = db.query(SLAInstance).filter(
            SLAInstance.operational_case_id == oc.id
        ).first()
        if sla and new_status == "RESOLVED":
            sla.resolved_at = now
            sla.sla_state = "MET"

        oc_audit = OperationalAuditEvent(
            operational_case_id=oc.id,
            event_type=f"COMPLAINT_STATUS_{new_status}",
            actor_id=staff.id,
            old_value=prev_status,
            new_value=oc_status,
            reason=data.note or f"Staff {staff.name} updated status"
        )
        db.add(oc_audit)

    db.commit()

    return {"status": "success", "complaint_id": complaint.id, "new_status": complaint.status}

@router.post("/attendance/mark")
def mark_attendance_session(data: AttendanceMark, staff: User = Depends(require_role("STAFF", "ADMIN")), db: Session = Depends(get_db)):
    created_records = []
    for s_id in data.student_ids:
        # Check if already marked for date and course
        existing = db.query(Attendance).filter(
            Attendance.course_id == data.course_id,
            Attendance.student_id == s_id,
            Attendance.session_date == data.session_date
        ).first()

        if existing:
            existing.status = data.status
            existing.marked_by = staff.id
        else:
            att = Attendance(
                course_id=data.course_id,
                student_id=s_id,
                session_date=data.session_date,
                status=data.status,
                marked_by=staff.id
            )
            db.add(att)
            created_records.append(att)

    db.commit()
    return {"status": "success", "marked_students_count": len(data.student_ids), "course_id": data.course_id}

@router.get("/students")
def list_students(staff: User = Depends(require_role("STAFF", "ADMIN")), db: Session = Depends(get_db)):
    students = db.query(User).filter(User.role == "STUDENT").all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "roll_no": s.roll_no,
            "branch": s.branch,
            "year": s.year,
            "hostel": s.hostel,
            "room": s.room,
            "email": s.email,
            "phone": s.phone
        }
        for s in students
    ]

@router.get("/gatepass/queue", response_model=List[GatePassResponse])
def get_gatepass_queue(staff: User = Depends(require_role("STAFF", "ADMIN")), db: Session = Depends(get_db)):
    passes = db.query(GatePass).order_by(desc(GatePass.created_at)).all()
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

@router.post("/gatepass/{gatepass_id}/action")
def act_on_gatepass(
    gatepass_id: int,
    data: GatePassAction,
    staff: User = Depends(require_role("STAFF", "ADMIN")),
    db: Session = Depends(get_db)
):
    gp = db.query(GatePass).filter(GatePass.id == gatepass_id).first()
    if not gp:
        raise HTTPException(status_code=404, detail="Gate pass not found")

    try:
        chain = json.loads(gp.approver_chain)
    except Exception:
        chain = []

    now = datetime.datetime.utcnow().isoformat()
    action = data.action.upper()

    if action == "APPROVE":
        # Update the step matching the staff member's role or sequential pending step
        updated_any = False
        for step in chain:
            if step.get("status") in ["PENDING", "ACTIVE"]:
                step["status"] = "APPROVED"
                step["timestamp"] = now
                step["approved_by"] = staff.name
                step["note"] = data.note or "Approved by staff"
                updated_any = True
                break
        
        # Check if all steps approved
        all_approved = all(s.get("status") == "APPROVED" for s in chain)
        if all_approved or len(chain) == 0:
            gp.status = "APPROVED"
        else:
            gp.status = "PENDING"

    elif action == "REJECT":
        for step in chain:
            if step.get("status") in ["PENDING", "ACTIVE"]:
                step["status"] = "REJECTED"
                step["timestamp"] = now
                step["note"] = data.note or "Rejected by staff"
                break
        gp.status = "REJECTED"

    elif action == "MARK_OUT":
        gp.status = "OUT"

    elif action == "MARK_RETURNED":
        gp.status = "RETURNED"

    gp.approver_chain = json.dumps(chain)
    db.commit()

    return {"status": "success", "gatepass_id": gp.id, "new_status": gp.status}


@router.post("/tickets/{complaint_id}/request-verification")
def request_verification(
    complaint_id: int,
    note: Optional[str] = "Work completed. Please confirm resolution.",
    staff: User = Depends(require_role("STAFF", "ADMIN")),
    db: Session = Depends(get_db)
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    prev_status = complaint.status
    now = datetime.datetime.utcnow()
    complaint.status = "RESOLVED"
    complaint.resolved_at = now

    audit = ComplaintAuditTrail(
        complaint_id=complaint.id,
        action="WORK_COMPLETED_VERIFICATION_REQUESTED",
        performed_by=staff.id,
        previous_status=prev_status,
        new_status="RESOLVED",
        note=note,
        timestamp=now
    )
    db.add(audit)

    from app.db.models_operational import OperationalCase, OperationalAuditEvent, SLAInstance
    oc = db.query(OperationalCase).filter(
        OperationalCase.linked_entity_type == "Complaint",
        OperationalCase.linked_entity_id == complaint_id
    ).first()

    if oc:
        oc.status = "VERIFICATION_PENDING"
        oc.completed_at = now

        sla = db.query(SLAInstance).filter(
            SLAInstance.operational_case_id == oc.id
        ).first()
        if sla:
            sla.resolved_at = now

        oc_audit = OperationalAuditEvent(
            operational_case_id=oc.id,
            event_type="VERIFICATION_REQUESTED",
            actor_id=staff.id,
            old_value="IN_PROGRESS",
            new_value="VERIFICATION_PENDING",
            reason=note
        )
        db.add(oc_audit)

    db.commit()
    return {"status": "success", "complaint_id": complaint_id}
