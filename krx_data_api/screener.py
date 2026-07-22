"""전시장 관리종목 스크리너 + KRX 공식 현황 대조.

`daily_snapshots`가 쌓은 롱 캐시(일자·표준코드·종가·시가총액)를 받아,
종목마다 `supervision.evaluate_stock`을 돌려 지정/해제 이벤트와 현재상태를 뽑는다.
그 결과를 KRX `supervised`(관리종목현황)와 대조해 로직 정확도를 확증한다.

이벤트/상태 산출부는 순수(네트워크 없음)라 테스트 가능하고, 대조부만 라이브
`fetch("supervised")`를 호출한다.
"""
from __future__ import annotations

import time
from typing import Optional

import pandas as pd

from .client import fetch
from . import daily_snapshots as ds
from . import supervision as sv

# 판정 대상 유니버스(보통주권+외국주권+DR)를 얻는 KIND 엔드포인트 설정.
# 시장(mktId) × 증권구분(secugrpId) 조합. KONEX(KNX)·스팩(SP)·리츠·투자회사(MF) 등은
# 애초에 빼서 호출하므로 결과 목록이 곧 규칙 대상이다.
UNIVERSE_MARKETS = ("STK", "KSQ")          # 유가 / 코스닥 (코넥스 제외)
UNIVERSE_SECUGRPS = ("ST", "FS", "DR")     # 주권 / 외국주권 / 주식예탁증권

# 사유 라벨
REASON_MKTCAP = "시가총액"
REASON_PRICE = "주가"

# 시가총액 미달 기준은 시장별 + **부칙 경과규정에 따라 시기별로 단계 적용**된다
# (부칙 2026.5.13 신설, 시행 2026.7.1). 각 날짜가 속한 구간의 기준으로 미달을 판단한다.
#   KOSDAQ(제53조5호):  ~2026.6.30 150억 / 2026.7.1~12.31 200억 / 2027.1.1~ 300억(본칙)
#   KOSPI (제47조9호):   ~2026.6.30 200억 / 2026.7.1~12.31 300억 / 2027.1.1~ 500억(본칙)
#   KONEX: 규칙 없음 → 제외.
# 우선주·외국주 무관하게 각 시장 기준을 동일 적용. 시총 일수는 연속(카운트 시작 제한 없음).
# 구간: (구간시작일 포함, 기준액). 정렬된 상태로 두고 날짜 이상인 마지막 구간을 취한다.
MKTCAP_SCHEDULE = {
    "KOSPI": [("00000000", 20_000_000_000), ("20260701", 30_000_000_000), ("20270101", 50_000_000_000)],
    "KOSDAQ": [("00000000", 15_000_000_000), ("20260701", 20_000_000_000), ("20270101", 30_000_000_000)],
}
# 주가 미달 기준(1,000원)은 KOSPI/KOSDAQ 공통. KONEX는 제외.
PRICE_MARKETS = {"KOSPI", "KOSDAQ"}
# 주가 미달 일수는 **시행일(2026.7.1) 이후 최초로 1,000원 미만인 날부터** 산정(부칙 제3조①).
PRICE_COUNT_START = "20260701"


def mktcap_threshold_won(market: str, date: str) -> Optional[float]:
    """해당 시장·날짜(YYYYMMDD)의 시가총액 미달 기준액(원). 시장 미포함이면 None."""
    sched = MKTCAP_SCHEDULE.get(market)
    if not sched:
        return None
    thr = None
    for start, amt in sched:
        if str(date) >= start:
            thr = amt
    return thr

# 규칙 대상 = 보통주권 + 외국주권 + 외국주식예탁증권(DR) (사용자 확인 2026-07-22).
# 외국주권·DR은 단축코드 900xxx/950xxx로 끝자리가 0이라 아래 우선주 필터에 걸리지 않아
# 자동 포함된다(라이브 검증: 외국·DR 21종목 전부 제외 0).
# 아래 종목군은 규칙 비적용이라 제외:
#   - 스팩(SPAC): 종목명에 "스팩" 포함 (소속부 SPAC 태그의 상위집합, 라이브 확인).
#   - 우선주 등 종류주식: 단축코드 끝자리 != "0" (보통주는 끝자리 0). 전환우선주도 포함되고
#     외국주 보통주(끝자리 0)·SPAC(끝자리 0)은 제외되지 않음 — 라이브 검증.
#   - 리츠(REIT): 종목명이 "리츠"로 끝남 (부분매칭은 '블리츠웨이' 등 오탐이라 접미사로 한정).
#   - 인프라펀드(사회기반시설 투융자회사): 실물 소수라 표준코드 큐레이트. "인프라" 부분매칭은
#     '바이오인프라'(바이오 회사)·'NICE인프라'(일반 회사)를 오탐하므로 쓰지 않는다.
SPAC_NAME_PATTERN = "스팩"
REIT_NAME_SUFFIX = "리츠"
INFRA_FUND_CODES = {
    "KR7088980008",  # 맥쿼리인프라
    "KR7415640002",  # KB발해인프라
}

