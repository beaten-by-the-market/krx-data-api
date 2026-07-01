# data.krx.co.kr 데이터를 사용하는 프로젝트 정리

KRX 정보데이터시스템(`data.krx.co.kr`)에서 데이터를 불러오는 코드가 포함된 프로젝트 폴더와 파일 목록입니다.

스캔 결과: **9개 프로젝트 폴더 · 46개 파일 · 155건의 호출**

---

## 사용되는 KRX 엔드포인트 패턴

KRX 정보데이터시스템에서 데이터를 가져오는 방식은 두 가지가 있고, 두 패턴 모두 코드 전반에서 사용됩니다.

### 1) JSON API (`getJsonData.cmd`)

```python
url = 'http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd'
data = {
    'bld': 'dbms/MDC/STAT/standard/MDCSTAT01901',  # 화면별로 bld가 다름
    'locale': 'ko_KR',
    ...
}
```

### 2) CSV 다운로드 (OTP 2단계 호출)

```python
gen_otp_url = 'http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd'
# ...OTP 발급
down_url = 'http://data.krx.co.kr/comm/fileDn/download_csv/download.cmd'
# Referer: http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=...
```

### 자주 쓰이는 `bld` (화면번호)

| bld | 화면번호 | 내용 |
|-----|---------|------|
| `dbms/MDC/STAT/standard/MDCSTAT01901` | 12005 | 전종목 기본정보 |
| `dbms/MDC/STAT/standard/MDCSTAT01501` | 12001 | 전종목 시세 |
| `dbms/MDC/STAT/standard/MDCSTAT01701` | 12003 | 개별종목 시세추이 |
| `dbms/MDC/STAT/standard/MDCSTAT02301` | 12009 | 투자자별 거래실적(개별종목) |
| `dbms/MDC/STAT/issue/MDCSTAT23801`    | 20037 | 상장폐지종목 현황 |
| `dbms/MDC/STAT/issue/MDCSTAT20001`    | 20001 | 신규/이전상장 |
| `dbms/MDC/STAT/issue/MDCSTAT20201`    | 20003 | 공모가대비 등락률 |
| `dbms/MDC/STAT/srt/MDCSTAT30101`      | 32001 | 개별종목 공매도 거래 |

---

## 프로젝트별 정리

### 1. [ad_hoc_issues/](ad_hoc_issues/)
DART 수시공시 처리 관련 스크립트. 종목코드/기업 기본정보를 KRX에서 결합.

- [annual_report_items.py](ad_hoc_issues/annual_report_items.py) — 3건
- [eng_discl_support.v2.py](ad_hoc_issues/eng_discl_support.v2.py) — 3건
- [get_bonus_issue.py](ad_hoc_issues/get_bonus_issue.py) — 6건 (전종목 기본정보 + 시세 결합)
- [supply_contract.py](ad_hoc_issues/supply_contract.py) — 4건

### 2. [adhoc_shareholdermeeting_agenda/](adhoc_shareholdermeeting_agenda/)
주주총회 소집공고 안건 분석. KRX 전종목 기본정보 사용.

- [주주총회소집공고_정관변경건.py](adhoc_shareholdermeeting_agenda/주주총회소집공고_정관변경건.py) — 1건
- [사업보고서_미상환CBBW.py](adhoc_shareholdermeeting_agenda/사업보고서_미상환CBBW.py) — 1건

### 3. [dart_disclosure/](dart_disclosure/)
DART 공시와 KRX 데이터를 결합하는 Jupyter 노트북 모음. 가장 빈번한 사용 폴더.

- [basic_listing_data.ipynb](dart_disclosure/basic_listing_data.ipynb) — 4건
- [bonusissue_getprice.ipynb](dart_disclosure/bonusissue_getprice.ipynb) — 6건
- [buyback_000390.ipynb](dart_disclosure/buyback_000390.ipynb) — 15건 (가장 호출 많음)
- [buyback_mkt20005.ipynb](dart_disclosure/buyback_mkt20005.ipynb) — 3건
- [kosdaq_buyback.ipynb](dart_disclosure/kosdaq_buyback.ipynb) — 4건
- [kospi_buyback.ipynb](dart_disclosure/kospi_buyback.ipynb) — 4건
- [kospi_buyback_mkt.ipynb](dart_disclosure/kospi_buyback_mkt.ipynb) — 4건
- [listing_special.ipynb](dart_disclosure/listing_special.ipynb) — 7건
- [stockcollateral.ipynb](dart_disclosure/stockcollateral.ipynb) — 6건
- [자사주_소각KIND.ipynb](dart_disclosure/자사주_소각KIND.ipynb) — 4건

### 4. [fairdisclosure/](fairdisclosure/)
공정공시(KIND) 관련. 상장사 종목코드 매핑 용도로 KRX 사용.

- [earningschangedisc.py](fairdisclosure/earningschangedisc.py) — 2건 (전종목 기본정보 + 상장폐지 현황)
- [fairdisc_kind.py](fairdisclosure/fairdisc_kind.py) — 2건
- [staff_ir_analysis.py](fairdisclosure/staff_ir_analysis.py) — 3건

