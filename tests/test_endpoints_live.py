"""Live tests that call KRX.

Run: pytest tests/test_endpoints_live.py
Skip: set KRX_SKIP_LIVE=1.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd
import pytest

from krx_data_api import client, fetch, list_endpoints

pytestmark = pytest.mark.skipif(
    os.getenv("KRX_SKIP_LIVE") == "1", reason="KRX_SKIP_LIVE set"
)


def _recent_trading_day() -> str:
    """Return the latest weekday, using Friday when today is a weekend."""
    d = datetime.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def test_catalog_lists_registered_endpoints():
    names = list_endpoints()
    assert len(names) >= 15
    for required in (
        "listed_stocks",
        "listed_stocks_csv",
        "all_stock_price",
        "all_stock_price_csv",
        "individual_price_trend",
        "investor_trading_individual",
        "investor_trading_individual_json",
        "investor_trading_individual_daily",
        "investor_trading_individual_daily_json",
        "delisted",
        "delisted_json",
        "delisted_stock_price",
        "delisted_stock_price_json",
        "new_listing",
        "new_listing_json",
        "offering_price_change_rate",
        "offering_price_change_rate_json",
        "treasury_individual",
        "treasury_market",
        "supervised",
        "unfaithful_disclosure",
        "vi_triggered",
        "vi_triggered_csv",
        "short_selling_individual",
        "listing_special",
        "ipo_price_return",
        "listed_bonds",
        "listed_bonds_csv",
        "equity_index",
    ):
        assert required in names


def test_offering_price_change_rate_adjusted_price_option(monkeypatch):
    captured: list[dict] = []

    def fake_csv_download(bld, params, *, session=None, menu_id=None):
        captured.append(dict(params))
        return "col\n1\n".encode("EUC-KR")

    monkeypatch.setattr(client.transport, "csv_download", fake_csv_download)

    fetch(
        "offering_price_change_rate",
        mktId="KSQ",
        adjusted_price=False,
        strtDd="20260402",
        endDd="20260702",
    )
    fetch(
        "offering_price_change_rate",
        mktId="KSQ",
        adjusted_price=True,
        strtDd="20260402",
        endDd="20260702",
    )

    assert captured[0]["mktId"] == "KSQ"
    assert "inqCondTpCd" not in captured[0]
    assert captured[1]["mktId"] == "KSQ"
    assert captured[1]["inqCondTpCd"] == "Y"


def test_individual_price_trend_adjusted_price_option(monkeypatch):
    captured: list[dict] = []

    def fake_csv_download(bld, params, *, session=None, menu_id=None):
        captured.append(dict(params))
        return "col\n1\n".encode("EUC-KR")

    monkeypatch.setattr(client.transport, "csv_download", fake_csv_download)

    # 기본값: 수정주가 (adjStkPrc_check=Y, adjStkPrc=2)
    fetch(
        "individual_price_trend",
        isuCd="KR7005930003",
        strtDd="20260625",
        endDd="20260702",
    )
    # 원주가: adjStkPrc_check 미전송, adjStkPrc=1
    fetch(
        "individual_price_trend",
        isuCd="KR7005930003",
        strtDd="20260625",
        endDd="20260702",
        adjusted_price=False,
    )
    # 수정주가 기준일(adjBasDd) override
    fetch(
        "individual_price_trend",
        isuCd="KR7005930003",
        strtDd="20260625",
        endDd="20260702",
        adjBasDd="20200101",
    )

    # 기본 = 수정주가
    assert captured[0]["adjStkPrc_check"] == "Y"
    assert captured[0]["adjStkPrc"] == "2"
    # adjBasDd 미지정 시 오늘 날짜(YYYYMMDD 8자리)로 채워짐
    assert len(captured[0]["adjBasDd"]) == 8 and captured[0]["adjBasDd"].isdigit()

    # 원주가 = check 제거, adjStkPrc=1
    assert "adjStkPrc_check" not in captured[1]
    assert captured[1]["adjStkPrc"] == "1"

    # adjBasDd override 반영
    assert captured[2]["adjBasDd"] == "20200101"


def test_listed_stocks_returns_nonempty():
    df = fetch("listed_stocks")
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 100
    assert "ISU_CD" in df.columns
    assert "MKT_TP_NM" in df.columns


def test_all_stock_price_recent_day():
    df = fetch("all_stock_price", trdDd=_recent_trading_day())
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 100


def test_supervised_json():
    df = fetch("supervised")
    assert isinstance(df, pd.DataFrame)


def test_vi_triggered_json():
    day = _recent_trading_day()
    df = fetch("vi_triggered", strtDd=day, endDd=day)
    assert isinstance(df, pd.DataFrame)
    assert "VI_KIND_NM" in df.columns
    assert "VI_TG_TM" in df.columns


def test_ipo_price_return_json():
    df = fetch("ipo_price_return")
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "ASSTCOM_NM" in df.columns
    assert "PUBOFR_FINAL_PRC" in df.columns
