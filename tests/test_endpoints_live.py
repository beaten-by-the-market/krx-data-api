"""Live tests that call KRX.

Run: pytest tests/test_endpoints_live.py
Skip: set KRX_SKIP_LIVE=1.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd
import pytest

from krx_data_api import fetch, list_endpoints

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
        "delisted",
        "delisted_json",
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
