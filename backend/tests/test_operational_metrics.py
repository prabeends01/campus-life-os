import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.operational.metrics import calculate_friction_score
from app.db.models_operational import OperationalCase


class TestFrictionScore:
    def test_zero_friction_fresh_case(self):
        case = OperationalCase(
            handoff_count=0,
            student_follow_up_count=0,
            reopen_count=0,
            created_at=None
        )
        score = calculate_friction_score(case)
        assert 0 <= score <= 100

    def test_high_friction_many_handoffs(self):
        case = OperationalCase(
            handoff_count=5,
            student_follow_up_count=3,
            reopen_count=2,
            created_at=None
        )
        score = calculate_friction_score(case)
        assert score > 0
        assert score <= 100

    def test_moderate_friction(self):
        case = OperationalCase(
            handoff_count=2,
            student_follow_up_count=1,
            reopen_count=0,
            created_at=None
        )
        score = calculate_friction_score(case)
        assert 0 <= score <= 100
