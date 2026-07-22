"""관리종목 판정 상태기계(순수함수) 단위 테스트.

라이브 네트워크 불필요. `pytest tests/test_supervision.py`
"""
from __future__ import annotations

import pytest

from krx_data_api.supervision import (
    DELIST_CONFIRMED,
    DELIST_EARLY,
    DESIGNATE,
    NO_DATA,
    NORMAL,
    RECOVERED,
    RELEASE,
    SUPERVISED,
    WATCHING,
    SupervisionEvent,
    evaluate_mktcap_recovery_failure,
    evaluate_price_recovery_failure,
    evaluate_reverse_split_delisting,
    evaluate_stock,
    run_state_machine,
)

THR = 1000  # 테스트용 기준값(주가 미달과 동일 수치)


def series(values, start=1):
    """정수 일련번호를 날짜 대용으로 쓰는 (date, value) 시계열 생성."""
    return [(start + i, v) for i, v in enumerate(values)]


# ---------------------------------------------------------------- 지정(30일)

def test_exactly_30_consecutive_deficient_triggers_designation():
    s = series([999] * 30)
    events = run_state_machine(s, THR, designate_days=30, release_days=45)
    assert len(events) == 1
    e = events[0]
    assert e.kind == DESIGNATE
    assert e.streak == 30
    assert e.trigger_date == 30          # 30번째 미달일
    assert e.effective_date is None      # 익일이 시계열에 아직 없음 → 미도래
    assert e.value == 999


def test_29_deficient_does_not_trigger():
    s = series([999] * 29)
    assert run_state_machine(s, THR) == []


def test_effective_date_is_next_trading_day():
    # 30일 미달 후 하루가 더 있으면 그 날이 익일(발효일)
    s = series([999] * 30 + [1500])
    events = run_state_machine(s, THR)
    assert len(events) == 1
    assert events[0].trigger_date == 30
    assert events[0].effective_date == 31


def test_boundary_31st_day_not_double_counted():
    # 31일 연속 미달이라도 지정은 30번째에서 한 번만.
    s = series([999] * 31)
    events = run_state_machine(s, THR)
    assert len(events) == 1
    assert events[0].trigger_date == 30


# ---------------------------------------------------------------- 리셋

def test_one_sufficient_day_resets_deficient_streak():
    # 29일 미달 → 하루 이상(리셋) → 다시 29일 미달: 어느 구간도 30 미충족
    s = series([999] * 29 + [1000] + [999] * 29)
    assert run_state_machine(s, THR) == []


def test_reset_then_fresh_30_triggers():
    # 리셋 후 새로 30일 채우면 지정
    s = series([999] * 10 + [1200] + [999] * 30)
    events = run_state_machine(s, THR)
    assert len(events) == 1
    # 리셋 이후 새 카운트: index 11(0-based)부터 30일째 = date 41
    assert events[0].trigger_date == 41


def test_threshold_is_strict_below():
    # 정확히 기준값(1000)은 '이상'이므로 미달 아님 → 지정 없음
    s = series([1000] * 60)
    assert run_state_machine(s, THR) == []


# ---------------------------------------------------------------- 해제(45일)

def test_designate_then_45_sufficient_releases():
    s = series([999] * 30 + [1500] * 45)
    events = run_state_machine(s, THR)
    kinds = [e.kind for e in events]
    assert kinds == [DESIGNATE, RELEASE]
    release = events[1]
    assert release.streak == 45
    # 지정 후 45일째 이상: date 30 + 45 = 75
    assert release.trigger_date == 75


def test_44_sufficient_does_not_release():
    s = series([999] * 30 + [1500] * 44)
    events = run_state_machine(s, THR)
    assert [e.kind for e in events] == [DESIGNATE]


def test_one_deficient_day_resets_release_streak():
    # 지정 후 44일 이상 → 하루 미달(리셋) → 44일 이상: 해제 미충족
    s = series([999] * 30 + [1500] * 44 + [999] + [1500] * 44)
    events = run_state_machine(s, THR)
    assert [e.kind for e in events] == [DESIGNATE]


def test_release_then_redesignation():
    # 지정 → 해제 → 다시 30일 미달 → 재지정
    s = series([999] * 30 + [1500] * 45 + [999] * 30)
    events = run_state_machine(s, THR)
    assert [e.kind for e in events] == [DESIGNATE, RELEASE, DESIGNATE]


