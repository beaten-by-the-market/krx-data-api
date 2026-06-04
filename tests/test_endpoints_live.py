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
        "vi_triggered",
        "listing_special",
        "ipo_price_return",
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


def test_vi_triggered_json():
    day = _recent_trading_day()
    df = fetch("vi_triggered", strtDd=day, endDd=day)
    assert isinstance(df, pd.DataFrame)
    # VI 발동 현황의 핵심 컬럼
    assert "VI_KIND_NM" in df.columns
    assert "VI_TG_TM" in df.columns


def test_ipo_price_return_json():
    df = fetch("ipo_price_return")
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    # 공모가 대비 주가수익률 화면의 핵심 컬럼
    assert "ASSTCOM_NM" in df.columns
    assert "PUBOFR_FINAL_PRC" in df.columns