# supervised.LIST_BZ_RSN_NM 중 보통주 시가총액/주가 미달 사유 라벨.
# 우선주("종류주식 ...")는 별도 조항이고 스크리너에서 제외하므로 대조 대상에서도 뺀다.
KRX_MKTCAP_REASONS = {"시가총액 미달"}
KRX_PRICE_REASONS = {"주가 미달"}

# 카운팅 시작일: 2026.5.13 규정 개정(시총 규칙 개정 + 주가 규칙 신설)으로 임계값/규칙이
# 바뀌었고 그 시점부터 30거래일 미달 카운트가 시작된다(사용자 확인). 개정 전 날짜는
# 미달 판정에서 제외한다. (개정 전 구 임계값을 반영한 "정확한 지정일" 로직은 보류.)
RULE_REVISION_DATE = "20260513"


def _series_none(values) -> list:
    """pandas 값 배열을 evaluate_stock용 리스트로. NaN → None, 그 외 int."""
    out = []
    for v in values:
        if pd.isna(v):
            out.append(None)
        else:
            out.append(int(v))
    return out


def excluded_reason(
    srt_code: str,
    name: str,
    code: str,
    *,
    exclude_spac: bool = True,
    exclude_preferred: bool = True,
    exclude_reit: bool = True,
    exclude_infra_funds: bool = True,
) -> Optional[str]:
    """규칙 비적용 종목이면 제외 사유 문자열, 아니면 None.

    srt_code: 단축코드(6자리), name: 종목명, code: 표준코드(KR7...).
    """
    name = str(name)
    if exclude_spac and SPAC_NAME_PATTERN in name:
        return "스팩"
    if exclude_preferred and str(srt_code)[-1:] != "0":
        return "우선주"  # 종류주식(전환우선주 포함)
    if exclude_reit and name.endswith(REIT_NAME_SUFFIX):
        return "리츠"
    if exclude_infra_funds and code in INFRA_FUND_CODES:
        return "인프라펀드"
    return None


def build_target_universe(
    sel_date: Optional[str] = None,
    *,
    markets=UNIVERSE_MARKETS,
    secugrps=UNIVERSE_SECUGRPS,
    save_csv: Optional[str] = None,
    max_retries: int = 5,
    retry_wait: float = 2.0,
) -> pd.DataFrame:
    """KIND `listed_issue_status`로 규칙 대상 유니버스를 조회한다.

    보통주권(ST)+외국주권(FS)+주식예탁증권(DR)을 유가(STK)·코스닥(KSQ)에서 받아
    합친다. 회사 단위 목록이라 우선주는 안 들어오고, 스팩(SP)·리츠·인프라펀드·
    투자회사(MF)는 secugrpId가 달라 애초에 제외된다. KONEX(KNX)도 호출하지 않는다.

    krx-kind-data-api가 설치돼 있어야 한다(지연 임포트). KIND는 간헐적 SSL 오류가
    있어 조합별로 재시도한다.

    Returns: 구분·시장구분·회사명·종목코드(6자리)·상장일·상장주식수(천주) DataFrame.
    """
    try:
        from krx_kind_data_api import fetch as kfetch
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "build_target_universe requires krx-kind-data-api. "
            "pip install -e ../krx-kind-data-api"
        ) from e

    frames = []
    for m in markets:
        for s in secugrps:
            df = None
            last_err = None
            for _ in range(max_retries):
                try:
                    df = kfetch(
                        "listed_issue_status", selDate=sel_date, mktId=m, secugrpId=s
                    )
                    break
                except Exception as e:  # KIND SSL 간헐 오류 재시도
                    last_err = e
                    time.sleep(retry_wait)
            if df is None:
                raise RuntimeError(f"KIND 조회 실패 mktId={m} secugrpId={s}: {last_err}")
            frames.append(df)

    uni = pd.concat(frames, ignore_index=True)
    # 종목코드 6자리 문자열 정규화(선행 0/영문 보존).
    uni["종목코드"] = uni["종목코드"].astype(str).str.zfill(6)
    uni = uni.drop_duplicates(subset=["종목코드"]).reset_index(drop=True)
    if save_csv is not None:
        import os as _os

        _os.makedirs(_os.path.dirname(_os.path.abspath(save_csv)), exist_ok=True)
        uni.to_csv(save_csv, index=False, encoding="utf-8-sig")
    return uni


