"""주식병합(액면병합)·자본감소 '변경상장' 이벤트 어댑터.

규정 제54조①13.나·다(주가미달 상폐)를 판정하려면 각 종목의 병합/감자 변경상장
**일자와 비율**이 필요하다. 이 모듈은 예탁결제원(SEIBro) 데이터를 seibro-api
패키지로 받아 판정용 이벤트 리스트로 정규화한다.

- 일자: SEIBro `LIST_DT`(변경상장일). kind stock_issue_list의 변경상장일과 동일함을
  라이브로 확인(인디에프 014990 = 2026-06-26 일치).
- 비율: SEIBro `STK_FIX_RATIO`(= new/old). 규정의 'old:new'로 쓰려면 역수를 취한다
  (예: .2 → 5.0 = 5:1 병합).

seibro-api가 설치돼 있어야 한다(지연 임포트). 비율 파싱부(`parse_ratio`)는 순수라
네트워크 없이 테스트 가능하다.
"""
from __future__ import annotations

from typing import Optional

# SEIBro 사유코드
FACE_VALUE_MERGE = "202"   # 액면병합
CAPITAL_REDUCTION = "205"  # 자본감소
REVERSE_SPLIT_REASONS = {FACE_VALUE_MERGE: "액면병합", CAPITAL_REDUCTION: "자본감소"}


def parse_ratio(stk_fix_ratio) -> Optional[float]:
    """SEIBro STK_FIX_RATIO(new/old, 예 '.2')를 old:new 비율(float, 예 5.0)로.

    빈 값/0/파싱 실패는 None. 1 이상으로 감소한 경우(병합·감자)만 의미가 있다.
    """
    if stk_fix_ratio is None:
        return None
    s = str(stk_fix_ratio).strip().replace(",", "")
    if s in ("", "-", "nan", "None"):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if v <= 0:
        return None
    return 1.0 / v


def _norm_ymd(s) -> Optional[str]:
    if s is None:
        return None
    t = str(s).replace("/", "").replace("-", "").strip()[:8]
    return t if len(t) == 8 and t.isdigit() else None


def reverse_split_events(
    stock_code: str,
    start_dt: str,
    end_dt: str,
    *,
    reasons=(FACE_VALUE_MERGE, CAPITAL_REDUCTION),
) -> list[dict]:
    """한 종목의 [start_dt, end_dt] 병합/감자 변경상장 이벤트를 조회한다.

    Returns: [{"date": 변경상장일 YYYYMMDD, "ratio": old:new float, "type": 사유명}] 리스트.
        비율을 못 구한 행은 건너뛴다.
    """
    try:
        from seibro_api import get_schedule_reason_details
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "reverse_split_events는 seibro-api가 필요합니다. "
            "pip install -e ../seibro-api"
        ) from e

    start_dt = _norm_ymd(start_dt)
    end_dt = _norm_ymd(end_dt)
    events: list[dict] = []
    for rc in reasons:
        df = get_schedule_reason_details(
            stock_code, reason_code=rc, start_dt=start_dt, end_dt=end_dt,
            save_csv=False,
        )
        if df is None or df.empty or "DETAIL_TYPE" not in df.columns:
            continue
        issued = df[df["DETAIL_TYPE"] == "issued_stock"]
        for _, row in issued.iterrows():
            ratio = parse_ratio(row.get("STK_FIX_RATIO"))
            date = _norm_ymd(row.get("LIST_DT"))
            if ratio is None or date is None:
                continue
            events.append({
                "date": date,                        # 변경상장일(LIST_DT)
                "issue_date": _norm_ymd(row.get("ISSU_DT")),  # 발행일
                "ratio": ratio,                      # old:new
                "type": REVERSE_SPLIT_REASONS.get(rc, rc),
            })
    return events
