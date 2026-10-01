"""Taboo-day (忌日) validation: pure functions, no I/O."""

DAYS_PER_WEEK = 7  # legal taboo days are 0..6


def validate_taboo_days(days, max_days: int = DAYS_PER_WEEK) -> list[int]:
    """Normalize a taboo-day list to sorted unique ints; reject out-of-range.

    Raises ValueError("taboo_day_out_of_range") on anything outside [0, max_days)
    or non-integer input — callers must treat this as reject-the-whole-save.
    """
    out = set()
    for d in days or []:
        if isinstance(d, bool) or not isinstance(d, int) or d < 0 or d >= max_days:
            raise ValueError("taboo_day_out_of_range")
        out.add(d)
    return sorted(out)


def taboos_by_member(rows) -> dict[int, set[int]]:
    """Group (member_id, day) rows into {member_id: {day, ...}}."""
    out: dict[int, set[int]] = {}
    for member_id, day in rows:
        out.setdefault(member_id, set()).add(day)
    return out
