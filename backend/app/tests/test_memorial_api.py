"""忌日全链路：越界拒写、跳格生成、快照钉周、全员忌日保格、对调收紧门禁。"""

import pytest
from fastapi import HTTPException

from app import main
from app.engines.rota import build_week_slots


WEEK = 1


def _board():
    return main.week_board(WEEK)


def _assignment_map(board):
    return {(a["day"], a["task_id"]): a["member_id"] for a in board["assignments"]}


def _swap_status(swap_id):
    from app.db import connect
    c = connect()
    s = c.execute("SELECT status FROM swap_requests WHERE id=?", (swap_id,)).fetchone()["status"]
    c.close()
    return s


def _set_memorial(mid, days):
    return main.put_member_memorial(mid, main.MemorialBody(days=days))


# ---------- 无忌日回退 ----------

def test_generate_no_memorial_matches_legacy(tmp_db):
    resp = main.generate(WEEK, main.GenBody(days=7))
    legacy = build_week_slots([1, 2, 3], [1, 2, 3], days=7)
    assert resp["slots"] == legacy
    assert resp["memorial_snapshot"] == {}
    board = _board()
    assert board["memorial_snapshot"] == {}
    assert _assignment_map(board) == {(s["day"], s["task_id"]): s["member_id"] for s in legacy}


# ---------- 有忌日跳人 + 快照 ----------

def test_generate_with_memorial_skips_and_snapshots(tmp_db):
    _set_memorial(1, [0])
    resp = main.generate(WEEK, main.GenBody(days=7))
    # day0 任何格子都没有成员 1
    assert all(not (s["day"] == 0 and s["member_id"] == 1) for s in resp["slots"])
    # day0 首格（t1）由下一位成员 2 承接，相位继续前进（day1 t1 落到 3）
    first = next(s for s in resp["slots"] if s["day"] == 0 and s["task_id"] == 1)
    nxt = next(s for s in resp["slots"] if s["day"] == 1 and s["task_id"] == 1)
    assert first["member_id"] == 2 and nxt["member_id"] == 3
    # 快照随生成回包，且看板回看同钉
    assert resp["memorial_snapshot"] == {"1": [0]}
    assert _board()["memorial_snapshot"] == {"1": [0]}


# ---------- 全员忌日取舍：整次失败、保持原格 ----------

def test_all_unavailable_fails_and_keeps_original_grid(tmp_db):
    main.generate(WEEK, main.GenBody(days=7))
    before = _board()
    before_grid = _assignment_map(before)
    before_snapshot = before["memorial_snapshot"]
    for mid in (1, 2, 3):
        _set_memorial(mid, [2])
    with pytest.raises(HTTPException) as ei:
        main.generate(WEEK, main.GenBody(days=7))
    assert ei.value.status_code == 400 and ei.value.detail == "all_unavailable"
    after = _board()
    assert _assignment_map(after) == before_grid  # 原格不动
    assert after["memorial_snapshot"] == before_snapshot  # 旧快照不被覆盖
    assert after["week"]["status"] == "ready"


# ---------- 越界拒写 ----------

@pytest.mark.parametrize("bad", [[-1], [7], [0, 7]])
def test_out_of_range_rejected_and_member_unchanged(tmp_db, bad):
    with pytest.raises(HTTPException) as ei:
        _set_memorial(1, bad)
    assert ei.value.status_code == 400 and ei.value.detail == "memorial_day_out_of_range"
    members = {m["id"]: m for m in main.list_members()}
    assert members[1]["memorial_days"] == []


def test_valid_then_invalid_keeps_prior(tmp_db):
    _set_memorial(1, [3, 4])
    with pytest.raises(HTTPException):
        _set_memorial(1, [9])
    members = {m["id"]: m for m in main.list_members()}
    assert members[1]["memorial_days"] == [3, 4]


# ---------- 现行收紧不回刷已生成周 ----------

def test_changing_current_memorial_does_not_repaint_generated_week(tmp_db):
    _set_memorial(1, [0])
    main.generate(WEEK, main.GenBody(days=7))
    pinned_board = _board()
    pinned_grid = _assignment_map(pinned_board)
    # 现行忌日改为 day6：已生成周的格位与快照都不得回刷
    _set_memorial(1, [6])
    again = _board()
    assert again["memorial_snapshot"] == {"1": [0]}
    assert _assignment_map(again) == pinned_grid


# ---------- 现行收紧后对调门禁 ----------

def test_swap_request_blocked_after_tightening_without_change(tmp_db):
    main.generate(WEEK, main.GenBody(days=7))
    _set_memorial(1, [1])  # 成员1 不得进入 day1
    # day0/t1 占用人是 1，与 day1/t2 占用人 2 对调会把 1 派进 day1
    with pytest.raises(HTTPException) as ei:
        main.request_swap(WEEK, main.SwapBody(a_day=0, a_task=1, b_day=1, b_task=2))
    assert ei.value.status_code == 400 and ei.value.detail == "memorial_blocked"
    # 未落申请
    from app.db import connect
    c = connect()
    n = c.execute("SELECT COUNT(*) n FROM swap_requests").fetchone()["n"]
    c.close()
    assert n == 0
    # 原表不动
    grid = _assignment_map(_board())
    assert grid[(0, 1)] == 1 and grid[(1, 2)] == 2


def test_pending_swap_confirm_blocked_after_tightening(tmp_db):
    main.generate(WEEK, main.GenBody(days=7))
    # 收紧前申请合法（1→day1、2→day0 无忌日）
    sid = main.request_swap(
        WEEK, main.SwapBody(a_day=0, a_task=1, b_day=1, b_task=2)
    )["id"]
    _set_memorial(1, [1])  # 随后收紧
    with pytest.raises(HTTPException) as ei:
        main.confirm_swap(sid)
    assert ei.value.status_code == 400 and ei.value.detail == "memorial_blocked"
    # 表不改、申请仍 pending
    grid = _assignment_map(_board())
    assert grid[(0, 1)] == 1 and grid[(1, 2)] == 2
    assert _swap_status(sid) == "pending"


def test_swap_within_safe_days_confirms(tmp_db):
    main.generate(WEEK, main.GenBody(days=7))
    _set_memorial(1, [1])
    # 两格都在 day0：1、2 目标日均为 0，不触忌日
    sid = main.request_swap(
        WEEK, main.SwapBody(a_day=0, a_task=1, b_day=0, b_task=2)
    )["id"]
    assert main.confirm_swap(sid)["ok"] is True
    grid = _assignment_map(_board())
    assert grid[(0, 1)] == 2 and grid[(0, 2)] == 1
