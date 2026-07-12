# krx-data-api

KRX 정보데이터시스템(`data.krx.co.kr`) 호출을 endpoint 이름 기반 `fetch()` 함수로 감싼 Python 패키지입니다.

- `getJsonData.cmd` JSON API와 OTP 2단계 CSV 다운로드를 같은 `fetch()` 인터페이스로 호출합니다.
- KRX 로그인 세션이 필요한 호출은 `KRX_ID` / `KRX_PW` 환경변수로 자동 로그인합니다.
- 기간 조회에서 CSV가 JSON보다 긴 기간을 허용하는 화면은 CSV를 기본 방식으로 둡니다.

## 설치

```bash
pip install git+https://github.com/beaten-by-the-market/krx-data-api.git
```

## 인증 설정

프로젝트 루트의 `.env`에 KRX 계정 정보를 저장합니다.

```text
KRX_ID=your_id
KRX_PW=your_password
```

Google Colab에서는 Secrets에서 읽어 환경변수로 넣으면 됩니다.

```python
from google.colab import userdata
import os

os.environ["KRX_ID"] = userdata.get("KRX_ID")
os.environ["KRX_PW"] = userdata.get("KRX_PW")
```

## 네이밍 원칙

동일 화면에 CSV와 JSON 방식이 모두 등록된 경우, **기본 이름은 현재 권장 방식**입니다.

- **기간형 화면에서 CSV가 JSON보다 긴 기간을 조회할 수 있으면 기본 이름은 CSV**입니다.
- **기간 이점이 없거나 비기간형 화면이면 기본 이름은 JSON**입니다.
- 보조 방식은 **`_csv` 또는 `_json` suffix**를 붙입니다.
- `ipo_price_return` / `listing_special`처럼 같은 `bld`라도 화면 의미와 파라미터가 다르면 별도 이름을 유지합니다.

예를 들면 `new_listing`은 CSV가 긴 기간에 유리하므로 **기본 CSV**이고, JSON 보조 방식은 `new_listing_json`입니다. 반대로 `listed_stocks`는 **JSON이 기본**이고 CSV 보조 방식은 `listed_stocks_csv`입니다.

## 사용 예시

