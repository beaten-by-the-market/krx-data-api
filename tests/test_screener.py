"""전시장 스크리너 순수 로직 테스트 (네트워크 없음)."""
from __future__ import annotations

import pandas as pd

from krx_data_api import screener as scr


def _long_cache(code, dates, closes, caps, name="테스트", srt="000010", mkt="KOSDAQ"):
    """단일 종목 롱 캐시 생성."""
    return pd.DataFrame(
        {
            "일자": dates,
            "단축코드": srt,
            "표준코드": code,
            "종목명": name,
            "시장": mkt,
            "소속부": "",
            "종가": pd.array(closes, dtype="Int64"),
            "시가총액": pd.array(caps, dtype="Int64"),
        }
    )


def test_screen_market_price_designation():
    dates = [f"2026{d:04d}" for d in range(101, 131)]  # 30 dummy dates
    closes = [900] * 30                # 주가 미달 30일
    caps = [500_000_000_000] * 30      # 시총 넉넉
    cache = _long_cache("KR7000001000", dates, closes, caps)
    events = scr.screen_market(cache, price_count_start=None)
    price = events[events["사유"] == "주가"]
    assert len(price) == 1
    assert price.iloc[0]["종류"] == "designate"
    assert price.iloc[0]["판정일"] == dates[-1]
    assert pd.isna(price.iloc[0]["발효일"])  # 익일 미도래 → 당일예측 후보
    assert events[events["사유"] == "시가총액"].empty


def test_screen_market_mktcap_designation():
    dates = [f"2026{d:04d}" for d in range(101, 131)]
    closes = [5000] * 30
    caps = [10_000_000_000] * 30       # 100억 < 300억
    cache = _long_cache("KR7000001000", dates, closes, caps)
    events = scr.screen_market(cache, price_count_start=None)
    cap = events[events["사유"] == "시가총액"]
    assert len(cap) == 1
    assert cap.iloc[0]["종류"] == "designate"


def test_current_status_designation_with_effective_date():
    # 30일 미달 + 이후 5일 더(발효일 도래) → 상태 '관리'
    dates = [f"2026{d:04d}" for d in range(101, 136)]  # 35 dates
    closes = [900] * 30 + [900] * 5
    caps = [500_000_000_000] * 35
    cache = _long_cache("KR7000001000", dates, closes, caps)
    events = scr.screen_market(cache, price_count_start=None)
    status = scr.current_status(events)
    price = status[status["사유"] == "주가"].iloc[0]
    assert price["상태"] == "관리"
    assert price["지정발효일"] == dates[30]  # 30번째 미달일(index29)의 익일=index30


def test_current_status_as_of_excludes_future_effective():
    dates = [f"2026{d:04d}" for d in range(101, 132)]  # 31 dates
    closes = [900] * 30 + [900]
    caps = [500_000_000_000] * 31
    cache = _long_cache("KR7000001000", dates, closes, caps)
    events = scr.screen_market(cache, price_count_start=None)
    # 발효일 = dates[30]. as_of를 그 전날로 주면 아직 지정 전 → 빈 상태.
    status = scr.current_status(events, as_of=dates[29])
    assert status.empty or (status["상태"] == "관리").sum() == 0


def test_screen_market_empty_cache():
    events = scr.screen_market(pd.DataFrame(columns=["일자", "표준코드", "종가", "시가총액"]))
    assert events.empty


def test_price_count_start_excludes_pre_launch():
    # 부칙 제3조①: 시행일(20260701) 전 주가미달은 카운트 안 함.
    pre = [f"202606{d:02d}" for d in range(1, 31)]   # 6월(시행 전) 30일
    post = [f"202607{d:02d}" for d in range(1, 29)]  # 7월(시행 후) 28일
    dates = pre + post
    closes = [900] * len(dates)               # 계속 1,000원 미만
    caps = [500_000_000_000] * len(dates)     # 시총 넉넉
    cache = _long_cache("KR7000001000", dates, closes, caps)
    # 기본 price_count_start=20260701 → 시행 후 28일만 카운트(<30) → 미지정
    ev = scr.screen_market(cache)
    assert ev[ev["사유"] == "주가"].empty
    # 제한 해제 → 58일 미달 → 지정
    ev_all = scr.screen_market(cache, price_count_start=None)
    assert not ev_all[ev_all["사유"] == "주가"].empty


def test_mktcap_threshold_won_schedule():
    # 시기별 임계값(부칙 경과규정)
    assert scr.mktcap_threshold_won("KOSDAQ", "20260630") == 15_000_000_000
    assert scr.mktcap_threshold_won("KOSDAQ", "20260701") == 20_000_000_000
    assert scr.mktcap_threshold_won("KOSDAQ", "20270101") == 30_000_000_000
    assert scr.mktcap_threshold_won("KOSPI", "20260630") == 20_000_000_000
    assert scr.mktcap_threshold_won("KOSPI", "20260701") == 30_000_000_000
    assert scr.mktcap_threshold_won("KONEX", "20260701") is None