def load_target_universe(csv_path: str) -> pd.DataFrame:
    """저장해 둔 유니버스 CSV를 읽는다(종목코드 문자열 보존)."""
    return pd.read_csv(csv_path, dtype={"종목코드": str}, encoding="utf-8-sig")


def target_codes(universe: pd.DataFrame) -> set:
    """유니버스 DataFrame에서 단축코드(종목코드) 집합을 뽑는다."""
    return set(universe["종목코드"].astype(str).str.zfill(6))


def _meta_by_code(cache_df: pd.DataFrame) -> pd.DataFrame:
    """표준코드별 최신 메타(단축코드·종목명·시장)."""
    latest = (
        cache_df.sort_values("일자")
        .groupby("표준코드")
        .tail(1)
        .set_index("표준코드")[["단축코드", "종목명", "시장"]]
    )
    return latest


def _schedule_lookup(sched, date) -> Optional[float]:
    thr = None
    for start, amt in sched:
        if str(date) >= start:
            thr = amt
    return thr


def screen_market(
    cache_df: pd.DataFrame,
    *,
    mktcap_schedule: Optional[dict] = None,
    price_threshold: float = sv.PRICE_THRESHOLD,
    price_markets: Optional[set] = None,
    price_count_start: Optional[str] = PRICE_COUNT_START,
    mktcap_count_start: Optional[str] = None,
    designate_days: int = sv.DESIGNATE_DAYS,
    release_days: int = sv.RELEASE_DAYS,
    universe: Optional[set] = None,
    exclude_spac: bool = True,
    exclude_preferred: bool = True,
    exclude_reit: bool = True,
    exclude_infra_funds: bool = True,
) -> pd.DataFrame:
    """캐시 전체에 대해 종목×사유별 지정/해제 이벤트를 산출한다.

    시가총액 기준은 **시장별 + 시기별(부칙 경과규정)** 로 다르다(MKTCAP_SCHEDULE).
    각 날짜가 속한 구간의 기준으로 미달을 판단한다. KONEX는 규칙이 없어 제외.

    universe : 판정 대상 단축코드 집합(권장). 주면 이 집합에 든 종목만 판정하고
        이름/코드 휴리스틱(exclude_*)은 건너뛴다.
    mktcap_schedule : {시장: [(구간시작YYYYMMDD, 기준액), ...]}. 없으면 MKTCAP_SCHEDULE.
        여기 없는 시장(KONEX 등)은 시가총액 판정에서 제외.
    price_count_start : 주가 미달 카운트 시작일(부칙 제3조① 시행일 2026.7.1). 이 날 이전
        종가는 주가 카운트에서 제외. None이면 제한 없음.
    mktcap_count_start : 시총 미달 카운트 시작 제한(기본 None=연속). 시총은 부칙상
        종전부터 연속 산정하되 기준만 시기별이라 보통 None.

    Returns
    -------
    이벤트 롱 DataFrame: 표준코드·단축코드·종목명·시장·사유(시가총액|주가)·
        종류(designate|release)·판정일·발효일·연속일수·값
    """
    if mktcap_schedule is None:
        mktcap_schedule = MKTCAP_SCHEDULE
    if price_markets is None:
        price_markets = PRICE_MARKETS
    event_columns = [
        "표준코드", "단축코드", "종목명", "시장", "사유",
        "종류", "판정일", "발효일", "연속일수", "값",
    ]
    if cache_df.empty:
        return pd.DataFrame(columns=event_columns)

    close_wide = ds.to_wide(cache_df, "종가")
    cap_wide = ds.to_wide(cache_df, "시가총액").reindex(index=close_wide.index)
    dates = close_wide.index.tolist()
    meta = _meta_by_code(cache_df)

    rows = []
    for code in close_wide.columns:
        m = meta.loc[code] if code in meta.index else None
        market = m["시장"] if m is not None else None

        if universe is not None:
            if m is None or str(m["단축코드"]) not in universe:
                continue
        else:
            if m is not None and excluded_reason(
                m["단축코드"], m["종목명"], code,
                exclude_spac=exclude_spac, exclude_preferred=exclude_preferred,
                exclude_reit=exclude_reit, exclude_infra_funds=exclude_infra_funds,
            ):
                continue

        sched = mktcap_schedule.get(market)
        do_mktcap = sched is not None
        do_price = market in price_markets
        if not (do_mktcap or do_price):
            continue  # KONEX 등

        closes = _series_none(close_wide[code].values)
        caps = (_series_none(cap_wide[code].values)
                if code in cap_wide.columns else [None] * len(dates))

        events_by_reason = []
        if do_mktcap:
            thr_fn = (lambda s: (lambda d: _schedule_lookup(s, d)))(sched)
            cser = [(d, v) for d, v in zip(dates, caps)
                    if mktcap_count_start is None or d >= mktcap_count_start]
            events_by_reason.append((REASON_MKTCAP, sv.run_state_machine(
                cser, thr_fn, designate_days=designate_days, release_days=release_days)))
        if do_price:
            pser = [(d, v) for d, v in zip(dates, closes)
                    if price_count_start is None or d >= price_count_start]
            events_by_reason.append((REASON_PRICE, sv.run_state_machine(
                pser, price_threshold, designate_days=designate_days, release_days=release_days)))

        for reason, events in events_by_reason:
            for e in events:
                rows.append({
                    "표준코드": code,
                    "단축코드": m["단축코드"] if m is not None else None,
                    "종목명": m["종목명"] if m is not None else None,
                    "시장": market, "사유": reason, "종류": e.kind,
                    "판정일": e.trigger_date, "발효일": e.effective_date,
                    "연속일수": e.streak, "값": e.value,
                })
    return pd.DataFrame(rows, columns=event_columns)


