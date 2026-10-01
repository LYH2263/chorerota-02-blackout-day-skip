"""Taboo-day persistence: live member taboos + per-week snapshots.

Two tables (created in seed.init_db):
  member_taboos(member_id, day)           — the current/live taboo set
  week_taboos(week_id, member_id, day)    — snapshot frozen at generation time

Already-generated weeks read only the snapshot; editing the live set never
re-writes history.
"""
from app.engines.taboos import taboos_by_member


def load_taboos(c) -> dict[int, set[int]]:
    """Live taboo set for all members: {member_id: {day, ...}}."""
    rows = [(r["member_id"], r["day"]) for r in c.execute("SELECT member_id, day FROM member_taboos")]
    return taboos_by_member(rows)


def replace_member_taboos(c, member_id: int, days: list[int]) -> None:
    """Replace one member's live taboo set. Caller validates first and commits."""
    c.execute("DELETE FROM member_taboos WHERE member_id=?", (member_id,))
    c.executemany("INSERT INTO member_taboos(member_id, day) VALUES (?,?)",
                  [(member_id, d) for d in days])


def snapshot_week_taboos(c, week_id: int, taboos: dict[int, set[int]]) -> None:
    """Freeze the taboo set that constrained this week's grid. Caller commits."""
    c.execute("DELETE FROM week_taboos WHERE week_id=?", (week_id,))
    c.executemany(
        "INSERT INTO week_taboos(week_id, member_id, day) VALUES (?,?,?)",
        [(week_id, mid, d) for mid, days in taboos.items() for d in sorted(days)])


def load_week_taboos(c, week_id: int) -> dict[int, list[int]]:
    """This week's frozen snapshot: {member_id: [day, ...] sorted}."""
    rows = [(r["member_id"], r["day"]) for r in c.execute(
        "SELECT member_id, day FROM week_taboos WHERE week_id=? ORDER BY member_id, day", (week_id,))]
    grouped = taboos_by_member(rows)
    return {mid: sorted(days) for mid, days in grouped.items()}
