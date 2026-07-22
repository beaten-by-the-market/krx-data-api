# 관리종목 조기경보 대시보드 — 설계·데이터 계약

배치(수집·판정)와 표시(정적 프론트엔드)를 분리한다. 배치는 자격증명이 있는 환경에서
`dashboard.build_dashboard_artifacts()`를 돌려 JSON artifacts를 만들고, 정적 대시보드
(GitHub Pages 등)가 그 JSON을 읽는다. 프론트를 자유롭게 갈아끼울 수 있도록 스키마를 고정한다.

```
[배치: 자격증명 O]                               [공개: 자격증명 X]
KRX 전종목시세 → 캐시(daily_snapshots)            artifacts(JSON) → 정적 대시보드
KIND 유니버스 → screener → dashboard.build_… →   (버전=as_of)       (client 필터/정렬/차트)
KRX supervised(옵션, 공식 대조)
```

## 퍼널(생애주기) 상태 모델

종목×사유(mktcap/price)마다 하나의 state를 갖는다. 스크리너에서 기계적으로 도출한다.

```
normal ─(미달 streak↑)→ approaching ─(30)→ designated ─(이상 streak↑)→ release_pending ─(45)→ (해제)
                                              │
                              (주가미달만) └─(90거래일 미회복/병합·감자)→ delisting_risk → delisting_confirmed
```

| state | 도출 |
|---|---|
| `approaching` | 미지정 & 미달 연속 ≥ approach_threshold(기본 20) |
| `designated` | 상태기계상 지정(SUPERVISED) |
| `release_pending` | 지정 & 이상 연속 ≥ release_pending_threshold(기본 30) |
| `delisting_risk` | 주가미달 지정 & 90거래일 회복창 미회복(관찰중) |
| `delisting_confirmed` | 상폐확정/조기확정 |

정상(normal)은 artifacts에서 제외한다.

## 판정 규칙(부칙 반영)

- 시가총액 미달 기준 = **시장×시기별**(`screener.MKTCAP_SCHEDULE`): 코스닥 150→200(→300)억,
  유가 200→300(→500)억. 각 날짜가 속한 구간 기준으로 미달 판단, 일수는 연속 산정.
- 주가 미달(1,000원) = 시행일 **2026.7.1 이후**부터 산정(`screener.PRICE_COUNT_START`).
- 지정 연속 30거래일 / 해제 연속 45거래일 / 주가미달 상폐 회복창 90거래일.

## artifacts (build_dashboard_artifacts 반환 / out_json 저장)

하나의 JSON에 아래 5키. (대규모화하면 파일 분리 가능.)

### meta
```json
{ "as_of":"20260721", "generated_at":"2026-07-22T17:30:00",
  "rule":{"mktcap_schedule":{...},"price_threshold":1000,"designate_days":30,
          "release_days":45,"price_count_start":"20260701","delist_window_days":90},
  "universe_count":2552, "cache":{"first":"20260401","last":"20260721","trading_days":75},
  "official_available":true, "disclaimer":"...", "countdown_note":"..." }
```

### counts (KPI·퍼널)
```json
{ "mktcap_designated":34,"price_designated":0,"approaching":19,
  "release_pending":0,"delisting_risk":0,"imminent_D5":4 }
```

### reconcile (내 추정 vs KRX 공식; official_available=false면 null)
```json
{ "mktcap":{"official":14,"matched":14,"estimate_only":20,"missed":0},
  "price":{"official":0,"matched":0,"estimate_only":0,"missed":0} }
```

### rows (종목×사유 롱; state≠normal만) — 워치리스트/퍼널의 본체
```json
{ "code":"067770","name":"세진티에스","market":"KOSDAQ","reason":"mktcap",
  "state":"designated","streak":19,"streak_kind":"sufficient","target":45,
  "value":14870366203,"threshold":20000000000,"gap_pct":-25.6,
  "official":true,"official_design_date":"20260721","estimated_effective":"20260721",
  "countdown":{"basis":"trading_days","to_designation":null,"to_release":26,
               "to_delisting":null,"to_early_delisting":null},
  "delisting":null }
```
- `official`(KRX 공표) vs `estimated_effective`(내 계산) 분리 → 프론트에서 공식/추정 배지.
- `countdown` = 상태에 따른 D-day(거래일). 임박→to_designation, 지정회복→to_release,
  주가미달지정→to_delisting. **연속 지속 가정 하 최단**(리셋 시 늘어남).

### series (드릴다운 시계열; 임박·지정 상위만)
```json
{ "067770":{"name":"세진티에스","market":"KOSDAQ",
   "dates":["20260401",...],"close":[...],"mktcap":[...]} }
```

## 사용 예

```python
from krx_data_api import daily_snapshots as ds, screener as scr, dashboard
from krx_data_api import fetch

cache = ds.update_cache("20260401", "20260721", "data/snapshots.csv")   # 증분 수집
uni = scr.target_codes(scr.build_target_universe("20260721"))           # KIND 대상목록
sup = fetch("supervised")                                               # 공식(옵션)
dashboard.build_dashboard_artifacts(cache, uni, supervised=sup,
                                    out_json="data/dashboard_data.json")
```

## 민감성

예측(임박)을 포함하되 `meta.disclaimer`를 모든 화면이 노출하고, `official`/`estimated`를
구분 표기한다. 정확한 지정일은 부칙 시기별 임계값 반영 후 KRX 최초지정일과 일치 확인됨
(라이브 14/14). 향후: daily_counts(상태별 추세) 추가.