def _norm_date(s) -> str:
    """'2026/07/21'·'2026-07-21'·'20260721' → '20260721'."""
    return str(s).replace("/", "").replace("-", "").strip()[:8]


def screen_price_recovery_failure(
    cache_df: pd.DataFrame,
    designations,
    *,
    window_days: int = sv.PRICE_DELIST_WINDOW_DAYS,
    recovery_days: int = sv.RELEASE_DAYS,
    price_threshold: float = sv.PRICE_THRESHOLD,
) -> pd.DataFrame:
    """규정 제54조①13.가(주가미달 상폐: 회복 실패)를 종목별로 판정한다.

    designations : (표준코드, 지정일) 튜플의 iterable. 지정일은 어떤 형식이든
        내부에서 캐시 일자 형식(YYYYMMDD)으로 정규화한다. 실제로는 KRX supervised의
        주가미달 지정건(ISU_CD_FULL, FST_DESIGN_DD)을 넣는다.

    Returns: 표준코드·단축코드·종목명·시장·지정일·상태·최장회복런·회복일·관찰일수·창종료
    """
    close_wide = ds.to_wide(cache_df, "종가")
    dates_all = close_wide.index.tolist()
    meta = _meta_by_code(cache_df)

    rows = []
    for code, desig in designations:
        d = _norm_date(desig)
        m = meta.loc[code] if code in meta.index else None
        if code not in close_wide.columns:
            res = sv.RecoveryFailureResult(sv.NO_DATA, 0, None, None, None, 0)
        else:
            closes = _series_none(close_wide[code].values)
            res = sv.evaluate_price_recovery_failure(
                dates_all, closes, d,
                window_days=window_days,
                recovery_days=recovery_days,
                price_threshold=price_threshold,
            )
        rows.append(
            {
                "표준코드": code,
                "단축코드": m["단축코드"] if m is not None else None,
                "종목명": m["종목명"] if m is not None else None,
                "시장": m["시장"] if m is not None else None,
                "지정일": d,
                "상태": res.status,
                "최장회복런": res.max_recovery_run,
                "회복일": res.recovered_on,
                "관찰일수": res.observed_days,
                "창종료": res.window_end,
            }
        )
    return pd.DataFrame(
        rows,
        columns=["표준코드", "단축코드", "종목명", "시장", "지정일", "상태",
                 "최장회복런", "회복일", "관찰일수", "창종료"],
    )


def price_recovery_failure_from_supervised(
    cache_df: pd.DataFrame,
    *,
    session=None,
    **kwargs,
) -> pd.DataFrame:
    """KRX supervised의 '주가 미달' 지정건을 앵커로 가(회복 실패)를 판정한다.

    현재는 주가미달 공식 지정이 없을 수 있어 결과가 빌 수 있다(신설 규정).
    """
    sup = fetch("supervised", session=session)
    pm = sup[sup["LIST_BZ_RSN_NM"].isin(KRX_PRICE_REASONS)]
    designations = list(zip(pm["ISU_CD_FULL"].astype(str), pm["FST_DESIGN_DD"]))
    return screen_price_recovery_failure(cache_df, designations, **kwargs)


