import threading
import time
import datetime
from app.db.session import SessionLocal
from app.db.models_operational import OperationalCase, SLAInstance
from app.operational.sla import compute_sla_state
from app.operational.escalation import execute_escalation


class SLAMonitor:
    def __init__(self, interval_seconds=30):
        self.interval = interval_seconds
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while self._running:
            self._check_all()
            time.sleep(self.interval)

    def _check_all(self):
        db = SessionLocal()
        try:
            now = datetime.datetime.utcnow()
            active_cases = db.query(OperationalCase).filter(
                OperationalCase.status.notin_(["RESOLVED", "CLOSED", "CANCELLED"])
            ).all()

            state_changed = False
            for case in active_cases:
                sla = db.query(SLAInstance).filter(
                    SLAInstance.operational_case_id == case.id
                ).first()
                if not sla:
                    continue

                old_state = sla.sla_state
                new_state = compute_sla_state(sla, now)

                if new_state != old_state:
                    sla.sla_state = new_state
                    sla.updated_at = now
                    state_changed = True

                    if new_state == "BREACHED":
                        execute_escalation(db, case, sla, "SLA_BREACH")

            if state_changed:
                db.commit()
        finally:
            db.close()


_sla_monitor = SLAMonitor(interval_seconds=30)


def start_sla_monitor():
    _sla_monitor.start()


def stop_sla_monitor():
    _sla_monitor.stop()