```python
from krx_data_api import fetch

# 전종목 기본정보: JSON 기본
df = fetch("listed_stocks")
df_csv = fetch("listed_stocks_csv")

# 전종목 시세: JSON 기본
df = fetch("all_stock_price", trdDd="20260701")
df_csv = fetch("all_stock_price_csv", trdDd="20260701")

# 개별종목 시세추이: 기간형 CSV
# 기본은 수정주가이며, 수정주가 기준일(adjBasDd)은 지정하지 않으면 오늘 날짜입니다.
df = fetch(
    "individual_price_trend",
    isuCd="KR7005930003",
    strtDd="20250101",
    endDd="20260101",
)
# 원주가(비수정)로 조회하려면 adjusted_price=False.
df_raw = fetch(
    "individual_price_trend",
    isuCd="KR7005930003",
    strtDd="20250101",
    endDd="20260101",
    adjusted_price=False,
)
# 수정주가 기준일을 특정 시점으로 고정하려면 adjBasDd 지정.
df_adj_base = fetch(
    "individual_price_trend",
    isuCd="KR7005930003",
    strtDd="20250101",
    endDd="20260101",
    adjBasDd="20260101",
)

# 투자자별 거래실적(개별종목): 기간형 CSV 기본, JSON 보조
df = fetch(
    "investor_trading_individual",
    isuCd="KR7005930003",
    isuCd2="005930",
    strtDd="20260623",
    endDd="20260630",
)
df_json = fetch(
    "investor_trading_individual_json",
    isuCd="KR7005930003",
    isuCd2="005930",
    strtDd="20260623",
    endDd="20260630",
)

# 투자자별 거래실적(개별종목) "일별추이": 날짜가 행, 투자자 유형이 열.
# askBid=1 매수 / 2 매도 / 3 순매수(기본), trdVolVal=1 거래량 / 2 거래대금(기본)
df_daily = fetch(
    "investor_trading_individual_daily",
    isuCd="KR7005930003",
    strtDd="20260625",
    endDd="20260701",
)                                  # 기본: 순매수 거래대금
df_daily_buy = fetch(
    "investor_trading_individual_daily",
    isuCd="KR7005930003",
    strtDd="20260625",
    endDd="20260701",
    askBid="1",                    # 매수
)
df_daily_json = fetch(
    "investor_trading_individual_daily_json",
    isuCd="KR7005930003",
    strtDd="20260625",
    endDd="20260701",
)

# 상장폐지종목: 긴 기간은 CSV 기본
df = fetch("delisted", strtDd="20240101", endDd="20260701")
df_json = fetch("delisted_json", strtDd="20260624", endDd="20260701")

# 상장폐지종목 시세: CSV 기본, JSON 보조
# 주의: 이 화면(MDCSTAT23902)은 "원주가"만 제공합니다 (수정주가 옵션 없음).
df = fetch(
    "delisted_stock_price",
    isuCd="KR7164060006",
    strtDd="20231023",
    endDd="20241022",
)
df_json = fetch(
    "delisted_stock_price_json",
    isuCd="KR7164060006",
    strtDd="20231023",
    endDd="20241022",
)

# 상폐종목의 "수정주가"가 필요하면 individual_price_trend를 사용하세요.
# 상폐종목도 조회되며, 기준일(adjBasDd)은 상장폐지일로 주는 게 정석입니다.
# (상폐 후에는 이벤트가 없어 기준일을 오늘로 둬도 결과는 동일합니다.)
df_adj = fetch(
    "individual_price_trend",
    isuCd="KR7164060006",   # 이루다 (상폐 2024-10-22)
    strtDd="20200806",
    endDd="20241022",
    adjBasDd="20241022",    # 상장폐지일 기준
)

# 신규상장종목 현황: 긴 기간은 CSV 기본
df = fetch("new_listing", strtDd="20240101", endDd="20260701")
df_json = fetch("new_listing_json", strtDd="20260401", endDd="20260701")

# 공모가대비 등락률: 긴 기간은 CSV 기본
df = fetch("offering_price_change_rate", strtDd="20240101", endDd="20260701")
df_json = fetch("offering_price_change_rate_json", strtDd="20260401", endDd="20260701")

# 공모가대비 등락률: 기존 엔드포인트에서 코스닥 only CSV 옵션 지정
# 보통주가(미수정 주가) 버전은 inqCondTpCd를 보내지 않고,
# 수정주가 적용 버전은 KRX 화면 체크 값인 inqCondTpCd="Y"를 보냅니다.
df_kosdaq_common = fetch(
    "offering_price_change_rate",
    mktId="KSQ",
    adjusted_price=False,
    strtDd="20260402",
    endDd="20260702",
)
df_kosdaq_adjusted = fetch(
    "offering_price_change_rate",
    mktId="KSQ",
    adjusted_price=True,
    strtDd="20260402",
    endDd="20260702",
)

# 변동성완화장치 발동종목 현황: JSON 기본, CSV 보조
df = fetch("vi_triggered", strtDd="20260701", endDd="20260701")
df_csv = fetch("vi_triggered_csv", strtDd="20260701", endDd="20260701")

# 개별종목 공매도 거래
df = fetch("short_selling_individual", trdDd="20260701")

# 매매거래정지 종목 현황: 종목 지정 필수, 조회기간 최대 2년
# JSON은 정지 직전 최종매매일 시세(종가·거래량·시가총액)까지 포함합니다.
df = fetch(
    "trading_halt",
    isuCd="KR7000300004",
    isuCd2="000300",
    strtDd="20240101",
    endDd="20251231",
)
df_csv = fetch(
    "trading_halt_csv",
    isuCd="KR7000300004",
    isuCd2="000300",
    strtDd="20240101",
    endDd="20251231",
)
```

목록과 상세 정보는 프로그래밍 방식으로 확인할 수 있습니다.

```python
from krx_data_api import list_endpoints, endpoint_info

print(list_endpoints())
print(endpoint_info("new_listing"))
```

## 직접 호출

카탈로그에 없는 `bld`도 transport 함수로 직접 호출할 수 있습니다.

```python
from io import BytesIO
import pandas as pd
from krx_data_api import transport

raw = transport.csv_download(
    bld="dbms/MDC/STAT/standard/MDCSTAT99999",
    params={"mktId": "STK", "trdDd": "20260701"},
    menu_id="MDC0201020201",
)
df = pd.read_csv(BytesIO(raw), encoding="EUC-KR")
```

