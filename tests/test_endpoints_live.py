"""실제 KRX 호출을 수행하는 라이브 테스트.

실행: pytest tests/test_endpoints_live.py
스킵: KRX_SKIP_LIVE=1 환경변수 설정 시 전체 스킵.
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
    """대략 최근 영업일. 주말이면 금요일로."""
    d = datetime.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def test_catalog_lists_12_endpoints():
    names = list_endpoints()
    assert len(names) >= 12
    for required in (
        "listed_stocks",
        "all_stock_price",
        "individual_price_trend",
        "delisted",
        "new_listing",
        "treasury_individual",
        "treasury_market",
        "supervised",
        "unfaithful_disclosure",
        "listing_special",
        "listed_bonds",
        "equity_index",
    ):
        assert required in names


def test_listed_stocks_returns_nonempty():
    df = fetch("listed_stocks")
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 100  # 전체 종목이면 수천 행
    assert "시장구분" in df.columns
    # KOSDAQ GLOBAL이 KOSDAQ으로 정규화돼야 한다
    assert "KOSDAQ GLOBAL" not in df["시장구분"].unique()


def test_all_stock_price_recent_day():
    df = fetch("all_stock_price", trdDd=_recent_trading_day())
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 100


def test_supervised_json():
    df = fetch("supervised")
    assert isinstance(df, pd.DataFrame)
