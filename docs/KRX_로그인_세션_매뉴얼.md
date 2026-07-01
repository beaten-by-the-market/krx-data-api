# KRX 데이터 수집 — 로그인 세션 획득 매뉴얼

- **작성**: 2026-05-27
- **대상 모듈**: `backend/app/krx_auth.py`
- **상태**: 라이브 검증 완료

---

## 1. 한 줄 요약

브라우저(Selenium/Playwright) 없이, 순수 `requests.Session`으로 KRX 데이터마켓(`data.krx.co.kr`)에 ID/PW를 직접 POST → `JSESSIONID` 쿠키를 받아 `getJsonData.cmd`의 모든 시장 데이터에 접근합니다.

---

## 2. 왜 Selenium이 필요 없나

- KRX 자체 계정 로그인 API(`MDCCOMS001D1.cmd`)는 **CAPTCHA·JS challenge 없이** 평범한 form POST에 JSON으로 응답합니다.
- 네이버/카카오 OAuth는 "우회"가 아닌 **정식 로그인 경로**이지만, 자체 계정이 더 단순해 채택하지 않았습니다.
- **참고**: `pykrx`의 OHLCV는 `fchart.stock.naver.com`(네이버 차트 API)에서 받으므로 KRX 로그인과 무관합니다. **투자자별 매매동향·공매도** 등 풀 데이터는 KRX 로그인 세션이 필요합니다.

---

## 3. 로그인 3단계 흐름

```
1) GET  login.jsp?site=mdc            → JSESSIONID 쿠키 발급받음
2) POST MDCCOMS001D1.cmd              → {mbrId, pw, skipDup:"Y"} 전송
        헤더: X-Requested-With: XMLHttpRequest, Referer: 로그인페이지
3) 응답 JSON _error_code == "CD001"   → 성공 (MBR_NO 발급)
   이후 같은 세션으로 getJsonData.cmd 호출 → 모든 MDCSTAT 데이터 접근
```

---

## 4. 핵심 코드 (요지)

```python
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 ... Chrome/145 ..."})

# Step 1: 로그인 페이지 → JSESSIONID
s.get("https://data.krx.co.kr/contents/MDC/COMS/client/view/login.jsp?site=mdc")

# Step 2: ID/PW POST
resp = s.post(
    "https://data.krx.co.kr/contents/MDC/COMS/client/MDCCOMS001D1.cmd",
    data={"mbrId": KRX_ID, "pw": KRX_PW, "skipDup": "Y"},
    headers={"Referer": LOGIN_PAGE, "X-Requested-With": "XMLHttpRequest"})

# Step 3: 성공 판정 — CD001만 인정 (CD007도 MBR_NO 발급되어 위장 성공 발생)
if resp.json().get("_error_code") == "CD001":
    # 인증 완료 — 이후 getJsonData.cmd 재사용
    s.post("https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd",
           data={"bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
                 "mktId": "STK", "trdDd": "20260526", "locale": "ko_KR"})
```

> **주의**: 응답의 `_error_code`가 `CD007`인 경우에도 `MBR_NO`가 발급되어 위장 성공처럼 보일 수 있습니다. **반드시 `CD001`만 성공으로 판정**해야 합니다.

---

## 5. 사용법

```python
from app.krx_auth import get_krx_auth

auth = get_krx_auth()
df = auth.fetch("all_stock_price", trdDd="20260526")   # 전체 종목 시세
df = auth.fetch("index_price")                          # 지수 시세
df = auth.fetch("short_selling_individual", trdDd="20260526")  # 공매도 전종목
```

싱글톤이라 한 번 로그인하면 **25분간 세션 재사용**, 만료 시 자동 재로그인합니다.
