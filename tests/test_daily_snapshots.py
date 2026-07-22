"""일별 스냅샷 로더/증분 캐시 테스트 (네트워크 없이 fetch 몽키패치)."""
from __future__ import annotations

import pandas as pd
import pytest

from krx_data_api import daily_snapshots as ds


def _raw_snapshot(codes_prices_caps):
    """all_stock_price 원형(영문코드, 콤마 문자열) 흉내."""
    rows = []
    for srt, price, cap in codes_prices_caps:
        rows.append(
            {
                "ISU_SRT_CD": srt,
                "ISU_CD": "KR7" + srt + "000",
                "ISU_ABBRV": f"종목{srt}",
                "MKT_NM": "KOSDAQ",
                "SECT_TP_NM": "벤처기업부",
                "TDD_CLSPRC": f"{price:,}",
                "MKTCAP": f"{cap:,}",
            }
        )
    return pd.DataFrame(rows)


def test_parse_won_strips_commas():
    s = pd.Series(["56,401,759,520", "1,063", "", "-", "0"])
    out = ds._parse_won(s)
    assert out.tolist()[:2] == [56401759520, 1063]
    assert pd.isna(out.iloc[2]) and pd.isna(out.iloc[3])
    assert out.iloc[4] == 0


def test_fetch_snapshot_normalizes(monkeypatch):
    raw = _raw_snapshot([("060310", 1063, 56_401_759_520), ("005930", 244000, 1_400_000_000_000_000)])
    monkeypatch.setattr(ds, "fetch", lambda name, **kw: raw)
    snap = ds.fetch_snapshot("20260720")
    assert list(snap.columns) == ds.SNAPSHOT_COLUMNS
    assert (snap["일자"] == "20260720").all()
    assert snap.iloc[0]["종가"] == 1063
    assert snap.iloc[0]["시가총액"] == 56_401_759_520
    # 단축코드 문자열·선행 0 보존
    assert snap.iloc[0]["단축코드"] == "060310"


def test_trading_days_from_reference(monkeypatch):
    ipt = pd.DataFrame({"일자": ["2026/07/20", "2026/07/16", "2026/07/15"]})
    monkeypatch.setattr(ds, "fetch", lambda name, **kw: ipt)
    days = ds.trading_days("20260715", "20260720")
    assert days == ["20260715", "20260716", "20260720"]  # 정렬·YYYYMMDD


def test_update_cache_incremental_and_roundtrip(tmp_path, monkeypatch):
    cache = str(tmp_path / "snap.csv")

    # 1차: 07/15, 07/16 두 거래일 수집
    def fake_fetch_v1(name, **kw):
        if name == "individual_price_trend":
            return pd.DataFrame({"일자": ["2026/07/15", "2026/07/16"]})
        if name == "all_stock_price":
            d = kw["trdDd"]
            price = 900 if d == "20260715" else 950
            return _raw_snapshot([("060310", price, 20_000_000_000)])
        raise AssertionError(name)

    monkeypatch.setattr(ds, "fetch", fake_fetch_v1)
    df1 = ds.update_cache("20260715", "20260716", cache, verbose=False)
    assert sorted(df1["일자"].unique()) == ["20260715", "20260716"]

    # roundtrip: 다시 읽으면 dtype/값 보존
    reloaded = ds.load_cache(cache)
    assert reloaded.iloc[0]["단축코드"] == "060310"
    assert reloaded[reloaded["일자"] == "20260715"]["종가"].iloc[0] == 900

    # 2차: 범위 확장(07/15~07/17). 기존 2일은 건너뛰고 07/17만 신규 수집.
    fetched_dates = []

    def fake_fetch_v2(name, **kw):
        if name == "individual_price_trend":
            return pd.DataFrame({"일자": ["2026/07/15", "2026/07/16", "2026/07/17"]})
        if name == "all_stock_price":
            fetched_dates.append(kw["trdDd"])
            return _raw_snapshot([("060310", 980, 21_000_000_000)])
        raise AssertionError(name)

    monkeypatch.setattr(ds, "fetch", fake_fetch_v2)
    df2 = ds.update_cache("20260715", "20260717", cache, verbose=False)
    assert fetched_dates == ["20260717"]  # 신규 일자만 호출
    assert sorted(df2["일자"].unique()) == ["20260715", "20260716", "20260717"]
    assert len(df2) == 3  # 종목 1개 × 3일


def test_update_cache_dedupes_on_rerun(tmp_path, monkeypatch):
    cache = str(tmp_path / "snap.csv")

    def fake(name, **kw):
        if name == "individual_price_trend":
            return pd.DataFrame({"일자": ["2026/07/20"]})
        return _raw_snapshot([("060310", 1000, 30_000_000_000)])

    monkeypatch.setattr(ds, "fetch", fake)
    ds.update_cache("20260720", "20260720", cache, verbose=False)
    df = ds.update_cache("20260720", "20260720", cache, verbose=False)  # 재실행
    assert len(df) == 1  # 중복 없음


def test_to_wide_pivot(tmp_path):
    long = pd.DataFrame(
        {
            "일자": ["20260715", "20260716", "20260715"],
            "단축코드": ["060310", "060310", "005930"],
            "표준코드": ["KR7060310000", "KR7060310000", "KR7005930003"],
            "종목명": ["A", "A", "B"],
            "시장": ["KOSDAQ"] * 3,
            "소속부": [""] * 3,
            "종가": pd.array([900, 950, 244000], dtype="Int64"),
            "시가총액": pd.array([20, 21, 1400], dtype="Int64"),
        }
    )
    wide = ds.to_wide(long, "종가")
    assert list(wide.index) == ["20260715", "20260716"]
    assert wide.loc["20260715", "KR7060310000"] == 900
    # 005930는 07/16에 결측 → NaN
    assert pd.isna(wide.loc["20260716", "KR7005930003"])


def test_to_wide_rejects_bad_column():
    with pytest.raises(ValueError):
        ds.to_wide(pd.DataFrame(), "거래대금")
