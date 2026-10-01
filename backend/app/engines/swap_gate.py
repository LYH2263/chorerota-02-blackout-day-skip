"""Swap gating against taboo days: a swap may not seat anyone on their taboo day."""


def swap_taboo_violation(slots: list[dict], a_day: int, a_task: int, b_day: int, b_task: int,
                         taboos: dict[int, set[int]]) -> dict:
    """Check the hypothetical post-swap grid against the given taboo set.

    After swapping, A's member would sit on b_day and B's member on a_day;
    either landing on their own taboo day rejects the swap. Callers decide
    which taboo set to pass (live set for new/confirming swaps).
    """
    def find(day, task):
        for s in slots:
            if s["day"] == day and s["task_id"] == task:
                return s
        return None

    sa, sb = find(a_day, a_task), find(b_day, b_task)
    if sa is None or sb is None:
        return {"ok": False, "reason": "slot_missing"}
    if b_day in taboos.get(sa["member_id"], ()):
        return {"ok": False, "reason": "taboo_violation",
                "member_id": sa["member_id"], "day": b_day}
    if a_day in taboos.get(sb["member_id"], ()):
        return {"ok": False, "reason": "taboo_violation",
                "member_id": sb["member_id"], "day": a_day}
    return {"ok": True, "reason": ""}
