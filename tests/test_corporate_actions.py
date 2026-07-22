"""SEIBro 병합/감자 어댑터의 순수 파싱부 테스트 (네트워크 없음)."""
from __future__ import annotations

from krx_data_api import corporate_actions as ca


def test_parse_ratio_converts_new_over_old_to_old_over_new():
    # STK_FIX_RATIO = new/old. '.2' → 5:1
    assert ca.parse_ratio(".2") == 5.0
    assert ca.parse_ratio("0.1") == 10.0
    assert ca.parse_ratio("0.05") == 20.0


def test_parse_ratio_handles_blank_and_bad():
    for bad in (None, "", "-", "nan", "None", "0", "abc"):
        assert ca.parse_ratio(bad) is None


def test_parse_ratio_strips_commas():
    # 방어적: 콤마 섞인 값
    assert ca.parse_ratio("0.20") == 5.0