# ---------------------------------------------------------------- initial_state

def test_initial_supervised_counts_release_first():
    # 이미 관리종목이면 SUPERVISED로 시작 → 45일 이상만으로 해제
    s = series([1500] * 45)
    events = run_state_machine(s, THR, initial_state=SUPERVISED)
    assert [e.kind for e in events] == [RELEASE]


def test_initial_supervised_stays_if_deficient_continues():
    s = series([999] * 60)
    events = run_state_machine(s, THR, initial_state=SUPERVISED)
    assert events == []  # 계속 미달이면 해제도 (재)지정도 없음


# ---------------------------------------------------------------- None 처리

def test_none_values_are_skipped_not_reset():
    # 상장 전 결측(None) 15일 → 이후 30일 미달: 지정. None은 리셋 아님.
    s = series([None] * 15 + [999] * 30)
    events = run_state_machine(s, THR)
    assert len(events) == 1
    assert events[0].streak == 30


def test_none_between_deficient_days_preserves_streak():
    # 미달 중간에 데이터 없는 날이 껴도 연속으로 간주(스킵), 30일 채우면 지정
    s = series([999] * 20 + [None] * 3 + [999] * 10)
    events = run_state_machine(s, THR)
    assert len(events) == 1
    assert events[0].streak == 30


def test_counting_starts_at_first_non_none_listing_day():
    # 신규상장 시뮬: 앞은 None, 상장 첫날부터 카운트 → 정확히 30일째 지정
    s = series([None] * 5 + [999] * 30, start=1)
    events = run_state_machine(s, THR)
    # None 5개 뒤 첫 값은 date 6, 30일째 = date 35
    assert events[0].trigger_date == 35


# ---------------------------------------------------------------- evaluate_stock

def test_evaluate_stock_independent_reasons():
    dates = list(range(1, 31))
    closes = [500] * 30          # 주가 미달 30일 → 주가 지정
    mktcaps = [9_999_999_999_999] * 30  # 시총 넉넉(기준 이상) → 시총 지정 없음
    res = evaluate_stock(dates, closes, mktcaps)
    assert [e.kind for e in res.price_events] == [DESIGNATE]
    assert res.mktcap_events == []


def test_evaluate_stock_both_reasons_fire():
    dates = list(range(1, 31))
    closes = [500] * 30
    mktcaps = [10_000_000_000] * 30  # 100억 < 300억 → 시총도 미달
    res = evaluate_stock(dates, closes, mktcaps)
    assert [e.kind for e in res.price_events] == [DESIGNATE]
    assert [e.kind for e in res.mktcap_events] == [DESIGNATE]
    assert len(res.all_events) == 2


def test_evaluate_stock_length_mismatch_raises():
    with pytest.raises(ValueError):
        evaluate_stock([1, 2], [1000], [1, 2])


def test_invalid_initial_state_raises():
    with pytest.raises(ValueError):
        run_state_machine(series([999]), THR, initial_state="bogus")


# ------------------------------------------ 제54조13가: 주가미달 상폐(회복 실패)

def _dates(n, start=1):
    return list(range(start, start + n))


def test_recovery_success_within_window():
    # 지정(day1) 후 창 안에서 45연속 1000원 이상 → 회복(상폐 아님)
    dates = _dates(90)
    closes = [500] * 20 + [1500] * 45 + [500] * 25  # 21~65일 회복
    res = evaluate_price_recovery_failure(dates, closes, designation_date=1,
                                          window_days=90, recovery_days=45)
    assert res.status == RECOVERED
    assert res.recovered_on == 65  # 21부터 45일째 = 65
    assert res.max_recovery_run == 45


def test_delist_confirmed_when_window_elapsed_no_recovery():
    # 90거래일 다 지났는데 45연속 이상 못 만듦 → 상폐확정
    dates = _dates(90)
    closes = ([1500] * 44 + [500]) * 2  # 44연속만 반복, 45 못 채움
    res = evaluate_price_recovery_failure(dates, closes, designation_date=1)
    assert res.status == DELIST_CONFIRMED
    assert res.max_recovery_run == 44
    assert res.window_end == 90


def test_watching_when_window_not_elapsed():
    # 아직 30거래일만 관찰, 회복 가능성 남음 → 관찰중
    dates = _dates(30)
    closes = [500] * 30
    res = evaluate_price_recovery_failure(dates, closes, designation_date=1)
    assert res.status == WATCHING
    assert res.window_end is None
    assert res.observed_days == 30


