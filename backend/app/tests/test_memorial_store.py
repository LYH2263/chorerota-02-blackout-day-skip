import json

import pytest

from app.modules.memorial import store
from app.modules.memorial.validation import MemorialDayError


def _member_id(c, name):
    return c.execute("SELECT id FROM members WHERE name=?", (name,)).fetchone()["id"]


def test_set_then_get_roundtrip(c):
    mid = _member_id(c, "阿明")
    norm = store.set_member_memorial(c, mid, [3, 3, 0])
    assert norm == [0, 3]
    c.commit()
    assert store.get_member_memorial(c, mid) == [0, 3]


def test_out_of_range_refuses_and_does_not_touch_member(c):
    """越界拒写且不改成员档：先存合法值，再用越界值保存失败，旧值不变。"""
    mid = _member_id(c, "阿明")
    store.set_member_memorial(c, mid, [1, 2]); c.commit()
    before = c.execute("SELECT memorial_days FROM members WHERE id=?", (mid,)).fetchone()["memorial_days"]
    with pytest.raises(MemorialDayError):
        store.set_member_memorial(c, mid, [7])
    c.rollback()
    after = c.execute("SELECT memorial_days FROM members WHERE id=?", (mid,)).fetchone()["memorial_days"]
    assert after == before
    assert store.get_member_memorial(c, mid) == [1, 2]


def test_set_unknown_member_lookup_error(c):
    with pytest.raises(LookupError):
        store.set_member_memorial(c, 9999, [0])


def test_build_and_load_week_snapshot_is_pinned(c):
    """生成时快照钉周；之后改现行忌日，快照不变。"""
    aming = _member_id(c, "阿明")
    xiaoyu = _member_id(c, "小雨")
    store.set_member_memorial(c, aming, [0, 4])
    store.set_member_memorial(c, xiaoyu, [2])
    c.commit()
    snapshot = store.build_snapshot(c, [aming, xiaoyu])
    wid = c.execute("INSERT INTO weeks(label,status) VALUES ('回看周','ready')").lastrowid
    store.save_week_snapshot(c, wid, snapshot)
    c.commit()
    # 现行忌日收紧/改样
    store.set_member_memorial(c, aming, [6]); c.commit()
    loaded = store.load_week_snapshot(c, wid)
    assert loaded == {aming: {0, 4}, xiaoyu: {2}}
    raw = store.week_snapshot_json(c, wid)
    assert raw == {str(aming): [0, 4], str(xiaoyu): [2]}


def test_replace_week_assignments_full_rewrite(c):
    wid = c.execute("SELECT id FROM weeks").fetchone()["id"]
    c.execute("INSERT INTO assignments(week_id,day,task_id,member_id) VALUES (1,0,1,9)")
    c.commit()
    store.replace_week_assignments(c, wid, [
        {"day": 0, "task_id": 1, "member_id": 2},
        {"day": 1, "task_id": 1, "member_id": 3},
    ])
    c.commit()
    rows = c.execute("SELECT day,member_id FROM assignments WHERE week_id=? ORDER BY day", (wid,)).fetchall()
    assert [dict(r) for r in rows] == [{"day": 0, "member_id": 2}, {"day": 1, "member_id": 3}]