def test_market_period_thresholds():
    # 시총 180억(시행 전): KOSPI(200억 기준)만 미달, KOSDAQ(150억)은 미달 아님
    dates = [f"202606{d:02d}" for d in range(1, 31)]  # 6월(시행 전) 30일
    closes = [5000] * 30
    caps = [18_000_000_000] * 30  # 180억
    kospi = _long_cache("KR7000002000", dates, closes, caps, mkt="KOSPI")
    kosdaq = _long_cache("KR7000003000", dates, closes, caps, mkt="KOSDAQ")
    evk = scr.screen_market(kospi, price_count_start=None)
    assert not evk[evk["사유"] == "시가총액"].empty          # KOSPI 미달
    assert scr.screen_market(kosdaq, price_count_start=None).empty  # KOSDAQ 미달 아님


def test_mktcap_period_transition_across_launch():
    # 6월 150억↑·7월 200억↓ 종목(코스닥): 6월엔 미달 아님(>150), 7월부터 미달(<200)
    pre = [f"202606{d:02d}" for d in range(1, 31)]   # 6월 30일, 시총 180억(>150 → 정상)
    post = [f"202607{d:02d}" for d in range(1, 31)]  # 7월 30일, 시총 180억(<200 → 미달)
    dates = pre + post
    caps = [18_000_000_000] * len(dates)  # 180억 내내 동일
    closes = [5000] * len(dates)
    cache = _long_cache("KR7000009000", dates, closes, caps, srt="000090", mkt="KOSDAQ")
    ev = scr.screen_market(cache, price_count_start=None)
    cap = ev[(ev["사유"] == "시가총액") & (ev["종류"] == "designate")]
    assert len(cap) == 1
    # 7월 1일부터 30거래일째에 지정 → 판정일은 post의 30번째
    assert cap.iloc[0]["판정일"] == post[29]


def test_konex_excluded_entirely():
    # KONEX는 시총·주가 규칙 모두 없음 → 아무리 낮아도 이벤트 없음
    dates = [f"2026{d:04d}" for d in range(101, 131)]
    closes = [500] * 30            # 주가 미달 수준
    caps = [1_000_000_000] * 30    # 10억, 시총 미달 수준
    konex = _long_cache("KR7000004000", dates, closes, caps, mkt="KONEX")
    ev = scr.screen_market(konex, price_count_start=None)
    assert ev.empty


def test_spac_excluded():
    # 스팩(종목명에 '스팩')은 시총 미달이어도 규칙 대상 아님 → 이벤트 없음
    dates = [f"2026{d:04d}" for d in range(101, 131)]
    closes = [2000] * 30
    caps = [10_000_000_000] * 30  # 100억 < 300억
    spac = _long_cache("KR70044K0008", dates, closes, caps, mkt="KOSDAQ", name="삼성스팩10호")
    assert scr.screen_market(spac, price_count_start=None).empty
    # exclude_spac=False로 끄면 잡힘
    ev = scr.screen_market(spac, price_count_start=None, exclude_spac=False)
    assert not ev[ev["사유"] == "시가총액"].empty


def test_preferred_excluded_by_short_code_suffix():
    # 우선주: 단축코드 끝자리 != '0' → 제외. (종목명 '우' 아니어도 코드로 판별)
    dates = [f"2026{d:04d}" for d in range(101, 131)]
    closes = [5000] * 30
    caps = [10_000_000_000] * 30  # 100억 < 300억
    pref = _long_cache("KR7000005005", dates, closes, caps, srt="000005",
                       mkt="KOSDAQ", name="테스트우")
    assert scr.screen_market(pref, price_count_start=None).empty
    # 보통주(끝자리 0)는 잡힘
    common = _long_cache("KR7000006000", dates, closes, caps, srt="000060",
                         mkt="KOSDAQ", name="테스트")
    assert not scr.screen_market(common, price_count_start=None).empty


def test_reit_excluded_by_suffix_not_substring():
    dates = [f"2026{d:04d}" for d in range(101, 131)]
    closes = [5000] * 30
    caps = [10_000_000_000] * 30
    # '리츠'로 끝나는 리츠 → 제외
    reit = _long_cache("KR7000007000", dates, closes, caps, srt="000070",
                       mkt="KOSPI", name="케이탑리츠")
    assert scr.screen_market(reit, price_count_start=None).empty
    # '리츠'가 중간에 든 일반주(블리츠웨이) → 제외 안 됨
    blitz = _long_cache("KR7000008000", dates, closes, caps, srt="000080",
                        mkt="KOSDAQ", name="블리츠웨이엔터테인먼트")
    assert not scr.screen_market(blitz, price_count_start=None).empty


def test_foreign_stock_included():
    # 외국주권도 대상. 단축코드 900xxx/950xxx(끝자리 0), 표준코드 KR7 아님 → 포함
    dates = [f"2026{d:04d}" for d in range(101, 131)]
    closes = [5000] * 30
    caps = [10_000_000_000] * 30  # 100억 < 300억(KOSDAQ)
    foreign = _long_cache("HK0000214814", dates, closes, caps, srt="900270",
                          mkt="KOSDAQ", name="헝셩그룹")
    ev = scr.screen_market(foreign, price_count_start=None)
    assert not ev[ev["사유"] == "시가총액"].empty
    assert scr.excluded_reason("900270", "헝셩그룹", "HK0000214814") is None


