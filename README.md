# krx-data-api

KRX 정보데이터시스템(`data.krx.co.kr`) 호출을 친절한 이름의 함수로 래핑한 Python 패키지.

- OTP 2단계 CSV 다운로드와 `getJsonData.cmd` JSON API를 같은 `fetch()` 인터페이스로
- 셀레니움 미사용 → Google Colab에서도 동일하게 작동
- **2026-05 시점 변경:** KRX가 모든 OTP CSV 다운로드에 로그인을 요구하도록 정책을 강화했습니다.
  `fetch()`는 OTP 응답이 `'LOGOUT'`이면 자동으로 `KRX_ID`/`KRX_PW` 자격증명으로 로그인 후 재시도합니다.
  자격증명이 없으면 `KRXAuthRequiredError`가 발생합니다.

## 설치

```bash
pip install git+https://github.com/beaten-by-the-market/krx-data-api.git
```

Colab에서는 앞에 `!` 를 붙입니다.

## 사용법

> 2026-05 시점 KRX 정책 변경으로, 이 패키지의 **모든 호출은 KRX 자체계정 로그인이 필요**합니다.
> 따라서 자격증명 설정이 첫 단계입니다.

### 1단계 — 자격증명 설정 (필수)

KRX 자체계정의 ID/PW를 환경변수 `KRX_ID` / `KRX_PW`로 등록합니다. 
한번 등록해두면 첫 `fetch()` 호출 시 자동 로그인되고, 25분간 같은 세션이 재사용됩니다.

**로컬 (PC):** 프로젝트를 실행할 작업 디렉터리(노트북이 있는 폴더)에 `.env` 파일을 만들고 아래 내용 저장:
```
KRX_ID=your_id
KRX_PW=your_password
```
`python-dotenv`가 의존성에 포함되어 있어 자동으로 읽힙니다. 
`.env`는 `.gitignore`에 추가해서 커밋되지 않도록 하세요.

**Google Colab:** 좌측 사이드바의 🔑 (Secrets)에 `KRX_ID`, `KRX_PW`를 등록한 뒤, 노트북 첫 셀에:
```python
from google.colab import userdata
import os
os.environ["KRX_ID"] = userdata.get("KRX_ID")
os.environ["KRX_PW"] = userdata.get("KRX_PW")
```

자격증명 미설정 시 첫 호출에서 `KRXAuthRequiredError`가 발생합니다.

### 2단계 — 데이터 가져오기

```python
from krx_data_api import fetch

# 전종목 기본정보 (가장 흔히 쓰는 종목 마스터)
df = fetch("listed_stocks")

# 전종목 시세
df = fetch("all_stock_price", trdDd="20260526")

# 개별종목 시세추이
df = fetch("individual_price_trend",
           isuCd="KR7005930003", strtDd="20250101", endDd="20260101")

# 상장폐지종목
df = fetch("delisted", strtDd="20240101", endDd="20260101")

# 신규상장 (JSON API)
df = fetch("new_listing", strtDd="20250101", endDd="20260101")

# 자사주취득/처분 — 개별종목
df = fetch("treasury_individual",
           isuCd="KR7000390005", strtDd="20180101", endDd="20211231")

# 자사주취득/처분 — 시장 전체
df = fetch("treasury_market", strtDd="20240101", endDd="20260101")

# 상장채권 상세검색
df = fetch("listed_bonds")
```

