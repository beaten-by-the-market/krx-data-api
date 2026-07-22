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


def test_price_not_counted_before_launch():
    # 6월(시행 전) 종가 900 계속이어도 주가미달 카운트 안 됨 → price row 없음
    dates = [f"202606{d:02d}" for d in range(1, 31)]
    rows = _one_stock("KR7000010000", "000100", "가가", "KOSDAQ",
                      dates, [900]*30, [500_000_000_000]*30)  # 시총 넉넉
    art = dash.build_dashboard_artifacts(_cache(rows), {"000100"})
    assert [r for r in art["rows"] if r["reason"] == "price"] == []


def test_out_json_roundtrip(tmp_path):
    dates = [f"202606{d:02d}" for d in range(1, 31)]
    rows = _one_stock("KR7000010000", "000100", "가가", "KOSDAQ",
                      dates, [5000]*30, [10_000_000_000]*30)
    p = str(tmp_path / "d.json")
    dash.build_dashboard_artifacts(_cache(rows), {"000100"}, out_json=p)
    back = json.load(open(p, encoding="utf-8"))
    assert back["meta"]["universe_count"] == 1
    assert len(back["rows"]) >= 1
