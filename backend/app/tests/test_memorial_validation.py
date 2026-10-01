import pytest

from app.modules.memorial.validation import (
    MemorialDayError,
    normalize_days,
    unavailable_map,
)


def test_valid_edges_and_dedup_sort():
    assert normalize_days([]) == []
    assert normalize_days(None) == []
    assert normalize_days([0, 6]) == [0, 6]  # 一周内边界
    assert normalize_days([3, 1, 3, 0]) == [0, 1, 3]  # 去重排序
    assert normalize_days((5,)) == [5]


@pytest.mark.parametrize("bad", [-1, 7, 100, ["1"], [1.5], [True], "012", 3])
def test_out_of_range_or_bad_type_rejected(bad):
    with pytest.raises(MemorialDayError):
        normalize_days(bad)


def test_bool_is_not_int_day():
    with pytest.raises(MemorialDayError):
        normalize_days([False, True])


def test_unavailable_map_drops_empty():
    m = unavailable_map({1: [0, 0, 6], 2: [], 3: [2]})
    assert m == {1: {0, 6}, 3: {2}}