def test_early_delist_when_recovery_impossible():
    # 46거래일 지났고 전부 미달 → 남은 44거래일로는 45연속 불가 → 조기상폐확정
    dates = _dates(46)
    closes = [500] * 46
    res = evaluate_price_recovery_failure(dates, closes, designation_date=1)
    # 남은 = 90-46 = 44, trailing run = 0 → 44 < 45 → 조기확정
    assert res.status == DELIST_EARLY


def test_early_delist_boundary_still_watching():
    # 45거래일 지남, 남은 45 → 딱 45연속 가능 → 아직 관찰중
    dates = _dates(45)
    closes = [500] * 45
    res = evaluate_price_recovery_failure(dates, closes, designation_date=1)
    assert res.status == WATCHING


def test_recovery_run_broken_by_one_below_day():
    # 44 이상 → 하루 미달 → 다시 이상: 연속 끊겨 45 미달성
    dates = _dates(90)
    closes = [1500] * 44 + [999] + [1500] * 45
    res = evaluate_price_recovery_failure(dates, closes, designation_date=1)
    # 뒤쪽 45연속(46~90)이 성립 → 회복
    assert res.status == RECOVERED
    assert res.recovered_on == 90


def test_designation_date_anchors_window():
    # 지정일 이전 데이터는 창에서 제외
    dates = _dates(100)
    closes = [1500] * 50 + [500] * 50  # 51일부터 미달
    # 지정일=51 → 창은 51~90(=40거래일 관찰, 전부 미달), 창 미경과
    res = evaluate_price_recovery_failure(dates, closes, designation_date=51)
    assert res.window_start == 51
    assert res.max_recovery_run == 0


def test_recovery_no_data_after_designation():
    dates = _dates(10)
    closes = [500] * 10
    res = evaluate_price_recovery_failure(dates, closes, designation_date=999)
    assert res.status == NO_DATA


# ------------------------------------------ 제54조13 나·다: 병합/감자 상폐

def test_na_repeat_reverse_split_within_year():
    # 지정 20260601. 지정 후 병합(20260701), 지정 전 1년 내에도 병합(20260201) → 나 성립
    events = [
        {"date": "20260701", "ratio": 3.0},   # 지정 후 90일 내
        {"date": "20260201", "ratio": 2.0},   # 지정 전 1년 내
    ]
    res = evaluate_reverse_split_delisting("20260601", "20261001", events)
    assert res.na is True
    assert res.delist is True
    assert res.within_window == 1 and res.in_past_year == 1


def test_na_fails_without_past_year_event():
    events = [{"date": "20260701", "ratio": 3.0}]  # 지정 후만 있음
    res = evaluate_reverse_split_delisting("20260601", "20261001", events)
    assert res.na is False


def test_na_past_event_older_than_one_year_excluded():
    # 지정 전 이벤트가 1년 넘게 과거면 나 불성립
    events = [
        {"date": "20260701", "ratio": 3.0},
        {"date": "20250401", "ratio": 2.0},   # 20260601 기준 1년 초과
    ]
    res = evaluate_reverse_split_delisting("20260601", "20261001", events)
    assert res.na is False
    assert res.in_past_year == 0


def test_da_cumulative_ratio_exceeds_cap():
    # 창 내 5:1 두 번 → 누적 25:1 > 10 → 다 성립
    events = [
        {"date": "20260701", "ratio": 5.0},
        {"date": "20260801", "ratio": 5.0},
    ]
    res = evaluate_reverse_split_delisting("20260601", "20261001", events)
    assert res.da is True
    assert res.cumulative_ratio == 25.0
    assert res.delist is True


def test_da_not_triggered_at_or_below_cap():
    # 정확히 10:1은 '초과' 아님 → 다 불성립
    events = [{"date": "20260701", "ratio": 10.0}]
    res = evaluate_reverse_split_delisting("20260601", "20261001", events)
    assert res.da is False


def test_da_single_split_over_cap():
    events = [{"date": "20260701", "ratio": 12.0}]  # 12:1 > 10
    res = evaluate_reverse_split_delisting("20260601", "20261001", events)
    assert res.da is True


def test_events_outside_window_ignored_for_da():
    # 창(90거래일=window_end 20261001) 밖 이벤트는 다 계산 제외
    events = [{"date": "20261115", "ratio": 20.0}]  # 창 종료 후
    res = evaluate_reverse_split_delisting("20260601", "20261001", events)
    assert res.da is False
    assert res.within_window == 0


