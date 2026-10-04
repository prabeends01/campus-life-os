import pytest
import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.operational.priority import calculate_priority


class TestPriorityCalculation:
    def test_p0_safety_keywords(self):
        result = calculate_priority("MAINTENANCE", "HOSTEL", "Exposed wire sparking near ceiling", {})
        assert result == "P0"

    def test_p0_physically_waiting(self):
        result = calculate_priority("GATE_PASS", "SAFETY", "Need gate pass", {"student_at_gate": True})
        assert result == "P0"

    def test_p1_high_urgency_keywords(self):
        result = calculate_priority("MAINTENANCE", "HOSTEL", "No water supply in entire floor", {})
        assert result == "P1"

    def test_p1_deadline_30min(self):
        result = calculate_priority("FEE_ISSUE", "ADMIN", "Exam registration", {"deadline_minutes": 25})
        assert result == "P0"

    def test_p2_default(self):
        result = calculate_priority("MAINTENANCE", "HOSTEL", "Leaking tap in room", {})
        assert result == "P2"

    def test_p1_large_blast_scope(self):
        result = calculate_priority(
            "MAINTENANCE", "HOSTEL", "Water outage",
            {}, blast_scope="FLOOR", affected_count=50
        )
        assert result == "P1"