### 5. [forecast_real/](forecast_real/)
실적예측 관련. KRX CSV 다운로드(전종목 기본정보, 개별종목 시세추이) 사용.

- [forecast_real.py](forecast_real/forecast_real.py) — 2건
- [stock_option.py](forecast_real/stock_option.py) — 3건

### 6. [krxnewsscrap/](krxnewsscrap/)
KRX vs NXT 비교, 채권 등 KRX 데이터 직접 활용 비중이 큰 폴더.

- [250713_dilution_dashboard_streamlit.py](krxnewsscrap/250713_dilution_dashboard_streamlit.py) — 3건
- [financial_st.py](krxnewsscrap/financial_st.py) — 3건
- [krxlistedbond.py](krxnewsscrap/krxlistedbond.py) — 3건 (화면 14011 상장채권 상세검색)
- [krxnxtplotly.py](krxnewsscrap/krxnxtplotly.py) — 3건
- [krxvsnxt.ipynb](krxnewsscrap/krxvsnxt.ipynb) — 3건
- [krxvsnxt_cumul.ipynb](krxnewsscrap/krxvsnxt_cumul.ipynb) — 6건
- [nxtvskrx.py](krxnewsscrap/nxtvskrx.py) — 3건
- [predictprice.py](krxnewsscrap/predictprice.py) — 6건

### 7. [seibro/](seibro/)
SEIBRO 기반 분석. 종목 메타데이터 매핑·시세 결합에 KRX 사용.

- [250713_dilution_dashboard.py](seibro/250713_dilution_dashboard.py) — 3건
- [250713_dilution_dashboard_crawl.py](seibro/250713_dilution_dashboard_crawl.py) — 3건
- [250713_dilution_dashboard_streamlit.py](seibro/250713_dilution_dashboard_streamlit.py) — 3건
- [elec_cb_status.py](seibro/elec_cb_status.py) — 1건
- [seibro_anlysis.py](seibro/seibro_anlysis.py) — 1건
- [seibro_cbbw.py](seibro/seibro_cbbw.py) — 2건
- [seibro_data_get_azure.py](seibro/seibro_data_get_azure.py) — 2건
- [value_up.py](seibro/value_up.py) — 1건

### 8. [xbrl_validation/](xbrl_validation/)
DART XBRL 데이터 검증. KRX 종목 마스터 결합용.

- [dart_gcd_extract.py](xbrl_validation/dart_gcd_extract.py) — 1건
- [dart_stockoption_extract.py](xbrl_validation/dart_stockoption_extract.py) — 7건
- [stockoption_endow.py](xbrl_validation/stockoption_endow.py) — 3건

### 9. [beaten-by-the-market.github.io/](beaten-by-the-market.github.io/)
블로그 글(예제 코드 포함). 실제 실행 코드라기보다 코드 인용/설명.

- [_posts/2025-01-21-buybackexplanation.md](beaten-by-the-market.github.io/_posts/2025-01-21-buybackexplanation.md)
- [_posts/2025-01-22-buybackexplanation2.md](beaten-by-the-market.github.io/_posts/2025-01-22-buybackexplanation2.md)
- [_posts/2025-01-27-dartandkrx.md](beaten-by-the-market.github.io/_posts/2025-01-27-dartandkrx.md)
- [_posts/2025-02-13-bonusissue_getprice-code.md](beaten-by-the-market.github.io/_posts/2025-02-13-bonusissue_getprice-code.md) — 6건
- [_posts/2025-03-01-listing_special.md](beaten-by-the-market.github.io/_posts/2025-03-01-listing_special.md)
- [_posts/2025-03-16-buyback_mkt.md](beaten-by-the-market.github.io/_posts/2025-03-16-buyback_mkt.md)

---

## 요약

| 폴더 | 파일 수 | 주된 용도 |
|------|--------|-----------|
| dart_disclosure | 10 | DART 공시 + KRX 결합 (가장 활발) |
| krxnewsscrap | 8 | KRX/NXT 비교, 채권, dilution 분석 |
| seibro | 7 | SEIBRO 분석 보조 데이터로 KRX 활용 |
| beaten-by-the-market.github.io | 6 | 블로그 글 (예제 코드) |
| ad_hoc_issues | 4 | DART 수시공시 분석 |
| fairdisclosure | 3 | 공정공시 종목 매핑 |
| xbrl_validation | 3 | DART XBRL 검증 |
| adhoc_shareholdermeeting_agenda | 2 | 주총 안건 분석 |
| forecast_real | 2 | 실적예측 |

**공통 패턴**: 거의 모든 프로젝트가 "DART/SEIBRO 등 다른 공시 데이터" + "KRX 전종목 기본정보(MDCSTAT01901)"를 결합하는 형태로 KRX를 사용합니다. 즉 KRX는 대부분 **종목 마스터/시세 보조 데이터** 역할입니다.
