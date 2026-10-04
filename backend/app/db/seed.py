import datetime
import json
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, Base, engine
from app.db.models import (
    User, Complaint, ComplaintAuditTrail, GatePass, CertificateRequest,
    Attendance, ScheduleSlot, Notice, NoticeReadReceipt, MessHall, MessMenuItem, MessFeedback
)
from app.db.models_operational import SLAPolicy, EscalationPolicy
from app.auth.security import hash_password


def seed_database():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    already_seeded = db.query(User).first() is not None

    if not already_seeded:
        print("Seeding BPUT Campus Life OS database...")

        student1 = User(
            name="Aarav Sharma",
            email="student@campus.edu",
            password_hash=hash_password("student123"),
            role="STUDENT",
            roll_no="220101045",
            branch="CSE",
            year=3,
            hostel="Aryabhatta Hall",
            room="302",
            phone="+919876543210",
            preferred_language="en"
        )
        student2 = User(
            name="Sneha Mohanty",
            email="student2@campus.edu",
            password_hash=hash_password("student123"),
            role="STUDENT",
            roll_no="220101099",
            branch="CSE",
            year=3,
            hostel="Gargi Hall",
            room="204",
            phone="+919876543211",
            preferred_language="or"
        )
        student3 = User(
            name="Rohan Das",
            email="student3@campus.edu",
            password_hash=hash_password("student123"),
            role="STUDENT",
            roll_no="230102012",
            branch="ECE",
            year=2,
            hostel="Aryabhatta Hall",
            room="302",
            phone="+919876543212",
            preferred_language="hi"
        )

        warden = User(
            name="Dr. K. C. Pradhan",
            email="warden@campus.edu",
            password_hash=hash_password("warden123"),
            role="STAFF",
            hostel="Aryabhatta Hall",
            phone="+919876543220",
            preferred_language="en"
        )
        faculty = User(
            name="Prof. S. N. Jena",
            email="faculty@campus.edu",
            password_hash=hash_password("faculty123"),
            role="STAFF",
            branch="CSE",
            phone="+919876543221",
            preferred_language="en"
        )

        admin = User(
            name="Dr. B. K. Mishra (Dean Admin)",
            email="admin@campus.edu",
            password_hash=hash_password("admin123"),
            role="ADMIN",
            phone="+919876543230",
            preferred_language="en"
        )

        mess_mgr = User(
            name="Ramesh Nayak (Mess In-Charge)",
            email="mess@campus.edu",
            password_hash=hash_password("mess123"),
            role="MESS",
            phone="+919876543240",
            preferred_language="en"
        )

        db.add_all([student1, student2, student3, warden, faculty, admin, mess_mgr])
        db.commit()

        mess1 = MessHall(name="Aryabhatta Boys Mess", hostel_id="Aryabhatta Hall")
        mess2 = MessHall(name="Gargi Girls Dining Hall", hostel_id="Gargi Hall")
        db.add_all([mess1, mess2])
        db.commit()

        today = datetime.date.today()
        m1 = MessMenuItem(mess_hall_id=mess1.id, date=today, meal_type="BREAKFAST", name="Idli, Sambar, Coconut Chutney & Boiled Egg")
        m2 = MessMenuItem(mess_hall_id=mess1.id, date=today, meal_type="LUNCH", name="Steamed Rice, Dalma (Odisha Special), Paneer Curry, Salad & Papad")
        m3 = MessMenuItem(mess_hall_id=mess1.id, date=today, meal_type="SNACKS", name="Aloo Chop & Masala Milk Tea")
        m4 = MessMenuItem(mess_hall_id=mess1.id, date=today, meal_type="DINNER", name="Tawa Roti, Chicken Kassa / Matar Paneer, Dal Fry & Kheer")

        db.add_all([m1, m2, m3, m4])
        db.commit()

        fb1 = MessFeedback(
            student_id=student1.id,
            menu_item_id=m2.id,
            rating=2,
            tags=json.dumps(["cold", "too_salty"]),
            comment="Dalma was served completely cold today and had excess salt. Please fix warming pans."
        )
        fb2 = MessFeedback(
            student_id=student2.id,
            menu_item_id=m2.id,
            rating=5,
            tags=json.dumps(["delicious", "fresh"]),
            comment="Paneer curry was very tasty and fresh!"
        )
        db.add_all([fb1, fb2])
        db.commit()

        now = datetime.datetime.utcnow()
        c1 = Complaint(
            student_id=student1.id,
            category="Plumbing",
            title="Leaking bathroom washbasin tap going on for 9 days",
            description="Washbasin faucet in room washroom has been leaking constantly day and night. Water is accumulating on the tiles.",
            place="Aryabhatta Hall",
            room="302",
            floor="3rd Floor",
            priority="HIGH",
            status="OPEN",
            assigned_to=warden.id,
            created_at=now - datetime.timedelta(days=9)
        )
        c2 = Complaint(
            student_id=student1.id,
            category="Electrical",
            title="Ceiling fan regulator burnt out - only runs at speed 5",
            description="Speed controller sparking when turned and stuck at full speed. Risk of short circuit.",
            place="Aryabhatta Hall",
            room="302",
            floor="3rd Floor",
            priority="HIGH",
            status="ASSIGNED",
            assigned_to=warden.id,
            created_at=now - datetime.timedelta(hours=54)
        )
        c3 = Complaint(
            student_id=student3.id,
            category="Plumbing",
            title="Shower pipe valve broken - no cold water",
            description="Hot water only coming through mixer valve, cold water valve jammed shut.",
            place="Aryabhatta Hall",
            room="302",
            floor="3rd Floor",
            priority="MEDIUM",
            status="IN_PROGRESS",
            assigned_to=warden.id,
            created_at=now - datetime.timedelta(hours=30)
        )
        c4 = Complaint(
            student_id=student1.id,
            category="Plumbing",
            title="Toilet flush tank leaking continuously into pan",
            description="Ballcock valve not shutting off water inlet. Massive water wastage.",
            place="Aryabhatta Hall",
            room="302",
            floor="3rd Floor",
            priority="HIGH",
            status="OPEN",
            created_at=now - datetime.timedelta(days=4)
        )
        c5 = Complaint(
            student_id=student3.id,
            category="Plumbing",
            title="Corridor main washroom line overflow",
            description="Water backing up into 3rd floor corridor outside room 305.",
            place="Aryabhatta Hall",
            room="305",
            floor="3rd Floor",
            priority="CRITICAL",
            status="OPEN",
            created_at=now - datetime.timedelta(minutes=45)
        )

        db.add_all([c1, c2, c3, c4, c5])
        db.commit()

        a1 = ComplaintAuditTrail(
            complaint_id=c2.id,
            action="STATUS_CHANGED",
            performed_by=warden.id,
            previous_status="OPEN",
            new_status="ASSIGNED",
            note="Assigned to Electrical maintenance team. Work order #E-409 generated.",
            timestamp=now - datetime.timedelta(hours=48)
        )
        db.add(a1)
        db.commit()

        approver_chain = [
            {"step": 1, "role": "faculty", "name": "Prof. S. N. Jena", "status": "APPROVED", "timestamp": (now - datetime.timedelta(hours=4)).isoformat(), "note": "Academic attendance verified (78%)"},
            {"step": 2, "role": "warden", "name": "Dr. K. C. Pradhan", "status": "PENDING", "timestamp": None, "note": "Awaiting hostel register verification"},
            {"step": 3, "role": "gate", "name": "Main Gate Security", "status": "PENDING", "timestamp": None, "note": "Pending departure verification"}
        ]
        gp1 = GatePass(
            student_id=student1.id,
            reason="Attending cousin's wedding ceremony and medical checkup",
            destination="Cuttack (Home)",
            departure_time=now + datetime.timedelta(days=1, hours=2),
            expected_return=now + datetime.timedelta(days=3, hours=6),
            approver_chain=json.dumps(approver_chain),
            status="PENDING",
            created_at=now - datetime.timedelta(hours=5)
        )
        db.add(gp1)
        db.commit()

        cert1 = CertificateRequest(
            student_id=student1.id,
            type="BONAFIDE",
            purpose="Application for Passport renewal at Regional Passport Office, Bhubaneswar",
            status="PROCESSING",
            requested_at=now - datetime.timedelta(days=1, hours=4)
        )
        cert2 = CertificateRequest(
            student_id=student1.id,
            type="TRANSCRIPT",
            purpose="Application for Summer Research Internship at IIT Kharagpur",
            status="READY",
            requested_at=now - datetime.timedelta(days=3),
            ready_at=now - datetime.timedelta(hours=6)
        )
        db.add_all([cert1, cert2])
        db.commit()

        slots = [
            ScheduleSlot(course_id="CS301", course_name="Database Management Systems", day_of_week="Monday", start_time="09:00", end_time="10:00", room="LH-101", instructor_name="Prof. S. N. Jena", batch="CSE-2023"),
            ScheduleSlot(course_id="CS302", course_name="Computer Networks", day_of_week="Monday", start_time="10:15", end_time="11:15", room="LH-102", instructor_name="Dr. P. Panda", batch="CSE-2023"),
            ScheduleSlot(course_id="CS303", course_name="Operating Systems", day_of_week="Monday", start_time="11:30", end_time="12:30", room="LH-101", instructor_name="Prof. A. Ray", batch="CSE-2023"),
            ScheduleSlot(course_id="CS304", course_name="Design & Analysis of Algorithms", day_of_week="Monday", start_time="02:00", end_time="04:00", room="Lab-3", instructor_name="Dr. R. K. Behera", batch="CSE-2023"),
            ScheduleSlot(course_id="CS301", course_name="Database Management Systems", day_of_week="Tuesday", start_time="09:00", end_time="10:00", room="LH-101", instructor_name="Prof. S. N. Jena", batch="CSE-2023"),
            ScheduleSlot(course_id="CS302", course_name="Computer Networks", day_of_week="Tuesday", start_time="10:15", end_time="11:15", room="LH-102", instructor_name="Dr. P. Panda", batch="CSE-2023"),
        ]
        db.add_all(slots)
        db.commit()

        for i in range(10):
            d = today - datetime.timedelta(days=i+1)
            st = "PRESENT" if i != 2 else "ABSENT"
            db.add(Attendance(course_id="CS301", student_id=student1.id, session_date=d, status=st, marked_by=faculty.id))

        for i in range(10):
            d = today - datetime.timedelta(days=i+1)
            st = "PRESENT" if i in [0, 1, 3, 5, 7, 9] else "ABSENT"
            db.add(Attendance(course_id="CS302", student_id=student1.id, session_date=d, status=st, marked_by=faculty.id))

        for i in range(10):
            d = today - datetime.timedelta(days=i+1)
            st = "PRESENT" if i not in [4, 8] else "ABSENT"
            db.add(Attendance(course_id="CS303", student_id=student1.id, session_date=d, status=st, marked_by=faculty.id))

        db.commit()

        n1 = Notice(
            title="Mid-Semester Examination Schedule Announced",
            body="Mid-Semester examinations for 3rd and 5th semester B.Tech commence from October 15. Admit cards must be collected from department office.",
            author_id=admin.id,
            target_type="YEAR",
            target_value="3",
            priority="URGENT",
            created_at=now - datetime.timedelta(hours=18)
        )
        n2 = Notice(
            title="Hostel Wi-Fi Upgradation & Scheduled Downtime",
            body="BPUT Central IT will carry out fiber backbone maintenance in Aryabhatta Hall this Saturday between 02:00 AM and 05:00 AM.",
            author_id=admin.id,
            target_type="HOSTEL",
            target_value="Aryabhatta Hall",
            priority="NORMAL",
            created_at=now - datetime.timedelta(hours=36)
        )
        n3 = Notice(
            title="Mandatory Attendance Warning: 75% BPUT Policy",
            body="Students having attendance lower than 75% are immediately barred from appearing in practical evaluations without medical clearance.",
            author_id=admin.id,
            target_type="ALL",
            target_value="ALL",
            priority="CRITICAL",
            created_at=now - datetime.timedelta(days=2)
        )
        db.add_all([n1, n2, n3])
        db.commit()

        rr1 = NoticeReadReceipt(notice_id=n1.id, student_id=student1.id, read_at=now - datetime.timedelta(hours=2), acknowledged_at=now - datetime.timedelta(hours=2))
        db.add(rr1)
        db.commit()

        from app.db.models import CampusMap, MapPin
        cmap = CampusMap(
            glb_path="/models/campus_prototype.glb",
            uploaded_by=admin.id,
            uploaded_at=now,
            is_active=True
        )
        db.add(cmap)
        db.commit()

        pins = [
            MapPin(campus_map_id=cmap.id, label="Administrative Block", description="Dean Offices, Accounts, Bonafide/Transcript Counter #2", x=-5.0, y=0.5, z=2.0),
            MapPin(campus_map_id=cmap.id, label="Academic Block (CSE/ECE)", description="Lecture Halls LH-101 to LH-106 & Computer Labs", x=6.0, y=0.5, z=-3.0),
            MapPin(campus_map_id=cmap.id, label="Central Library", description="Reading Rooms, Digital Library, Book Issue Counter", x=3.0, y=0.5, z=1.0),
            MapPin(campus_map_id=cmap.id, label="Aryabhatta Boys Hostel", description="Residential Block A & B, Warden Office", x=-8.0, y=0.5, z=-7.0),
            MapPin(campus_map_id=cmap.id, label="Gargi Girls Hostel", description="Residential Block G1 & G2", x=-12.0, y=0.5, z=-2.0),
            MapPin(campus_map_id=cmap.id, label="Central Mess Hall", description="Mess Dining, Catering Kitchen", x=-6.0, y=0.5, z=-8.0),
            MapPin(campus_map_id=cmap.id, label="Main Campus Gate", description="Gate Pass Security Scanner, Bus Shuttle Stop", x=0.0, y=0.5, z=10.0),
        ]
        db.add_all(pins)
        db.commit()

        print("Database seeding completed successfully!")
    else:
        print("Database already seeded. Skipping initial data load.")

    # Always seed SLA and escalation policies if they don't exist
    existing_sla = db.query(SLAPolicy).first()
    if not existing_sla:
        sla_policies = [
            SLAPolicy(domain="SAFETY", service_type="GATE_PASS", priority="P0",
                      ack_sla_minutes=2, action_sla_minutes=5, resolution_sla_minutes=10),
            SLAPolicy(domain="SAFETY", service_type="GATE_PASS", priority="P1",
                      ack_sla_minutes=10, action_sla_minutes=20, resolution_sla_minutes=60),
            SLAPolicy(domain="SAFETY", service_type="GATE_PASS", priority="P2",
                      ack_sla_minutes=30, action_sla_minutes=60, resolution_sla_minutes=240),
            SLAPolicy(domain="SAFETY", service_type="GATE_PASS", priority="P3",
                      ack_sla_minutes=60, action_sla_minutes=120, resolution_sla_minutes=480),
            SLAPolicy(domain="HOSTEL", service_type="MAINTENANCE", priority="P0",
                      ack_sla_minutes=5, action_sla_minutes=15, resolution_sla_minutes=60),
            SLAPolicy(domain="HOSTEL", service_type="MAINTENANCE", priority="P1",
                      ack_sla_minutes=30, action_sla_minutes=60, resolution_sla_minutes=240),
            SLAPolicy(domain="HOSTEL", service_type="MAINTENANCE", priority="P2",
                      ack_sla_minutes=60, action_sla_minutes=180, resolution_sla_minutes=720),
            SLAPolicy(domain="HOSTEL", service_type="MAINTENANCE", priority="P3",
                      ack_sla_minutes=120, action_sla_minutes=360, resolution_sla_minutes=1440),
            SLAPolicy(domain="ADMIN", service_type="CERTIFICATE", priority="P0",
                      ack_sla_minutes=15, action_sla_minutes=60, resolution_sla_minutes=180),
            SLAPolicy(domain="ADMIN", service_type="CERTIFICATE", priority="P1",
                      ack_sla_minutes=60, action_sla_minutes=240, resolution_sla_minutes=480),
            SLAPolicy(domain="ADMIN", service_type="CERTIFICATE", priority="P2",
                      ack_sla_minutes=240, action_sla_minutes=480, resolution_sla_minutes=1440),
            SLAPolicy(domain="ADMIN", service_type="CERTIFICATE", priority="P3",
                      ack_sla_minutes=480, action_sla_minutes=1440, resolution_sla_minutes=4320),
            SLAPolicy(domain="ACADEMICS", service_type="ATTENDANCE", priority="P0",
                      ack_sla_minutes=15, action_sla_minutes=30, resolution_sla_minutes=120),
            SLAPolicy(domain="ACADEMICS", service_type="ATTENDANCE", priority="P1",
                      ack_sla_minutes=60, action_sla_minutes=180, resolution_sla_minutes=480),
            SLAPolicy(domain="ACADEMICS", service_type="ATTENDANCE", priority="P2",
                      ack_sla_minutes=180, action_sla_minutes=480, resolution_sla_minutes=1440),
        ]
        db.add_all(sla_policies)

    existing_esc = db.query(EscalationPolicy).first()
    if not existing_esc:
        escalation_policies = [
            EscalationPolicy(domain="SAFETY", service_type="GATE_PASS", priority="P0",
                             trigger="NO_ACK", delay_minutes=2, from_role="HOD", to_role="PRINCIPAL",
                             step_order=1),
            EscalationPolicy(domain="SAFETY", service_type="GATE_PASS", priority="P0",
                             trigger="NO_ACK", delay_minutes=5, from_role="PRINCIPAL", to_role="ADMIN",
                             step_order=2),
            EscalationPolicy(domain="HOSTEL", service_type="MAINTENANCE", priority="P1",
                             trigger="SLA_BREACH", delay_minutes=0, from_role="STAFF", to_role="WARDEN",
                             step_order=1),
            EscalationPolicy(domain="HOSTEL", service_type="MAINTENANCE", priority="P0",
                             trigger="SLA_BREACH", delay_minutes=0, from_role="STAFF", to_role="WARDEN",
                             step_order=1),
            EscalationPolicy(domain="HOSTEL", service_type="MAINTENANCE", priority="P0",
                             trigger="SLA_BREACH", delay_minutes=30, from_role="WARDEN", to_role="ADMIN",
                             step_order=2),
            EscalationPolicy(domain="ADMIN", service_type="CERTIFICATE", priority="P2",
                             trigger="NO_ACTION", delay_minutes=240, from_role="ADMIN", to_role="ADMIN",
                             step_order=1),
            EscalationPolicy(domain="ACADEMICS", service_type="ATTENDANCE", priority="P1",
                             trigger="SLA_BREACH", delay_minutes=0, from_role="FACULTY", to_role="HOD",
                             step_order=1),
        ]
        db.add_all(escalation_policies)

    admin_user = db.query(User).filter(User.role == "ADMIN").first()
    if admin_user:
        from app.db.models import Incident
        from app.db.models_incident import IncidentMember

        now = datetime.datetime.utcnow()

        inc1 = Incident(
            title="Water supply interruption - Old Campus",
            category="Infrastructure",
            place="Old Campus",
            description="Multiple hostels experiencing no water supply since 6 AM. Plumber deployed.",
            status="INVESTIGATING",
            severity="P1",
            service="Water Supply",
            affected_population=3,
            owner_id=admin_user.id,
            started_at=now - datetime.timedelta(hours=2),
            created_at=now - datetime.timedelta(hours=2)
        )
        inc2 = Incident(
            title="Campus WiFi outage - Academic Block",
            category="Network",
            place="Academic Block A",
            description="WiFi connectivity down across all floors. IT team investigating router failure.",
            status="RESOLVED",
            severity="P2",
            service="Network",
            affected_population=5,
            owner_id=admin_user.id,
            started_at=now - datetime.timedelta(days=1),
            created_at=now - datetime.timedelta(days=1),
            resolved_at=now - datetime.timedelta(hours=20)
        )
        inc3 = Incident(
            title="Mess food quality issue",
            category="Mess",
            place="Aryabhatta Boys Mess",
            description="Students reporting food poisoning symptoms after dinner. Mess closed for inspection.",
            status="MONITORING",
            severity="P1",
            service="Mess",
            affected_population=2,
            owner_id=admin_user.id,
            started_at=now - datetime.timedelta(days=2),
            created_at=now - datetime.timedelta(days=2)
        )

        db.add_all([inc1, inc2, inc3])
        db.flush()

        students = db.query(User).filter(User.role == "STUDENT").limit(3).all()
        for i, s in enumerate(students):
            if i == 0 and inc1.id:
                m1 = IncidentMember(
                    incident_id=inc1.id,
                    student_id=s.id,
                    impact_statement="No water in hostel since morning. Cannot bathe or use restroom.",
                    joined_at=now - datetime.timedelta(hours=1)
                )
                db.add(m1)

    db.commit()
    db.close()


if __name__ == "__main__":
    seed_database()
