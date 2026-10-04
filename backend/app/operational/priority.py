SAFETY_KEYWORDS = ["spark", "fire", "shock", "exposed wire", "electrical hazard", "gas leak"]
HIGH_URGENCY_KEYWORDS = ["no water", "no power", "flood", "broken door", "medical", "emergency"]


def calculate_priority(
    service_type: str,
    domain: str,
    text: str,
    context: dict,
    blast_scope: str = None,
    affected_count: int = 1
) -> str:
    text_lower = text.lower()

    if any(kw in text_lower for kw in SAFETY_KEYWORDS):
        return "P0"
    if context.get("student_at_gate") or context.get("physically_waiting"):
        return "P0"

    if context.get("deadline_minutes") and context["deadline_minutes"] <= 30:
        if service_type in ["FEE_ISSUE", "EXAM_REGISTRATION"]:
            return "P0"

    if any(kw in text_lower for kw in HIGH_URGENCY_KEYWORDS):
        return "P1"

    if blast_scope in ["FLOOR", "BUILDING", "HOSTEL"] and affected_count >= 50:
        return "P1"

    if context.get("deadline_minutes") and context["deadline_minutes"] <= 120:
        return "P1"

    return "P2"