def test_foreign_dr_included():
    # 외국주식예탁증권(DR)도 대상. 950xxx 단축코드(끝자리 0), KR8 표준코드 → 포함
    dates = [f"2026{d:04d}" for d in range(101, 131)]
    closes = [5000] * 30
    caps = [10_000_000_000] * 30
    dr = _long_cache("KR8840150005", dates, closes, caps, srt="950200",
                     mkt="KOSDAQ", name="소마젠")
    assert not scr.screen_market(dr, price_count_start=None).empty
    assert scr.excluded_reason("950200", "소마젠", "KR8840150005") is None


def test_infra_fund_excluded_by_code_biotech_kept():
    dates = [f"2026{d:04d}" for d in range(101, 131)]
    closes = [5000] * 30
    caps = [10_000_000_000] * 30
    # 인프라펀드(큐레이트 코드) → 제외
    infra = _long_cache("KR7088980008", dates, closes, caps, srt="088980",
                        mkt="KOSPI", name="맥쿼리인프라")
    assert scr.screen_market(infra, price_count_start=None).empty
    # 바이오인프라(일반 회사, 코드 다름) → 유지
    bio = _long_cache("KR7199730003", dates, closes, caps, srt="199730",
                      mkt="KOSDAQ", name="바이오인프라")
    assert not scr.screen_market(bio, price_count_start=None).empty


def test_universe_whitelist_filters():
    dates = [f"2026{d:04d}" for d in range(101, 131)]
    closes = [5000] * 30
    caps = [10_000_000_000] * 30  # 100억 < 300억
    # 두 종목: 하나만 유니버스에 포함
    a = _long_cache("KR7000010000", dates, closes, caps, srt="000100", name="포함")
    b = _long_cache("KR7000020000", dates, closes, caps, srt="000200", name="제외")
    cache = pd.concat([a, b], ignore_index=True)
    ev = scr.screen_market(cache, price_count_start=None, universe={"000100"})
    codes = set(ev["단축코드"])
    assert codes == {"000100"}  # 유니버스 밖 종목은 판정 안 함


def test_universe_overrides_heuristics():
    # 유니버스가 있으면 이름 휴리스틱 무시: '스팩'이라도 유니버스에 있으면 판정됨
    dates = [f"2026{d:04d}" for d in range(101, 131)]
    closes = [5000] * 30
    caps = [10_000_000_000] * 30
    spac = _long_cache("KR70044K0008", dates, closes, caps, srt="0044K0",
                       name="삼성스팩10호")
    # 휴리스틱 경로면 제외, 유니버스 경로면 포함
    assert scr.screen_market(spac, price_count_start=None).empty
    ev = scr.screen_market(spac, price_count_start=None, universe={"0044K0"})
    assert not ev.empty


def test_target_codes_helper():
    uni = pd.DataFrame({"종목코드": ["005930", "0039P0", "900270"]})
    assert scr.target_codes(uni) == {"005930", "0039P0", "900270"}


def test_screen_price_recovery_failure_wrapper():
    # 지정일 20260501 이후 90거래일 안 되고 계속 미달 → 관찰중 또는 조기확정
    dates = [f"202605{d:02d}" for d in range(1, 21)]  # 20거래일만
    closes = [800] * 20
    cache = _long_cache("KR7000010000", dates, closes, [500_000_000_000] * 20,
                        srt="000100", name="가가")
    res = scr.screen_price_recovery_failure(
        cache, [("KR7000010000", "2026/05/01")]
    )
    assert len(res) == 1
    assert res.iloc[0]["지정일"] == "20260501"       # 날짜 정규화
    assert res.iloc[0]["상태"] in ("관찰중", "조기상폐확정")


def test_screen_price_recovery_failure_recovered():
    # 지정 후 45거래일 연속 1000원 이상 → 회복
    dates = [f"2026{d:04d}" for d in range(601, 651)]  # 50거래일
    closes = [1500] * 50
    cache = _long_cache("KR7000010000", dates, closes, [500_000_000_000] * 50,
                        srt="000100", name="회복종목")
    res = scr.screen_price_recovery_failure(cache, [("KR7000010000", dates[0])])
    assert res.iloc[0]["상태"] == "회복"


def test_current_designations_writes_csv(tmp_path):
    dates = [f"2026{d:04d}" for d in range(101, 136)]  # 35 dates (개정 전이지만 price_count_start=None 사용 위해)
    closes = [900] * 35
    caps = [500_000_000_000] * 35
    cache = _long_cache("KR7000001000", dates, closes, caps, name="가가종목")
    out = str(tmp_path / "designated.csv")
    res = scr.current_designations(cache, price_count_start=None, out_csv=out)
    assert (res["상태"] == "관리").all()
    assert (res["사유"] == "주가").any()
    # CSV 왕복
    back = pd.read_csv(out, dtype={"표준코드": str}, encoding="utf-8-sig")
    assert "가가종목" in set(back["종목명"])