def test_open_window_when_end_none():
    # window_end None이면 지정 이후 이벤트는 모두 창 내로 간주
    events = [{"date": "20270101", "ratio": 15.0}]
    res = evaluate_reverse_split_delisting("20260601", None, events)
    assert res.da is True
    assert res.within_window == 1


# ------------------------------------------ 제54조12호: 시총미달 상폐(회복 실패)

THR2 = 20_000_000_000  # 200억


def test_mktcap_recovery_via_consecutive_10():
    # 지정 후 10거래일 연속 기준 이상 → 회복(가)
    dates = _dates(90)
    caps = [1] * 20 + [THR2] * 10 + [1] * 60  # 21~30일 연속 이상
    res = evaluate_mktcap_recovery_failure(dates, caps, 1, THR2)
    assert res.status == RECOVERED
    assert res.recovered_by == "가"


def test_mktcap_recovery_via_cumulative_30():
    # 연속은 10 안 되지만(9씩) 누적 이상이 30일 → 회복(나)
    dates = _dates(90)
    block = [THR2] * 9 + [1]  # 9 이상 + 1 미달, 연속 최대 9
    caps = (block * 4)[:90]   # 이상 누적 36일, 연속 최대 9
    res = evaluate_mktcap_recovery_failure(dates, caps, 1, THR2)
    assert res.status == RECOVERED
    assert res.recovered_by == "나"
    assert res.max_consec < 10


def test_mktcap_delist_confirmed_no_recovery():
    # 90일 다 지났는데 이상이 연속10·누적30 둘 다 미달 → 상폐확정
    dates = _dates(90)
    # 이상을 8일마다 1번씩만(누적 ~11, 연속 1) → 회복 실패
    caps = [THR2 if (i % 8 == 0) else 1 for i in range(90)]
    res = evaluate_mktcap_recovery_failure(dates, caps, 1, THR2)
    assert res.status == DELIST_CONFIRMED
    assert res.max_consec < 10 and res.cumulative < 30


def test_mktcap_watching_before_window_end():
    dates = _dates(20)
    caps = [1] * 20  # 계속 미달, 창 미경과
    res = evaluate_mktcap_recovery_failure(dates, caps, 1, THR2)
    assert res.status == WATCHING


def test_mktcap_early_delist_impossible():
    # 82거래일 지남, 이상 0 → 남은 8일로는 연속10·누적30 불가 → 조기확정
    dates = _dates(82)
    caps = [1] * 82
    res = evaluate_mktcap_recovery_failure(dates, caps, 1, THR2)
    assert res.status == DELIST_EARLY


def test_mktcap_kospi_needs_45_consecutive_no_cumulative():
    # 유가: 회복 = 45연속만(누적조건 없음). 누적 40일이어도 연속 45 안 되면 미회복.
    dates = _dates(90)
    block = [THR2] * 20 + [1] * 5  # 20연속 이상 + 5미달 반복 → 연속 최대 20, 누적 다수
    caps = (block * 4)[:90]
    res = evaluate_mktcap_recovery_failure(dates, caps, 1, THR2, consec_days=45, cumul_days=None)
    assert res.status == DELIST_CONFIRMED   # 45연속 못 채움 → 상폐(누적조건 없음)
    assert res.max_consec == 20
    # 45연속이면 회복
    caps2 = [THR2] * 45 + [1] * 45
    res2 = evaluate_mktcap_recovery_failure(dates, caps2, 1, THR2, consec_days=45, cumul_days=None)
    assert res2.status == RECOVERED and res2.recovered_by == "가"


def test_mktcap_recovery_period_threshold_callable():
    # 날짜별 기준(callable) 지원: 후반 기준이 높아 이상 판정 달라짐
    dates = list(range(1, 41))
    caps = [25_000_000_000] * 40  # 250억
    thr = lambda d: 20_000_000_000 if d <= 20 else 30_000_000_000  # 200억→300억
    # 전반(<=20)은 250>=200 이상, 후반(>20)은 250<300 미달
    res = evaluate_mktcap_recovery_failure(dates, caps, 1, thr, window_days=40)
    # 전반 20일 연속 이상 → '가'(10연속) 이미 충족
    assert res.status == RECOVERED and res.recovered_by == "가"
