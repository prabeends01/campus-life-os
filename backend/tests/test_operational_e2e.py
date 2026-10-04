import pytest
import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal, Base, engine
from app.auth.security import create_access_token
from app.db.models import User, Complaint
from app.db.models_operational import OperationalCase, SLAInstance


client = TestClient(app)


@pytest.fixture
def auth_tokens():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    student = db.query(User).filter(User.role == "STUDENT").first()
    staff = db.query(User).filter(User.role == "STAFF").first()
    admin = db.query(User).filter(User.role == "ADMIN").first()

    student_token = create_access_token({"sub": str(student.id), "role": student.role, "email": student.email})
    staff_token = create_access_token({"sub": str(staff.id), "role": staff.role, "email": staff.email})
    admin_token = create_access_token({"sub": str(admin.id), "role": admin.role, "email": admin.email})

    db.close()
    return {
        "student": student_token,
        "staff": staff_token,
        "admin": admin_token
    }


def test_complaint_creates_operational_case(auth_tokens):
    """Complaint creation should also create an OperationalCase with SLA."""
    headers_student = {"Authorization": f"Bearer {auth_tokens['student']}"}

    resp = client.post("/api/student/complaints", json={
        "category": "Plumbing",
        "title": "Leaking tap in bathroom",
        "description": "Washbasin tap leaking constantly",
        "place": "Aryabhatta Hall",
        "room": "302"
    }, headers=headers_student)

    assert resp.status_code == 200
    complaint_id = resp.json()["id"]

    db = SessionLocal()
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    assert complaint is not None

    # Find operational case linked to this complaint
    oc = db.query(OperationalCase).filter(
        OperationalCase.linked_entity_type == "Complaint",
        OperationalCase.linked_entity_id == complaint_id
    ).first()

    assert oc is not None
    assert oc.domain == "HOSTEL"
    assert oc.service_type == "MAINTENANCE"
    assert oc.priority in ["P0", "P1", "P2", "P3"]
    assert oc.status == "SUBMITTED"

    # SLA instance should exist
    sla = db.query(SLAInstance).filter(
        SLAInstance.operational_case_id == oc.id
    ).first()
    assert sla is not None
    assert sla.sla_state == "ON_TRACK"
    assert sla.ack_due_at is not None

    db.close()


def test_staff_acknowledge_updates_operational_case(auth_tokens):
    """Staff updating ticket status should sync OperationalCase."""
    headers_student = {"Authorization": f"Bearer {auth_tokens['student']}"}

    resp = client.post("/api/student/complaints", json={
        "category": "Electrical",
        "title": "Fan not working",
        "description": "Ceiling fan stopped working",
        "place": "Aryabhatta Hall",
        "room": "302"
    }, headers=headers_student)

    complaint_id = resp.json()["id"]
    headers_staff = {"Authorization": f"Bearer {auth_tokens['staff']}"}

    resp2 = client.put(
        f"/api/staff/tickets/{complaint_id}/status",
        json={"status": "IN_PROGRESS", "note": "Technician assigned"},
        headers=headers_staff
    )
    assert resp2.status_code == 200

    db = SessionLocal()
    oc = db.query(OperationalCase).filter(
        OperationalCase.linked_entity_type == "Complaint",
        OperationalCase.linked_entity_id == complaint_id
    ).first()

    assert oc is not None
    assert oc.status in ["IN_PROGRESS", "WORK_COMPLETED"]
    db.close()


def test_gatepass_creates_operational_case(auth_tokens):
    """Gate pass request should also create an OperationalCase."""
    headers_student = {"Authorization": f"Bearer {auth_tokens['student']}"}

    departure = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    ret = datetime.datetime.utcnow() + datetime.timedelta(days=3)

    resp = client.post("/api/student/requests/gatepass", json={
        "reason": "Medical emergency at home",
        "destination": "Cuttack",
        "departure_time": departure.isoformat(),
        "expected_return": ret.isoformat()
    }, headers=headers_student)

    assert resp.status_code == 200
    gp_id = resp.json()["id"]

    db = SessionLocal()
    from app.db.models import GatePass
    gp = db.query(GatePass).filter(GatePass.id == gp_id).first()
    assert gp is not None

    oc = db.query(OperationalCase).filter(
        OperationalCase.linked_entity_type == "GatePass",
        OperationalCase.linked_entity_id == gp_id
    ).first()

    assert oc is not None
    assert oc.domain == "SAFETY"
    assert oc.service_type == "GATE_PASS"
    db.close()


def test_operations_api_list_cases(auth_tokens):
    """Admin can list operational cases via API."""
    headers_admin = {"Authorization": f"Bearer {auth_tokens['admin']}"}
    resp = client.get("/api/operations/cases", headers=headers_admin)
    assert resp.status_code == 200
    cases = resp.json()
    assert isinstance(cases, list)


def test_operations_api_pulse(auth_tokens):
    """Campus Pulse endpoint returns valid data."""
    headers_admin = {"Authorization": f"Bearer {auth_tokens['admin']}"}
    resp = client.get("/api/operations/metrics/pulse", headers=headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert "overall" in data
    assert "breakdown" in data
    assert 0 <= data["overall"] <= 100


def test_operations_api_slo_metrics(auth_tokens):
    """SLO metrics endpoint returns valid data."""
    headers_admin = {"Authorization": f"Bearer {auth_tokens['admin']}"}
    resp = client.get("/api/operations/metrics/slo", headers=headers_admin)
    assert resp.status_code == 200
    assert "slo_compliance_pct" in resp.json()


def test_operations_api_zero_chase(auth_tokens):
    """Zero-chase endpoint returns valid data."""
    headers_admin = {"Authorization": f"Bearer {auth_tokens['admin']}"}
    resp = client.get("/api/operations/metrics/zero-chase", headers=headers_admin)
    assert resp.status_code == 200
    assert "zero_chase_compliance_pct" in resp.json()
