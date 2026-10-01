import pytest

from app.engines.rota import build_week_slots, AllMembersUnavailableError


def test_no_memorial_matches_legacy_grid():
    """无忌日时格位与改造前 round-robin 逐格一致。"""
    legacy = build_week_slots([1, 2, 3], [10, 20], days=7)
    gated = build_week_slots([1, 2, 3], [10, 20], days=7, unavailable={})
    assert gated == legacy
    # 空集合成员不影响
    gated2 = build_week_slots([1, 2, 3], [10, 20], days=7, unavailable={2: set()})
    assert gated2 == legacy
    assert [s["member_id"] for s in legacy[:4]] == [1, 2, 3, 1]


def test_memorial_skips_person_and_phase_advances():
    """成员 1 忌日 day0：day0 该格由下一位承接，相位继续前进。"""
    slots = build_week_slots([1, 2, 3], [10], days=4, unavailable={1: {0}})
    by_day = {s["day"]: s["member_id"] for s in slots}
    assert by_day[0] == 2  # 1 跳过 → 2 承接
    assert by_day[1] == 3  # 相位继续：之后是 3
    assert by_day[2] == 1  # 非忌日 1 正常回岗
    assert by_day[3] == 2
    assert 1 not in [s["member_id"] for s in slots if s["day"] == 0]


def test_memorial_blocks_every_slot_of_that_day():
    """该成员不得出现在对应 day 的任何格子（多任务）。"""
    slots = build_week_slots([1, 2, 3], [10, 20, 30], days=3, unavailable={2: {1}})
    day1_members = {s["member_id"] for s in slots if s["day"] == 1}
    assert 2 not in day1_members


def test_multiple_blocked_same_day_rolls_to_next_available():
    slots = build_week_slots([1, 2, 3], [10], days=3, unavailable={1: {0}, 2: {0}})
    by_day = {s["day"]: s["member_id"] for s in slots}
    assert by_day[0] == 3  # 1、2 均忌日 → 3
    assert by_day[1] == 1  # 相位已推进，day1 回到 1


def test_all_members_unavailable_raises_and_caller_keeps_grid():
    """某 day 全员忌日：抛 all_unavailable，不产生部分结果（原格由调用方保留）。"""
    with pytest.raises(AllMembersUnavailableError) as ei:
        build_week_slots([1, 2, 3], [10], days=3, unavailable={1: {2}, 2: {2}, 3: {2}})
    assert ei.value.reason == "all_unavailable"
    assert ei.value.day == 2
