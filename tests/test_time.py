from datetime import datetime

import pytest

from scheduler.service import SchedulerService


@pytest.mark.parametrize("text, expected", [
    ("2026-10-09 15:30", datetime(2026, 10, 9, 15, 30)),
    ("2026-10-09 15:30:45", datetime(2026, 10, 9, 15, 30, 45)),
    ("11:30", datetime(2026, 10, 8, 11, 30)),
    ("09:30", datetime(2026, 10, 9, 9, 30)),
    ("11:30:45", datetime(2026, 10, 8, 11, 30, 45)),
    ("明天上午10点", datetime(2026, 10, 9, 10)),
    ("后天14点30分", datetime(2026, 10, 10, 14, 30)),
    (" 11:30 ", datetime(2026, 10, 8, 11, 30)),
    ("10:00", datetime(2026, 10, 8, 10)),
    ("00:00", datetime(2026, 10, 9)),
    ("23:59:59", datetime(2026, 10, 8, 23, 59, 59)),
    ("明天0点", datetime(2026, 10, 9)),
    pytest.param("2026-02-30 12:00", None, marks=pytest.mark.xfail(
        strict=True, raises=AssertionError,
        reason="已知缺陷：非法完整日期被降级解析成当天时间",
    )),
    ("无法解析", None),
    ("", None),
])
def test_parse_time(text, expected, fixed_clock):
    assert SchedulerService._parse_time(text) == expected


@pytest.mark.xfail(strict=True, reason="已知缺陷：未将下午转换为24小时制")
def test_afternoon(fixed_clock):
    assert SchedulerService._parse_time("下午3点") == datetime(2026, 10, 8, 15)


@pytest.mark.parametrize("text", ["25点", "14点99分"])
@pytest.mark.xfail(strict=True, reason="已知缺陷：非法时分抛异常而不是返回None")
def test_invalid_clock(text, fixed_clock):
    assert SchedulerService._parse_time(text) is None


@pytest.mark.xfail(strict=True, reason="已知缺陷：接受已过去的完整日期")
def test_past_date(fixed_clock):
    assert SchedulerService._parse_time("2026-10-07 15:30") is None
