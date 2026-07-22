"""관리종목 스크리너용 일별 전종목 스냅샷 수집 · CSV 증분 캐시.

`all_stock_price`(MDCSTAT01501)는 매 호출이 특정 매매거래일 하루의 전종목
종가·시가총액을 준다. 이 모듈은 그것을 정규화해 CSV 캐시에 **증분**으로 쌓는다
(이미 수집한 일자는 건너뛰고 빠진 일자만 받아 얹는다).

주의(라이브 검증 2026-07-22):
- `all_stock_price`는 응답에 날짜 컬럼이 없다. 휴장일 trdDd로 호출하면 **직전
  매매거래일 데이터를 그대로** 돌려준다. 따라서 달력일을 순회하면 안 되고, 실제
  매매거래일 목록을 먼저 확정해 그 날짜만 수집해야 한다.
- 매매거래일 목록은 유동성 높은 기준종목(삼성전자)의 `individual_price_trend`
  시계열 `일자`에서 얻는다(거래일만 행으로 존재).
- 원주가: `all_stock_price`의 TDD_CLSPRC는 기본이 원주가(미수정)라 규정 취지에 맞다.
- 값은 콤마 포함 문자열('56,401,759,520')이라 숫자로 파싱한다.
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from .client import fetch

# 매매거래일 캘린더 기준 종목: 삼성전자(유동성 최상, 종일 거래정지 사실상 없음).
REFERENCE_ISU = "KR7005930003"

# CSV 캐시 스키마. 코드/일자는 문자열(선행 0 보존), 금액은 정수(원).
SNAPSHOT_COLUMNS = [
    "일자",       # YYYYMMDD (매매거래일)
    "단축코드",   # ISU_SRT_CD (6자리)
    "표준코드",   # ISU_CD (KR7...)
    "종목명",     # ISU_ABBRV
    "시장",       # MKT_NM (KOSPI/KOSDAQ/KONEX)
    "소속부",     # SECT_TP_NM (관리종목/SPAC 등 태그 참고용)
    "종가",       # TDD_CLSPRC (원, 무거래일엔 기준가격)
    "시가총액",   # MKTCAP (원)
    "거래량",     # ACC_TRDVOL (주). 0이면 매매 없음(매매거래정지 등) → 미달 카운트 제외 신호
]
_STR_COLS = ["일자", "단축코드", "표준코드"]
_NUM_COLS = ["종가", "시가총액", "거래량"]


def _parse_won(s: pd.Series) -> pd.Series:
    """'56,401,759,520' 같은 콤마 문자열을 정수(Int64)로. 파싱 실패는 NA."""
    cleaned = (
        s.astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace({"": None, "-": None})
    )
    return pd.to_numeric(cleaned, errors="coerce").astype("Int64")


def trading_days(
    start: str, end: str, *, session=None, reference_isu: str = REFERENCE_ISU
) -> list[str]:
    """[start, end] 구간의 매매거래일(YYYYMMDD) 오름차순 목록.

    start/end 는 YYYYMMDD. 기준종목 시세추이의 `일자`를 매매거래일로 사용한다.
    """
    ipt = fetch(
        "individual_price_trend",
        isuCd=reference_isu,
        strtDd=start,
        endDd=end,
        adjusted_price=False,
        session=session,
    )
    if ipt.empty or "일자" not in ipt.columns:
        raise RuntimeError(
            f"매매거래일 목록을 얻지 못했습니다(기준종목 {reference_isu}, "
            f"{start}~{end}). 응답 컬럼: {list(ipt.columns)}"
        )
    days = ipt["일자"].astype(str).str.replace("/", "", regex=False).str.strip()
    return sorted(d for d in days if d)


def fetch_snapshot(trade_date: str, *, session=None) -> pd.DataFrame:
    """단일 매매거래일 전종목 스냅샷을 SNAPSHOT_COLUMNS 스키마로 정규화.

    trade_date 는 반드시 실제 매매거래일이어야 한다(휴장일이면 직전 거래일
    데이터가 오므로 호출자가 trading_days로 걸러 넘겨야 함).
    """
    raw = fetch("all_stock_price", trdDd=trade_date, session=session)
    out = pd.DataFrame(
        {
            "일자": trade_date,
            "단축코드": raw["ISU_SRT_CD"].astype(str),
            "표준코드": raw["ISU_CD"].astype(str),
            "종목명": raw["ISU_ABBRV"].astype(str),
            "시장": raw["MKT_NM"].astype(str),
            "소속부": raw["SECT_TP_NM"].astype(str) if "SECT_TP_NM" in raw else "",
            "종가": _parse_won(raw["TDD_CLSPRC"]),
            "시가총액": _parse_won(raw["MKTCAP"]),
            "거래량": _parse_won(raw["ACC_TRDVOL"]) if "ACC_TRDVOL" in raw else pd.NA,
        }
    )
    return out[SNAPSHOT_COLUMNS]


def load_cache(cache_path: str) -> pd.DataFrame:
    """CSV 캐시를 스키마 dtype으로 읽는다. 없으면 빈 프레임."""
    if not os.path.exists(cache_path):
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)
    df = pd.read_csv(
        cache_path,
        dtype={c: str for c in _STR_COLS},
        encoding="utf-8-sig",
    )
    for c in _NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    return df


def _write_cache(df: pd.DataFrame, cache_path: str) -> None:
    parent = os.path.dirname(os.path.abspath(cache_path))
    os.makedirs(parent, exist_ok=True)
    # utf-8-sig: Excel에서 한글 정상 표시.
    df.to_csv(cache_path, index=False, encoding="utf-8-sig")


def update_cache(
    start: str,
    end: str,
    cache_path: str,
    *,
    session=None,
    verbose: bool = True,
) -> pd.DataFrame:
    """[start, end]의 매매거래일 스냅샷을 CSV 캐시에 증분 수집한다.

    이미 캐시에 있는 일자는 재수집하지 않는다. 빠진 일자만 받아 얹고,
    (일자, 표준코드) 기준 중복 제거 후 정렬해 다시 저장한다.

    Returns
    -------
    캐시 전체 DataFrame(일자·단축코드 오름차순 정렬).
    """
    existing = load_cache(cache_path)
    have = set(existing["일자"].astype(str)) if not existing.empty else set()

    want = trading_days(start, end, session=session)
    missing = [d for d in want if d not in have]

    if verbose:
        print(
            f"[update_cache] 매매거래일 {len(want)}일 중 신규 {len(missing)}일 수집 "
            f"(캐시 보유 {len(have)}일)"
        )

    new_frames = []
    for idx, d in enumerate(missing, 1):
        snap = fetch_snapshot(d, session=session)
        new_frames.append(snap)
        if verbose:
            print(f"  ({idx}/{len(missing)}) {d}: {len(snap)}종목")

    if new_frames:
        # 빈 existing을 concat에 넣으면 dtype 관련 FutureWarning이 난다 → 비었을 때 제외.
        parts = ([existing] if not existing.empty else []) + new_frames
        combined = pd.concat(parts, ignore_index=True)
    else:
        combined = existing

    if not combined.empty:
        combined = (
            combined.drop_duplicates(subset=["일자", "표준코드"], keep="last")
            .sort_values(["일자", "단축코드"])
            .reset_index(drop=True)
        )
        _write_cache(combined, cache_path)

    return combined


def to_wide(cache_df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """롱 캐시를 일자(행)×표준코드(열) 매트릭스로 피벗한다.

    value_col: "종가"·"시가총액"·"거래량". 상장 전/후 결측은 NaN으로 남아
    상태기계에서 None(스킵)으로 처리된다. 인덱스(일자)는 오름차순.
    """
    if value_col not in ("종가", "시가총액", "거래량"):
        raise ValueError("value_col must be '종가', '시가총액', or '거래량'")
    wide = cache_df.pivot_table(
        index="일자", columns="표준코드", values=value_col, aggfunc="last"
    ).sort_index()
    return wide