def _window_end_trading_day(
    designation_date: str, *, window_days: int, session=None
) -> Optional[str]:
    """지정일로부터 window_days(90) 매매거래일째 날짜(YYYYMMDD). 아직 미도래면 None.

    삼성전자 시세추이(daily_snapshots.trading_days)로 거래일을 센다.
    """
    d = _norm_date(designation_date)
    # 지정일부터 넉넉히 앞으로(달력 200일 ≈ 130+ 거래일) 거래일을 받아 90번째를 취함.
    end_probe = (_dt_add_days(d, 220))
    days = ds.trading_days(d, end_probe, session=session)
    days = [x for x in days if x >= d]
    if len(days) >= window_days:
        return days[window_days - 1]
    return None


def _dt_add_days(yyyymmdd: str, days: int) -> str:
    from datetime import datetime, timedelta

    return (datetime.strptime(yyyymmdd, "%Y%m%d") + timedelta(days=days)).strftime("%Y%m%d")


def screen_reverse_split_delisting(
    designations,
    *,
    window_days: int = sv.PRICE_DELIST_WINDOW_DAYS,
    lookback_days: int = sv.REVERSE_SPLIT_LOOKBACK_DAYS,
    ratio_cap: float = sv.REVERSE_SPLIT_RATIO_CAP,
    session=None,
) -> pd.DataFrame:
    """규정 제54조①13.나·다(병합/감자에 의한 주가미달 상폐)를 종목별로 판정한다.

    designations : (종목코드6자리, 지정일) 튜플의 iterable. SEIBro는 6자리 종목코드로
        조회하므로 supervised의 ISU_CD(단축코드)를 넣는다.

    각 종목에 대해 SEIBro로 병합/감자 변경상장 이벤트를 받아
    supervision.evaluate_reverse_split_delisting에 넣는다.

    Returns: 종목코드·지정일·창종료·나·다·상폐·누적비율·창내이벤트·과거1년이벤트
    """
    from . import corporate_actions as ca

    rows = []
    for code, desig in designations:
        d = _norm_date(desig)
        window_end = _window_end_trading_day(d, window_days=window_days, session=session)
        # 이벤트 조회 구간: 과거 1년 ~ 창 종료(미도래면 지정일+달력200일).
        start = _dt_add_days(d, -lookback_days - 5)
        end = window_end or _dt_add_days(d, 220)
        events = ca.reverse_split_events(code, start, end)
        res = sv.evaluate_reverse_split_delisting(
            d, window_end, events, ratio_cap=ratio_cap, lookback_days=lookback_days
        )
        rows.append(
            {
                "종목코드": code,
                "지정일": d,
                "창종료": window_end,
                "나": res.na,
                "다": res.da,
                "상폐": res.delist,
                "누적비율": res.cumulative_ratio,
                "창내이벤트": res.within_window,
                "과거1년이벤트": res.in_past_year,
            }
        )
    return pd.DataFrame(
        rows,
        columns=["종목코드", "지정일", "창종료", "나", "다", "상폐",
                 "누적비율", "창내이벤트", "과거1년이벤트"],
    )


def current_status(
    events: pd.DataFrame,
    *,
    as_of: Optional[str] = None,
) -> pd.DataFrame:
    """이벤트에서 종목×사유별 현재상태(정상/관리)를 도출한다.

    as_of 가 주어지면 발효일이 as_of 이하인 이벤트까지만 반영한다(미도래 발효
    이벤트=당일예측은 제외). None이면 발효일 있는 모든 이벤트를 시간순 반영.

    Returns: 표준코드, 단축코드, 종목명, 시장, 사유, 상태(관리|정상),
             지정발효일(마지막), 해제발효일(마지막)
    """
    if events.empty:
        return pd.DataFrame(
            columns=["표준코드", "단축코드", "종목명", "시장", "사유",
                     "상태", "지정발효일", "해제발효일"]
        )

    ev = events.copy()
    # 발효일 없는(미도래) 이벤트는 상태 확정에서 제외.
    ev = ev[ev["발효일"].notna()]
    if as_of is not None:
        ev = ev[ev["발효일"].astype(str) <= str(as_of)]

    out_rows = []
    for (code, reason), grp in ev.groupby(["표준코드", "사유"]):
        grp = grp.sort_values(["발효일", "판정일"])
        last = grp.iloc[-1]
        state = "관리" if last["종류"] == sv.DESIGNATE else "정상"
        desig = grp[grp["종류"] == sv.DESIGNATE]["발효일"]
        rel = grp[grp["종류"] == sv.RELEASE]["발효일"]
        out_rows.append(
            {
                "표준코드": code,
                "단축코드": last["단축코드"],
                "종목명": last["종목명"],
                "시장": last["시장"],
                "사유": reason,
                "상태": state,
                "지정발효일": desig.iloc[-1] if len(desig) else None,
                "해제발효일": rel.iloc[-1] if len(rel) else None,
            }
        )
    return pd.DataFrame(out_rows)


