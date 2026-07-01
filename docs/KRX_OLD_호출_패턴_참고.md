# KRX 데이터 호출 - 구(old) 코드 패턴 참고

`krx-data-api` 패키지로 마이그레이션하기 전, 30개 .py 파일에서 반복되던 직접 호출 코드.
**현재는 이 패턴 그대로는 작동하지 않습니다** (2026-05 KRX 정책 변경으로 로그인 세션 필수).
혹시 모를 디버깅·참고용으로만 남깁니다.

대체된 새 사용법: `from krx_data_api import fetch; df = fetch("listed_stocks")` 등.
자세한 내용은 [krx-data-api/README.md](krx-data-api/README.md).

---

## 패턴 1 - CSV 다운로드 (OTP 2단계)

가장 흔한 패턴. 전종목 기본정보·시세·자사주·채권 등 대부분 화면.

```python
import requests
import pandas as pd
from io import BytesIO

# Step 1: OTP 발급
gen_otp_url = 'http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd'
gen_otp = {
    'locale': 'ko_KR',
    'mktId': 'ALL',
    'share': '1',
    'csvxls_isNo': 'false',
    'name': 'fileDown',
    'url': 'dbms/MDC/STAT/standard/MDCSTAT01901',  # 화면별로 다름
}
headers = {
    'Referer': 'http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020201',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...',
}
otp = requests.post(gen_otp_url, gen_otp, headers=headers).text

# Step 2: OTP로 CSV 다운로드
down_url = 'http://data.krx.co.kr/comm/fileDn/download_csv/download.cmd'
down_content = requests.post(down_url, {'code': otp}, headers=headers)

# Step 3: EUC-KR로 디코딩
df = pd.read_csv(BytesIO(down_content.content), encoding='EUC-KR')

# Step 4 (관용): KOSDAQ GLOBAL 정규화·컬럼 rename
df['시장구분'] = df['시장구분'].replace('KOSDAQ GLOBAL', 'KOSDAQ')
df = df.rename(columns={'단축코드': 'stock_code'})
```

**새 방식 한 줄**:
```python
df = fetch("listed_stocks")
df = df.rename(columns={'단축코드': 'stock_code'})  # KOSDAQ GLOBAL은 자동 정규화
```

---

## 패턴 2 - JSON API (`getJsonData.cmd`)

관리종목·불성실공시·신규상장 등 일부 화면에서 사용.

```python
import requests
import pandas as pd

url = 'http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd'
data = {
    'bld': 'dbms/MDC/STAT/issue/MDCSTAT21401',
    'locale': 'ko_KR',
    'mktId': 'ALL',
    'csvxls_isNo': 'false',
}
r = requests.post(url, data=data)
df_dict = pd.read_json(r.content.decode('utf-8'))

# 응답을 DataFrame으로 평탄화 (관용 패턴)
df = pd.DataFrame()
for i in range(len(df_dict)):
    dict_ex = df_dict.output[i]
    df_ex = pd.DataFrame(list(dict_ex.items())).transpose()
    df_ex2 = df_ex.rename(columns=df_ex.iloc[0])
    df_ex3 = df_ex2.drop(df_ex2.index[0])
    df = pd.concat([df, df_ex3], ignore_index=True)
```

**새 방식 한 줄**:
```python
df = fetch("supervised")
```

---

## 자주 쓰이던 `bld` (화면번호) 매핑

| bld | 화면번호 | 한글명 | 새 패키지 이름 |
|-----|---------|-------|--------------|
| `dbms/MDC/STAT/standard/MDCSTAT01901` | 12005 | 전종목기본정보 | `listed_stocks` |
| `dbms/MDC/STAT/standard/MDCSTAT01501` | 12001 | 전종목시세 | `all_stock_price` |
| `dbms/MDC/STAT/standard/MDCSTAT01701` | 12003 | 개별종목시세추이 | `individual_price_trend` |
| `dbms/MDC/STAT/standard/MDCSTAT02301` | 12009 | 투자자별 거래실적(개별종목) | `investor_trading_individual` |
| `dbms/MDC/STAT/standard/MDCSTAT02301` | 12009 | 투자자별 거래실적(개별종목)(JSON) | `investor_trading_individual_json` |
| `dbms/MDC/STAT/issue/MDCSTAT23801` | 20037 | 상장폐지종목 현황 | `delisted` |
| `dbms/MDC/STAT/issue/MDCSTAT23801` | 20037 | 상장폐지종목 현황(JSON) | `delisted_json` |
| `dbms/MDC/STAT/issue/MDCSTAT20001` | 20001 | 신규상장종목 현황 | `new_listing` |
| `dbms/MDC/STAT/issue/MDCSTAT20001` | 20001 | 신규상장종목 현황(JSON) | `new_listing_json` |
| `dbms/MDC/STAT/issue/MDCSTAT20201` | 20003 | 공모가대비 등락률 | `offering_price_change_rate` |
| `dbms/MDC/STAT/issue/MDCSTAT20201` | 20003 | 공모가대비 등락률(JSON) | `offering_price_change_rate_json` |
| `dbms/MDC/STAT/issue/MDCSTAT20601` | 20005 | 자사주취득/처분(개별) | `treasury_individual` |
| `dbms/MDC/STAT/issue/MDCSTAT20701` | 20005 | 자사주취득/처분(전체) | `treasury_market` |
| `dbms/MDC/STAT/issue/MDCSTAT21401` | 20012 | 관리종목현황 | `supervised` |
| `dbms/MDC/STAT/issue/MDCSTAT22001` | 20018 | 불성실공시법인 | `unfaithful_disclosure` |
| `dbms/MDC/STAT/issue/MDCSTAT24401` | - | 상장특례 현황 | `listing_special` |
| `dbms/MDC/STAT/issue/MDCSTAT22401` | 20023 | 변동성완화장치 발동종목 현황(CSV) | `vi_triggered_csv` |
| `dbms/MDC/STAT/srt/MDCSTAT30101` | 32001 | 개별종목 공매도 거래 | `short_selling_individual` |
| `dbms/MDC/STAT/standard/MDCSTAT10801` | 14011 | 상장채권 상세검색 | `listed_bonds` |
| `dbms/MDC/STAT/standard/MDCSTAT00301` | - | 지수 시세추이 | `equity_index` |

## `menuId` (Referer)

| menuId | 용도 |
|--------|------|
| `MDC0201020201` | 주식·기본정보 화면 (기본값) |
| `MDC03010201` | 자사주·채권 화면 |
| `MDC0202` | 상장특례 등 일부 |
| `MDC0203` | 공매도 통계 |
| `MDC02021301` | 신규/이전상장 |
| `MDC0201020101` | 기업정보 |

## 헤더 (모든 호출 동일)

```python
{
    'Referer': 'http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=...',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
}
```

---

## 2026-05 정책 변경 (왜 옛 코드가 깨졌나)

- 비로그인 세션에서 OTP를 요청하면 응답이 `'LOGOUT'` 6글자 문자열 (HTTP 200, content-type=octet-stream).
- 비로그인 세션에서 JSON API를 호출하면 본문이 `'LOGOUT'` (HTTP 400, content-type=text/html).
- 이전에는 공개 화면(전종목 기본정보 등)도 비로그인으로 가능했음. 변경 후로는 모든 호출이 KRX 자체계정 로그인 필수.
- 새 패키지 `krx-data-api`는 이 시그널을 자동 감지해 로그인 후 재시도하는 구조. 자세한 인증 매뉴얼은 [KRX_로그인_세션_매뉴얼.md](KRX_로그인_세션_매뉴얼.md).
