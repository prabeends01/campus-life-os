import pytest
import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.operational.sla import compute_sla_state
from app.db.models_operational import SLAInstance, SLAPolicy


class MockPolicy:
    at_risk_threshold_pct = 0.80


class TestSLAState:
    def test_on_track_fresh(self):
        sla = SLAInstance(
            started_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=1),
            ack_due_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=9),
            sla_state="ON_TRACK"
        )
        sla.sla_policy = MockPolicy()
        state = compute_sla_state(sla, datetime.datetime.utcnow())
        assert state == "ON_TRACK"

    def test_at_risk_80_percent(self):
        sla = SLAInstance(
            started_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=9),
            ack_due_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=1),
            sla_state="ON_TRACK"
        )
        sla.sla_policy = MockPolicy()
        state = compute_sla_state(sla, datetime.datetime.utcnow())
        assert state == "AT_RISK"

    def test_breached_ack_overdue(self):
        sla = SLAInstance(
            started_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=15),
            ack_due_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=5),
            acknowledged_at=None,
            sla_state="ON_TRACK"
        )
        sla.sla_policy = MockPolicy()
        state = compute_sla_state(sla, datetime.datetime.utcnow())
        assert state == "BREACHED"

    def test_met_when_resolved(self):
        sla = SLAInstance(
            started_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
            ack_due_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=50),
            acknowledged_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=40),
            resolved_at=datetime.datetime.utcnow(),
            sla_state="ON_TRACK"
        )
        sla.sla_policy = MockPolicy()
        state = compute_sla_state(sla, datetime.datetime.utcnow())
        assert state == "MET"

    def test_paused_when_reason_set(self):
        sla = SLAInstance(
            started_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
            ack_due_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=50),
            sla_state="BREACHED",
            pause_reason="Awaiting spare parts"
        )
        sla.sla_policy = MockPolicy()
        state = compute_sla_state(sla, datetime.datetime.utcnow())
        assert state == "PAUSED"