def current_designations(
    cache_df: pd.DataFrame,
    *,
    as_of: Optional[str] = None,
    universe: Optional[set] = None,
    out_csv: Optional[str] = None,
    **screen_kwargs,
) -> pd.DataFrame:
    """현재 관리종목 지정 후보(집합·현재상태)를 산출한다 — 확정 산출물.

    시총은 부칙 시기별 임계값으로 연속 산정, 주가는 시행일(2026.7.1) 이후부터 산정
    하여 지정일까지 정확히 재현된다. '지정발효일'은 KRX 최초지정일과 일치한다.

    as_of   : 이 일자까지 발효된 이벤트만 반영. None이면 캐시 마지막까지.
    out_csv : 주면 결과를 utf-8-sig CSV로 저장.

    Returns: 표준코드·단축코드·종목명·시장·사유·상태·지정발효일·해제발효일
             (상태=='관리'인 행만).
    """
    events = screen_market(cache_df, universe=universe, **screen_kwargs)
    status = current_status(events, as_of=as_of)
    designated = status[status["상태"] == "관리"].reset_index(drop=True)
    if out_csv is not None:
        import os as _os

        _os.makedirs(_os.path.dirname(_os.path.abspath(out_csv)), exist_ok=True)
        designated.to_csv(out_csv, index=False, encoding="utf-8-sig")
    return designated


def reconcile_with_supervised(
    cache_df: pd.DataFrame,
    *,
    reason: str = REASON_MKTCAP,
    universe: Optional[set] = None,
    session=None,
    **screen_kwargs,
) -> dict:
    """스크리너가 뽑은 '현재 지정' 집합을 KRX supervised와 대조한다.

    reason: "시가총액" 또는 "주가". 해당 사유의 내 지정집합 vs KRX 지정집합을 비교.

    Returns dict:
        match     : 양쪽 모두 지정 (표준코드 set)
        my_only   : 내 로직만 지정 (KRX 미지정) — 오탐/임박/단서제외 후보
        krx_only  : KRX만 지정 (내 로직 미지정) — 창 부족/초기상태/타사유 후보
        summary   : 개수 요약 dict
        krx       : supervised 원본(해당 사유 필터) DataFrame
        mine      : 내 현재 지정 상태 DataFrame
    """
    events = screen_market(cache_df, universe=universe, **screen_kwargs)
    status = current_status(events)
    mine = status[(status["사유"] == reason) & (status["상태"] == "관리")]
    my_set = set(mine["표준코드"])

    krx_reasons = KRX_MKTCAP_REASONS if reason == REASON_MKTCAP else KRX_PRICE_REASONS
    sup = fetch("supervised", session=session)
    # 표준코드 컬럼: ISU_CD_FULL (KR7...). 사유: LIST_BZ_RSN_NM.
    # 우선주("종류주식 ...")도 동일 규칙이라 대조 대상에 포함.
    sup_reason = sup[sup["LIST_BZ_RSN_NM"].isin(krx_reasons)].copy()
    krx_set = set(sup_reason["ISU_CD_FULL"])

    match = my_set & krx_set
    my_only = my_set - krx_set
    krx_only = krx_set - my_set

    return {
        "match": match,
        "my_only": my_only,
        "krx_only": krx_only,
        "summary": {
            "reason": reason,
            "cache_dates": (
                cache_df["일자"].min(),
                cache_df["일자"].max(),
                cache_df["일자"].nunique(),
            ),
            "my_designated": len(my_set),
            "krx_designated": len(krx_set),
            "match": len(match),
            "my_only": len(my_only),
            "krx_only": len(krx_only),
        },
        "krx": sup_reason,
        "mine": mine,
    }
