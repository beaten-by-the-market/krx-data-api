"""대시보드 artifacts 생성기 테스트 (네트워크 없음)."""
from __future__ import annotations

import json

import pandas as pd

from krx_data_api import dashboard as dash


def _cache(rows):
    """rows: list of (일자, 단축코드, 표준코드, 종목명, 시장, 종가, 시가총액)."""
    cols = ["일자", "단축코드", "표준코드", "종목명", "시장", "종가", "시가총액"]
    df = pd.DataFrame(rows, columns=cols)
    df["소속부"] = ""
    df["종가"] = df["종가"].astype("Int64")
    df["시가총액"] = df["시가총액"].astype("Int64")
    return df


def _one_stock(code, srt, name, market, dates, closes, caps):
    return [(d, srt, code, name, market, c, m)
            for d, c, m in zip(dates, closes, caps)]


def test_build_artifacts_structure_and_designation():
    # 코스닥 종목이 시총 100억(<150억 기준)으로 30일 미달 → 지정
    dates = [f"202606{d:02d}" for d in range(1, 31)]  # 6월 30일(시행 전, 150억 기준)
    rows = _one_stock("KR7000010000", "000100", "가가", "KOSDAQ",
                      dates, [5000]*30, [10_000_000_000]*30)
    cache = _cache(rows)
    uni = {"000100"}
    art = dash.build_dashboard_artifacts(cache, uni, generated_at="2026-07-22T00:00:00")
    assert set(art) == {"meta", "counts", "reconcile", "rows", "series"}
    assert art["meta"]["official_available"] is False
    cap_rows = [r for r in art["rows"] if r["reason"] == "mktcap"]
    assert len(cap_rows) == 1
    r = cap_rows[0]
    assert r["state"] in ("designated", "release_pending")
    assert r["official"] is False
    # reconcile: 공식 없음 → official null, estimate_only 1
    assert art["reconcile"]["mktcap"]["official"] is None
    assert art["reconcile"]["mktcap"]["estimate_only"] == 1


def test_approaching_countdown():
    # 미달 25일(<30) → 임박, D-5
    dates = [f"202606{d:02d}" for d in range(1, 26)]  # 25일
    rows = _one_stock("KR7000010000", "000100", "가가", "KOSDAQ",
                      dates, [5000]*25, [10_000_000_000]*25)
    art = dash.build_dashboard_artifacts(_cache(rows), {"000100"})
    r = [x for x in art["rows"] if x["reason"] == "mktcap"][0]
    assert r["state"] == "approaching"
    assert r["countdown"]["to_designation"] == 5


def test_official_reconcile_and_badge():
    dates = [f"202606{d:02d}" for d in range(1, 31)]
    rows = _one_stock("KR7000010000", "000100", "가가", "KOSDAQ",
                      dates, [5000]*30, [10_000_000_000]*30)
    supervised = pd.DataFrame({
        "ISU_CD": ["000100"], "LIST_BZ_RSN_NM": ["시가총액 미달"],
        "FST_DESIGN_DD": ["2026/07/11"],
    })
    art = dash.build_dashboard_artifacts(_cache(rows), {"000100"}, supervised=supervised)
    assert art["meta"]["official_available"] is True
    assert art["reconcile"]["mktcap"] == {"official": 1, "matched": 1,
                                          "estimate_only": 0, "missed": 0}
    r = [x for x in art["rows"] if x["reason"] == "mktcap"][0]
    assert r["official"] is True
    assert r["official_design_date"] == "20260711"


def test_official_from_supervised_combined_and_scoped():
    # KRX supervised는 다중사유를 콤마로 결합한다. 부분매칭으로 콤바인 라벨을 잡되,
    # 우선주("종류주식 시가총액 미달")는 유니버스 밖이라 공식집합에서 제외돼야 한다.
    sup = pd.DataFrame({
        "ISU_CD": ["000100", "000200", "000105"],
        "LIST_BZ_RSN_NM": [
            "시가총액 미달,주가 미달(동전주)",   # 보통주 콤바인(시총+동전주)
            "주가 미달(동전주)",                  # 보통주 동전주 단독
            "종류주식 시가총액 미달",             # 우선주(유니버스 밖)
        ],
        "FST_DESIGN_DD": ["2026/07/11", "2026/07/12", "2026/07/13"],
    })
    off_cap, off_price, dates = dash._official_from_supervised(sup, universe={"000100", "000200"})
    assert off_cap == {"000100"}                    # 콤바인 인식 + 우선주(000105) 스코핑 제외
    assert off_price == {"000100", "000200"}        # "주가 미달"·"주가 미달(동전주)" 모두 인식
    assert dates["000100"] == "20260711"


def test_price_not_counted_before_launch():
    # 6월(시행 전) 종가 900 계속이어도 주가미달 카운트 안 됨 → price row 없음
    dates = [f"202606{d:02d}" for d in range(1, 31)]
    rows = _one_stock("KR7000010000", "000100", "가가", "KOSDAQ",
                      dates, [900]*30, [500_000_000_000]*30)  # 시총 넉넉
    art = dash.build_dashboard_artifacts(_cache(rows), {"000100"})
    assert [r for r in art["rows"] if r["reason"] == "price"] == []


def test_kind_admin_issue_designation_date():
    # KIND admin_issue(종목명·지정일)로 지정 종목에 kind_design_date 부착(종목명 매칭)
    dates = [f"202606{d:02d}" for d in range(1, 31)]
    rows = _one_stock("KR7000010000", "000100", "가가종목", "KOSDAQ",
                      dates, [5000]*30, [10_000_000_000]*30)
    admin = pd.DataFrame({
        "종목명": ["가가종목", "딴종목"],
        "지정일": ["2026/03/24", "2026/01/02"],
        "지정사유": ["시가총액 미달", "감사의견"],
    })
    art = dash.build_dashboard_artifacts(_cache(rows), {"000100"}, admin_issue=admin)
    r = [x for x in art["rows"] if x["reason"] == "mktcap"][0]
    assert r["kind_design_date"] == "20260324"  # 종전 지정분 원본 지정일


def test_kind_admin_issue_none_when_not_designated():
    # 임박(미지정) 종목은 kind_design_date=None
    dates = [f"202606{d:02d}" for d in range(1, 26)]  # 25일 → 임박
    rows = _one_stock("KR7000010000", "000100", "가가종목", "KOSDAQ",
                      dates, [5000]*25, [10_000_000_000]*25)
    admin = pd.DataFrame({"종목명": ["가가종목"], "지정일": ["2026/03/24"], "지정사유": ["x"]})
    art = dash.build_dashboard_artifacts(_cache(rows), {"000100"}, admin_issue=admin)
    r = [x for x in art["rows"] if x["reason"] == "mktcap"][0]
    assert r["state"] == "approaching"
    assert r["kind_design_date"] is None


def test_out_json_roundtrip(tmp_path):
    dates = [f"202606{d:02d}" for d in range(1, 31)]
    rows = _one_stock("KR7000010000", "000100", "가가", "KOSDAQ",
                      dates, [5000]*30, [10_000_000_000]*30)
    p = str(tmp_path / "d.json")
    dash.build_dashboard_artifacts(_cache(rows), {"000100"}, out_json=p)
    back = json.load(open(p, encoding="utf-8"))
    assert back["meta"]["universe_count"] == 1
    assert len(back["rows"]) >= 1
