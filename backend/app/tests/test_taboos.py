"""Taboo-day feature tests: 无忌日回退 / 有忌日跳人 / 全员忌日取舍 / 越界拒写 / 对调门禁 / 快照钉住.

Pure-python asserts (no pytest imports) so the file also runs under a plain
interpreter harness; pytest discovers it unchanged.
"""
import os
import tempfile

from app.engines.rota import build_week_slots, AllTabooDayError
from app.engines.taboos import validate_taboo_days
from app.engines.swap_gate import swap_taboo_violation


def _raises(fn, exc):
    try:
        fn()
    except exc as e:
        return e
    return None


# --- 无忌日回退: no taboos → output identical to pre-change legacy ---
def test_no_taboo_matches_legacy():
    legacy = build_week_slots([1, 2, 3], [10, 20], days=7)
    assert build_week_slots([1, 2, 3], [10, 20], days=7, taboos=None) == legacy
    assert build_week_slots([1, 2, 3], [10, 20], days=7, taboos={}) == legacy
    assert build_week_slots([1, 2, 3], [10, 20], days=7, taboos={1: set(), 2: set()}) == legacy


# --- 有忌日跳人: taboo member skipped, next member takes cell, phase advances ---
def test_taboo_skips_member_and_phase_advances():
    slots = build_week_slots([1, 2, 3], [10, 20], days=2, taboos={2: {0}})
    # day0: t10→1, t20 skips 2 →3; day1: phase continues 1, 2 (2 not taboo on day1)
    assert [s["member_id"] for s in slots] == [1, 3, 1, 2]
    assert all(not (s["member_id"] == 2 and s["day"] == 0) for s in slots)


def test_taboo_on_later_day_skips_midweek():
    slots = build_week_slots([1, 2], [10], days=3, taboos={1: {1}})
    # day0→1, day1 skips 1 →2, day2 phase continues →1
    assert [s["member_id"] for s in slots] == [1, 2, 1]


# --- 全员忌日取舍: whole generation fails (AllTabooDayError), caller keeps old grid ---
def test_all_taboo_day_raises():
    e = _raises(lambda: build_week_slots([1, 2], [10], days=1, taboos={1: {0}, 2: {0}}),
                AllTabooDayError)
    assert e is not None and e.day == 0


def test_all_taboo_midweek_raises_with_day():
    e = _raises(lambda: build_week_slots([1, 2], [10], days=7, taboos={1: {3}, 2: {3}}),
                AllTabooDayError)
    assert e is not None and e.day == 3


# --- 越界拒写: out-of-range taboo days rejected ---
def test_validate_taboo_days_ok():
    assert validate_taboo_days([2, 0, 6, 2]) == [0, 2, 6]
    assert validate_taboo_days([]) == []
    assert validate_taboo_days(None) == []


def test_validate_taboo_days_rejects_out_of_range():
    for bad in ([7], [-1], [0, 7], [1.5], ["3"], [True]):
        e = _raises(lambda: validate_taboo_days(bad), ValueError)
        assert e is not None and str(e) == "taboo_day_out_of_range", bad


# --- 对调门禁: swap seating someone on their taboo day fails ---
def test_swap_gate_blocks_taboo_seating():
    slots = [{"day": 0, "task_id": 10, "member_id": 1},
             {"day": 1, "task_id": 10, "member_id": 2}]
    # swap would seat member 2 on day 0, their taboo day
    r = swap_taboo_violation(slots, 0, 10, 1, 10, {2: {0}})
    assert r["ok"] is False and r["reason"] == "taboo_violation" and r["member_id"] == 2
    # member 1 taboo on day 1: swap would seat member 1 there
    r = swap_taboo_violation(slots, 0, 10, 1, 10, {1: {1}})
    assert r["ok"] is False and r["member_id"] == 1


def test_swap_gate_allows_clean_swap():
    slots = [{"day": 0, "task_id": 10, "member_id": 1},
             {"day": 1, "task_id": 10, "member_id": 2}]
    assert swap_taboo_violation(slots, 0, 10, 1, 10, {})["ok"] is True
    assert swap_taboo_violation(slots, 0, 10, 1, 10, {1: {0}, 2: {1}})["ok"] is True  # already seated there
    r = swap_taboo_violation(slots, 0, 10, 9, 10, {})
    assert r["ok"] is False and r["reason"] == "slot_missing"


# --- 落库 + 快照钉住 + 拒写不改档 (temp DB) ---
def test_store_roundtrip_snapshot_and_reject():
    from app import seed
    from app.db import connect
    from app.taboos_store import (load_taboos, replace_member_taboos,
                                  snapshot_week_taboos, load_week_taboos)
    with tempfile.TemporaryDirectory() as d:
        os.environ["DATA_DIR"] = d
        seed.init_db()
        c = connect()
        # live set roundtrip
        replace_member_taboos(c, 1, [1, 3])
        c.commit()
        assert load_taboos(c)[1] == {1, 3}
        # 越界拒写: validation fails before any write → member record unchanged
        assert _raises(lambda: validate_taboo_days([1, 9]), ValueError) is not None
        assert load_taboos(c)[1] == {1, 3}
        # 生成快照钉住当周; 之后收紧/清空现行忌日不回刷已生成周
        snapshot_week_taboos(c, 1, {1: {1, 3}, 2: {0}})
        c.commit()
        replace_member_taboos(c, 1, [])
        c.commit()
        assert load_week_taboos(c, 1) == {1: [1, 3], 2: [0]}
        assert load_taboos(c).get(1, set()) == set()
        c.close()


def test_all_taboo_generation_keeps_existing_grid():
    """取舍落地: engine raises → endpoint writes nothing → old grid + no snapshot."""
    from app import seed
    from app.db import connect
    with tempfile.TemporaryDirectory() as d:
        os.environ["DATA_DIR"] = d
        seed.init_db()
        c = connect()
        c.execute("INSERT INTO assignments(week_id,day,task_id,member_id) VALUES (1,0,1,1)")
        c.commit()
        taboos = {1: {0}, 2: {0}, 3: {0}}  # all seeded active-clean members taboo day 0
        e = _raises(lambda: build_week_slots([1, 2, 3], [1, 2, 3], days=7, taboos=taboos),
                    AllTabooDayError)
        assert e is not None and e.day == 0
        rows = c.execute("SELECT * FROM assignments WHERE week_id=1").fetchall()
        assert len(rows) == 1 and rows[0]["member_id"] == 1  # 保持原格
        assert c.execute("SELECT COUNT(*) c FROM week_taboos").fetchone()["c"] == 0
        c.close()
