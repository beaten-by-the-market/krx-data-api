"""관리종목(시가총액·주가 미달) 지정/해제 판정 로직.

근거 규정 (2026 개정 반영):
- 규정 제53조제1항제5호   시가총액 미달: 시총 300억원 미만이 연속 30 매매거래일 → 지정
- 규정 제53조제1항제5호의2 주가 미달  : 종가 1,000원 미만이 연속 30 매매거래일 → 지정
- 세칙 제51조①           종가가 없으면 그날의 기준가격으로 판정
                          (KRX all_stock_price의 TDD_CLSPRC는 무거래일에도 기준가격이
                           채워지므로 별도 소스 없이 그대로 사용)
- 해제(별표10)            기준 이상인 상태가 연속 45 매매거래일 → 그 다음날 해제

핵심 규칙:
- 두 사유는 서로 독립적으로 판정한다.
- 미달 = 값 < 기준(strict). 이상 = 값 >= 기준.
- 연속 카운트는 중간에 반대 상태가 하루라도 끼면 0으로 리셋한다.
- 지정일/해제일 = 조건 충족 해당일의 "다음 매매거래일"(익일).
- 신규상장 종목은 상장 첫날부터 카운트한다(시계열 첫 행이 곧 상장 첫날).

이 모듈은 순수 판정 로직만 담는다(네트워크 없음). 시세 데이터를 받아
`run_state_machine`에 넣는 계층은 별도(M2 데이터 로더)에서 조립한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional, Sequence

# 규정 기준값
MKTCAP_THRESHOLD = 30_000_000_000  # 시가총액 300억원
PRICE_THRESHOLD = 1_000            # 종가 1,000원
DESIGNATE_DAYS = 30                # 지정: 연속 미달 매매거래일 수
RELEASE_DAYS = 45                  # 해제: 연속 이상 매매거래일 수
PRICE_DELIST_WINDOW_DAYS = 90      # 주가미달 상폐(가): 회복 유예 매매거래일 수
REVERSE_SPLIT_RATIO_CAP = 10.0     # 주가미달 상폐(다): 누적 병합/감자 비율(old:new) 상한(초과 시 상폐)
REVERSE_SPLIT_LOOKBACK_DAYS = 365  # 주가미달 상폐(나): 과거 이력 조회 기간(달력 1년)
MKTCAP_DELIST_WINDOW_DAYS = 90     # 시총미달 상폐(제54조12호): 회복 유예 매매거래일 수
MKTCAP_RECOVERY_CONSEC_DAYS = 10   # 시총미달 상폐 회복 '가': 기준 이상 연속 일수
MKTCAP_RECOVERY_CUMUL_DAYS = 30    # 시총미달 상폐 회복 '나': 기준 이상 누적 일수

DESIGNATE = "designate"
RELEASE = "release"

NORMAL = "normal"
SUPERVISED = "supervised"

# evaluate_price_recovery_failure 결과 상태
RECOVERED = "회복"              # 창 내 연속 45거래일 이상 1000원↑ 달성 → 상폐 아님
DELIST_CONFIRMED = "상폐확정"     # 90거래일 다 지났는데 회복 실패
DELIST_EARLY = "조기상폐확정"     # 남은 거래일로는 45연속이 수학적으로 불가(세칙 §51②)
WATCHING = "관찰중"             # 창 미경과, 아직 회복 가능
NO_DATA = "데이터없음"           # 지정일 이후 데이터 없음


@dataclass(frozen=True)
class SupervisionEvent:
    """지정 또는 해제 이벤트 하나.

    kind           : "designate"(지정) 또는 "release"(해제)
    trigger_date   : 연속 조건이 충족된 해당일(지정=30번째 미달일, 해제=45번째 이상일)
    effective_date : 실제 발효일(익일=다음 매매거래일). 시계열이 trigger에서 끝나
                     다음 거래일이 아직 없으면 None("익일 예정/미도래").
    streak         : 충족된 연속 일수(보통 30 또는 45)
    value          : trigger_date의 판정 값(종가 또는 시가총액)
    """

    kind: str
    trigger_date: Any
    effective_date: Any
    streak: int
    value: Any


def run_state_machine(
    series: Sequence[tuple[Any, Any]],
    threshold,
    *,
    designate_days: int = DESIGNATE_DAYS,
    release_days: int = RELEASE_DAYS,
    initial_state: str = NORMAL,
) -> list[SupervisionEvent]:
    """단일 종목·단일 사유의 일별 시계열을 지정/해제 이벤트로 변환한다.

    Parameters
    ----------
    series : (date, value) 튜플의 시퀀스. **오름차순(과거→현재)** 매매거래일만.
        value 가 None 이면 그 날은 판정에서 제외한다(카운트 증가도 리셋도 하지 않음).
        상장 전/상장폐지 후의 결측(피벗 NaN)을 자연스럽게 건너뛰기 위한 처리로,
        결과적으로 카운트는 값이 처음 존재하는 날(=상장 첫날)부터 시작된다.
    threshold : 기준값(scalar) 또는 **날짜별 함수** `f(date)->기준값`. 후자는 부칙의
        시기별 시총 임계값처럼 날짜마다 기준이 다를 때 쓴다.
        미달 = value < 기준, 이상 = value >= 기준.
    initial_state : 창 시작 시점의 상태. 이미 관리종목으로 알려진 종목은
        SUPERVISED 로 시작해 해제(45일) 카운트부터 돌린다.

    Returns
    -------
    발생 순서대로의 SupervisionEvent 리스트. 지정↔해제가 번갈아 나올 수 있다.
    """
    if initial_state not in (NORMAL, SUPERVISED):
        raise ValueError(f"initial_state must be {NORMAL!r} or {SUPERVISED!r}")

    state = initial_state
    deficient_streak = 0   # NORMAL에서 연속 미달 일수
    sufficient_streak = 0  # SUPERVISED에서 연속 이상 일수
    events: list[SupervisionEvent] = []

    thr_fn = threshold if callable(threshold) else (lambda _d: threshold)
    n = len(series)
    for i in range(n):
        date, value = series[i]
        if value is None:
            # 데이터 없는 날: 판정 제외(연속성 유지, 리셋도 증가도 안 함).
            continue

        below = value < thr_fn(date)  # 미달 여부(날짜별 기준 가능)

        if state == NORMAL:
            if below:
                deficient_streak += 1
                if deficient_streak >= designate_days:
                    events.append(
                        SupervisionEvent(
                            kind=DESIGNATE,
                            trigger_date=date,
                            effective_date=_next_trading_day(series, i),
                            streak=deficient_streak,
                            value=value,
                        )
                    )
                    state = SUPERVISED
                    sufficient_streak = 0
            else:
                deficient_streak = 0
        else:  # SUPERVISED
            if not below:  # 이상
                sufficient_streak += 1
                if sufficient_streak >= release_days:
                    events.append(
                        SupervisionEvent(
                            kind=RELEASE,
                            trigger_date=date,
                            effective_date=_next_trading_day(series, i),
                            streak=sufficient_streak,
                            value=value,
                        )
                    )
                    state = NORMAL
                    deficient_streak = 0
            else:  # 미달 → 해제 카운트 리셋
                sufficient_streak = 0

    return events


def _next_trading_day(series: Sequence[tuple[Any, Any]], i: int) -> Any:
    """i번째 다음에 오는 매매거래일(익일). 없으면 None.

    시계열의 다음 행이 곧 다음 매매거래일이므로 값 유무와 무관하게 그 날짜를 쓴다
    (거래정지로 값이 있어도 그 날은 매매거래일이다). 다음 행 자체가 없으면
    익일이 아직 데이터에 없다는 뜻이라 None을 반환한다.
    """
    j = i + 1
    if j < len(series):
        return series[j][0]
    return None


@dataclass(frozen=True)
class StockSupervisionResult:
    """한 종목에 대한 두 사유(시총·주가) 판정 결과."""

    mktcap_events: list[SupervisionEvent]
    price_events: list[SupervisionEvent]

    @property
    def all_events(self) -> list[SupervisionEvent]:
        return self.mktcap_events + self.price_events


def evaluate_stock(
    dates: Sequence[Any],
    closes: Sequence[Optional[float]],
    mktcaps: Sequence[Optional[float]],
    *,
    mktcap_threshold: float = MKTCAP_THRESHOLD,
    price_threshold: float = PRICE_THRESHOLD,
    designate_days: int = DESIGNATE_DAYS,
    release_days: int = RELEASE_DAYS,
    mktcap_initial_state: str = NORMAL,
    price_initial_state: str = NORMAL,
) -> StockSupervisionResult:
    """한 종목의 일별 종가·시가총액 시계열로 두 사유를 각각 판정한다.

    dates/closes/mktcaps 는 같은 길이의 **오름차순** 시퀀스. 값이 없으면 None.
    """
    if not (len(dates) == len(closes) == len(mktcaps)):
        raise ValueError("dates, closes, mktcaps must have equal length")

    price_series = list(zip(dates, closes))
    mktcap_series = list(zip(dates, mktcaps))

    price_events = run_state_machine(
        price_series,
        price_threshold,
        designate_days=designate_days,
        release_days=release_days,
        initial_state=price_initial_state,
    )
    mktcap_events = run_state_machine(
        mktcap_series,
        mktcap_threshold,
        designate_days=designate_days,
        release_days=release_days,
        initial_state=mktcap_initial_state,
    )
    return StockSupervisionResult(mktcap_events=mktcap_events, price_events=price_events)


@dataclass(frozen=True)
class RecoveryFailureResult:
    """제54조①13.가(주가미달 상폐: 회복 실패) 판정 결과.

    status         : RECOVERED / DELIST_CONFIRMED / DELIST_EARLY / WATCHING / NO_DATA
    max_recovery_run : 창 내 관찰된 최장 연속 '이상'(종가>=기준) 거래일 수
    recovered_on   : 연속 recovery_days 달성한 날(회복 확정일). 미달성이면 None
    window_start   : 실제 창 시작 거래일(지정일 이후 첫 거래일)
    window_end     : 창의 마지막 거래일(window_days째). 아직 도래 안 했으면 None
    observed_days  : 창 안에서 실제로 관찰된 거래일 수
    """

    status: str
    max_recovery_run: int
    recovered_on: Any
    window_start: Any
    window_end: Any
    observed_days: int


def evaluate_price_recovery_failure(
    dates: Sequence[Any],
    closes: Sequence[Optional[float]],
    designation_date: Any,
    *,
    price_threshold: float = PRICE_THRESHOLD,
    window_days: int = PRICE_DELIST_WINDOW_DAYS,
    recovery_days: int = RELEASE_DAYS,
) -> RecoveryFailureResult:
    """규정 제54조①13.가: 주가미달 관리종목 지정 후 window_days(90) 매매거래일 이내에
    종가가 price_threshold(1,000원) 이상인 상태가 연속 recovery_days(45) 매매거래일
    이상 계속되지 못하면 상장폐지.

    dates/closes: 오름차순 일별 시계열(거래일만). designation_date 이후의 창을 본다.
    designation_date: 주가미달 관리종목 지정일. **dates와 같은 형식/타입**이어야 한다
        (YYYYMMDD 문자열이면 designation_date도 YYYYMMDD 문자열). 호출자가 형식을 맞춘다.
        실제 사용 시 KRX supervised의 최초지정일(FST_DESIGN_DD, '2026/07/21')을 캐시
        일자 형식('20260721')으로 정규화해 앵커로 쓰면 정확하다.

    판정:
    - 창 안에서 연속 recovery_days 이상 '이상'이 나오면 RECOVERED(상폐 아님).
    - window_days 거래일이 다 관찰됐는데 회복 못하면 DELIST_CONFIRMED.
    - 창이 아직 안 끝났어도 남은 거래일로는 recovery_days 연속이 불가능하면
      DELIST_EARLY(세칙 §51② 조기 확정).
    - 그 외 아직 회복 가능하면 WATCHING.
    """
    if not (len(dates) == len(closes)):
        raise ValueError("dates, closes must have equal length")

    # 지정일 이후(포함) 거래일만, 앞에서 window_days개까지가 창.
    # dates와 designation_date는 같은 형식이어야 한다(YYYYMMDD 문자열 등).
    window = [
        (d, c) for d, c in zip(dates, closes) if d >= designation_date
    ][:window_days]
    if not window:
        return RecoveryFailureResult(NO_DATA, 0, None, None, None, 0)

    window_start = window[0][0]
    observed_days = len(window)
    window_end = window[-1][0] if observed_days >= window_days else None

    # 창 내 최장 연속 '이상' 런과 첫 회복(recovery_days째) 달성일.
    run = 0
    max_run = 0
    recovered_on = None
    for d, c in window:
        if c is not None and c >= price_threshold:
            run += 1
            if run > max_run:
                max_run = run
            if run == recovery_days and recovered_on is None:
                recovered_on = d
        else:
            run = 0

    if recovered_on is not None:
        status = RECOVERED
    elif observed_days >= window_days:
        status = DELIST_CONFIRMED
    else:
        # 남은 거래일 + 현재 진행 중인 말미 런으로도 recovery_days에 못 미치면 조기확정.
        trailing = run  # 관찰 끝 시점의 진행 중 '이상' 런
        remaining = window_days - observed_days
        status = WATCHING if trailing + remaining >= recovery_days else DELIST_EARLY

    return RecoveryFailureResult(
        status=status,
        max_recovery_run=max_run,
        recovered_on=recovered_on,
        window_start=window_start,
        window_end=window_end,
        observed_days=observed_days,
    )


@dataclass(frozen=True)
class MktcapRecoveryResult:
    """제54조①12호(시총미달 상폐) 판정 결과.

    status         : RECOVERED / DELIST_CONFIRMED / DELIST_EARLY / WATCHING / NO_DATA
    max_consec     : 창 내 최장 연속 '이상'(시총>=기준) 거래일 수
    cumulative     : 창 내 '이상' 누적 거래일 수
    recovered_by   : '가'(연속 consec) 또는 '나'(누적 cumul) 최초 충족 사유('가'/'나'/None)
    window_start / window_end / observed_days : 창 정보
    """

    status: str
    max_consec: int
    cumulative: int
    recovered_by: Any
    window_start: Any
    window_end: Any
    observed_days: int


def evaluate_mktcap_recovery_failure(
    dates: Sequence[Any],
    caps: Sequence[Optional[float]],
    designation_date: Any,
    threshold,
    *,
    window_days: int = MKTCAP_DELIST_WINDOW_DAYS,
    consec_days: int = MKTCAP_RECOVERY_CONSEC_DAYS,
    cumul_days: Optional[int] = MKTCAP_RECOVERY_CUMUL_DAYS,
) -> MktcapRecoveryResult:
    """시가총액 미달로 관리종목 지정된 후 window_days(90) 매매거래일 동안 시가총액
    회복조건을 충족 못하면 상장폐지. 시장별로 회복조건이 다르다:

    - 유가(제48조①9호): 기준 이상이 **45일 연속**(consec_days=45, cumul_days=None).
    - 코스닥(제54조①12호): 기준 이상 **10일 연속(가) 또는 누적 30일(나)** 중 하나.

    consec_days : '연속' 회복 일수. cumul_days : '누적' 회복 일수(None이면 누적조건 없음).
    threshold : 기준액(scalar) 또는 날짜별 함수 f(date)->기준액(부칙 시기별 기준용).
    caps : 시가총액 시계열(None=매매거래일 아님/스킵).
    designation_date : 시총미달 지정일(dates와 같은 형식).
    """
    thr_fn = threshold if callable(threshold) else (lambda _d: threshold)
    window = [
        (d, c) for d, c in zip(dates, caps) if d >= designation_date
    ][:window_days]
    if not window:
        return MktcapRecoveryResult(NO_DATA, 0, 0, None, None, None, 0)

    window_start = window[0][0]
    observed_days = len(window)
    window_end = window[-1][0] if observed_days >= window_days else None

    consec = 0
    max_consec = 0
    cumulative = 0
    trailing_consec = 0
    recovered_by = None
    for d, c in window:
        if c is not None and c >= thr_fn(d):  # 기준 이상
            consec += 1
            cumulative += 1
            if consec > max_consec:
                max_consec = consec
            if recovered_by is None:
                if consec >= consec_days:
                    recovered_by = "가"
                elif cumul_days is not None and cumulative >= cumul_days:
                    recovered_by = "나"
        else:
            consec = 0
        trailing_consec = consec

    if recovered_by is not None:
        status = RECOVERED
    elif observed_days >= window_days:
        status = DELIST_CONFIRMED
    else:
        remaining = window_days - observed_days
        # 남은 기간으로 '가'(연속 consec) 또는 '나'(누적 cumul) 달성 가능한가?
        can_consec = (trailing_consec + remaining) >= consec_days or remaining >= consec_days
        can_cumul = cumul_days is not None and (cumulative + remaining) >= cumul_days
        status = WATCHING if (can_consec or can_cumul) else DELIST_EARLY

    return MktcapRecoveryResult(
        status=status,
        max_consec=max_consec,
        cumulative=cumulative,
        recovered_by=recovered_by,
        window_start=window_start,
        window_end=window_end,
        observed_days=observed_days,
    )


def _to_dt(yyyymmdd: Any) -> datetime:
    return datetime.strptime(str(yyyymmdd).replace("/", "").replace("-", "")[:8], "%Y%m%d")


@dataclass(frozen=True)
class ReverseSplitDelistingResult:
    """제54조①13.나·다(주식병합·자본감소로 인한 주가미달 상폐) 판정 결과.

    na : 나 성립 여부(지정 후 90거래일 내 병합/감자 변경상장 + 지정 전 1년 내에도 있었음)
    da : 다 성립 여부(지정 후 90거래일 내 병합/감자 변경상장 누적비율 10:1 초과)
    cumulative_ratio : 창 내 병합/감자의 누적(곱) old:new 비율
    within_window : 창(지정~90거래일) 내 이벤트 수
    in_past_year  : 지정 전 1년 내 이벤트 수
    delist : na or da (13호 나·다에 의한 상폐 사유 발생)
    """

    na: bool
    da: bool
    delist: bool
    cumulative_ratio: float
    within_window: int
    in_past_year: int


def evaluate_reverse_split_delisting(
    designation_date: Any,
    window_end_date: Optional[Any],
    events: Iterable[dict],
    *,
    ratio_cap: float = REVERSE_SPLIT_RATIO_CAP,
    lookback_days: int = REVERSE_SPLIT_LOOKBACK_DAYS,
) -> ReverseSplitDelistingResult:
    """규정 제54조①13.나·다: 주가미달 관리종목이 주식병합/자본감소 변경상장으로
    상장폐지되는 경우.

    나: 지정 후 90거래일 이내에 병합/감자 변경상장을 완료했고, 지정일로부터
        과거 1년(달력) 이내에도 병합/감자 변경상장이 있었던 경우.
    다: 지정 후 90거래일 이내에 병합/감자 변경상장을 1회 이상 완료했고, 그 누적
        비율(old:new의 곱)이 10:1을 초과하는 경우.

    Parameters
    ----------
    designation_date : 주가미달 지정일(YYYYMMDD 등).
    window_end_date : 지정 후 90거래일째 날짜(거래일 캘린더로 계산해 넘김). 아직
        도래하지 않았으면 None → 지정일 이후 이벤트를 열린 구간으로 본다.
    events : 병합/감자 **변경상장** 이벤트들. 각 dict은
        {"date": 변경상장일(YYYYMMDD, kind 기준), "ratio": old:new 비율(float, >=1)}.
        (예: 5:1 병합이면 ratio=5.0. SEIBro STK_FIX_RATIO=new/old이므로 1/값으로 변환.)
    """
    dd = _to_dt(designation_date)
    we = _to_dt(window_end_date) if window_end_date else None
    floor = dd - timedelta(days=lookback_days)

    within = []
    past = []
    for e in events:
        ed = _to_dt(e["date"])
        if ed > dd and (we is None or ed <= we):
            within.append(e)
        elif floor <= ed < dd:
            past.append(e)

    cumulative = 1.0
    for e in within:
        cumulative *= float(e["ratio"])

    na = bool(within) and bool(past)
    da = bool(within) and cumulative > ratio_cap
    return ReverseSplitDelistingResult(
        na=na,
        da=da,
        delist=na or da,
        cumulative_ratio=cumulative if within else 0.0,
        within_window=len(within),
        in_past_year=len(past),
    )