## 엔드포인트 카탈로그

| 이름 | bld | 화면 | 방식 |
|------|-----|------|------|
| `listed_stocks` | `MDCSTAT01901` | 12005 전종목기본정보 | JSON |
| `listed_stocks_csv` | `MDCSTAT01901` | 12005 전종목기본정보 | CSV |
| `all_stock_price` | `MDCSTAT01501` | 12001 전종목시세 | JSON |
| `all_stock_price_csv` | `MDCSTAT01501` | 12001 전종목시세 | CSV |
| `individual_price_trend` | `MDCSTAT01701` | 12003 개별종목시세추이 | CSV |
| `investor_trading_individual` | `MDCSTAT02301` | 12009 투자자별 거래실적(개별종목) | CSV |
| `investor_trading_individual_json` | `MDCSTAT02301` | 12009 투자자별 거래실적(개별종목) | JSON |
| `investor_trading_individual_daily` | `MDCSTAT02303` | 12009 투자자별 거래실적(개별종목) 일별추이 | CSV |
| `investor_trading_individual_daily_json` | `MDCSTAT02303` | 12009 투자자별 거래실적(개별종목) 일별추이 | JSON |
| `delisted` | `MDCSTAT23801` | 20037 상장폐지종목 현황 | CSV |
| `delisted_json` | `MDCSTAT23801` | 20037 상장폐지종목 현황 | JSON |
| `delisted_stock_price` | `MDCSTAT23902` | Delisted stock price data | CSV |
| `delisted_stock_price_json` | `MDCSTAT23902` | Delisted stock price data | JSON |
| `new_listing` | `MDCSTAT20001` | 20001 신규상장종목 현황 | CSV |
| `new_listing_json` | `MDCSTAT20001` | 20001 신규상장종목 현황 | JSON |
| `offering_price_change_rate` | `MDCSTAT20201` | 20003 공모가대비 등락률 | CSV |
| `offering_price_change_rate_json` | `MDCSTAT20201` | 20003 공모가대비 등락률 | JSON |
| `treasury_individual` | `MDCSTAT20601` | 20005 자사주취득/처분내역(개별종목) | CSV |
| `treasury_market` | `MDCSTAT20701` | 20005 자사주취득/처분내역(전체) | CSV |
| `supervised` | `MDCSTAT21401` | 20012 관리종목현황 | JSON |
| `unfaithful_disclosure` | `MDCSTAT22001` | 20018 불성실공시법인 현황 | JSON |
| `vi_triggered` | `MDCSTAT22401` | 20023 변동성완화장치 발동종목 현황 | JSON |
| `vi_triggered_csv` | `MDCSTAT22401` | 20023 변동성완화장치 발동종목 현황 | CSV |
| `trading_halt` | `MDCSTAT21301` | 매매거래정지 종목 현황 | JSON |
| `trading_halt_csv` | `MDCSTAT21301` | 매매거래정지 종목 현황 | CSV |
| `short_selling_individual` | `MDCSTAT30101` | 32001 개별종목 공매도 거래 | JSON |
| `listing_special` | `MDCSTAT24401` | 상장특례 현황 | CSV |
| `ipo_price_return` | `MDCSTAT24401` | 20043 공모가 대비 주가수익률 | JSON |
| `listed_bonds` | `MDCSTAT10801` | 14011 상장채권 상세검색 | JSON |
| `listed_bonds_csv` | `MDCSTAT10801` | 14011 상장채권 상세검색 | CSV |
| `etf_price_trend` | `MDCSTAT04501` | 개별종목 시세추이 | CSV |
| `etf_all_info` | `MDCSTAT04601` | 전종목 기본정보 | CSV |
| `equity_index` | `MDCSTAT00301` | 지수 시세추이 | CSV |

## 프로젝트 구조
_
```text
krx_data_api/
├── __init__.py        공개 API re-export
├── transport.py       OTP CSV / JSON 저수준 호출
├── auth.py            KRX 로그인 세션 관리
├── endpoints.py       25개 endpoint 카탈로그
├── client.py          fetch()와 후처리 레지스트리
└── exceptions.py
```