사용 가능한 엔드포인트 목록 전체는 아래 [엔드포인트 카탈로그](#엔드포인트-카탈로그-v010) 표 참조. 
프로그래밍적으로 확인하려면:
```python
from krx_data_api import list_endpoints, endpoint_info
print(list_endpoints())                 # 모든 이름 리스트
print(endpoint_info("all_stock_price")) # 특정 엔드포인트 상세
```

### 3단계 (선택) — 고급 사용

대부분 `fetch("name")` 한 줄로 충분합니다. 다음은 특수한 경우에만 필요한 옵션들입니다.

**`auth=True`** — 첫 호출 전에 미리 로그인. 호출 횟수 한 번 절약:
```python
df = fetch("listed_stocks", auth=True)
```
없어도 첫 호출이 `LOGOUT`을 받으면 자동 로그인 후 재시도하므로 결과는 동일합니다.

**`get_krx_auth()`** — `requests.Session`을 직접 다뤄야 할 때:
```python
from krx_data_api import get_krx_auth
auth = get_krx_auth()
print(auth.mbr_no)       # 로그인된 MBR_NO
session = auth.session   # requests.Session 그대로 사용
```

> **참고** — KRX 로그인 응답이 `_error_code == "CD007"`이면 `MBR_NO`가 발급되더라도
> 실제로는 인증되지 않은 위장 성공입니다. `auth.py`는 **`CD001`만 성공으로 인정**하고
> 그 외에는 `KRXAuthError`를 던집니다 (자동으로 처리되므로 사용자가 신경 쓸 일은 없음).

## 카탈로그에 없는 새 화면 호출

`endpoints.py`에 등록되지 않은 새 `bld`도 transport 함수로 직접 호출 가능:

```python
from krx_data_api import transport
import pandas as pd
from io import BytesIO

raw = transport.csv_download(
    bld="dbms/MDC/STAT/standard/MDCSTAT99999",
    params={"mktId": "STK", "trdDd": "20260526"},
    menu_id="MDC0201020201",
)
df = pd.read_csv(BytesIO(raw), encoding="EUC-KR")
```

자주 쓰는 화면이라면 `krx_data_api/endpoints.py`의 `ENDPOINTS` dict에 추가하는 것을 권장.

## 엔드포인트 카탈로그 (v0.1.0)

| 이름 | bld | 화면 | 방식 |
|------|-----|------|------|
| `listed_stocks` | `MDCSTAT01901` | 12005 전종목기본정보 | CSV |
| `all_stock_price` | `MDCSTAT01501` | 12001 전종목시세 | CSV |
| `individual_price_trend` | `MDCSTAT01701` | 12003 개별종목시세추이 | CSV |
| `delisted` | `MDCSTAT23801` | 20037 상장폐지종목 현황 | CSV |
| `new_listing` | `MDCSTAT20001` | 20001 신규상장종목 현황 | JSON |
| `treasury_individual` | `MDCSTAT20601` | 20005 자사주취득/처분(개별) | CSV |
| `treasury_market` | `MDCSTAT20701` | 20005 자사주취득/처분(전체) | CSV |
| `supervised` | `MDCSTAT21401` | 20012 관리종목현황 | JSON |
| `unfaithful_disclosure` | `MDCSTAT22001` | 20018 불성실공시법인 | JSON |
| `listing_special` | `MDCSTAT24401` | 상장특례 현황 | CSV |
| `listed_bonds` | `MDCSTAT10801` | 14011 상장채권 상세검색 | CSV |
| `equity_index` | `MDCSTAT00301` | 지수 시세추이 | CSV |

## 패키지 구조

```
krx_data_api/
├── __init__.py        공개 API re-export
├── transport.py       OTP 2단계 / JSON API 저수준 (내부 사용 권장)
├── auth.py            로그인 싱글톤 (CD001만 성공)
├── endpoints.py       12개 bld 카탈로그
├── client.py          fetch() + 후처리 레지스트리
└── exceptions.py
```

## 라이선스 / 관련

- 매뉴얼: [docs/KRX_로그인_세션_매뉴얼.md](docs/KRX_로그인_세션_매뉴얼.md)
- 사용 프로젝트 인벤토리: [docs/KRX_데이터_프로젝트_정리.md](docs/KRX_데이터_프로젝트_정리.md)
- 구 호출 패턴 참고: [docs/KRX_OLD_호출_패턴_참고.md](docs/KRX_OLD_호출_패턴_참고.md)
