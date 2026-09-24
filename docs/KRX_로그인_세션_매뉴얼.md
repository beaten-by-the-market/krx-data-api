# KRX 데이터 수집 — 로그인 세션 획득 매뉴얼

- **작성**: 2026-05-27 (다른 프로젝트의 `backend/app/krx_auth.py` 기준)
- **갱신**: 2026-09-24 — 이 레포의 `krx_data_api/auth.py` 기준으로 사용법 정정, 비로그인 차단·https 필수 반영
- **상태**: 라이브 검증 완료

> **2026-09 변경**: KRX가 비로그인 요청을 화면 구분 없이 `400 LOGOUT`으로 거절합니다(09-03까지는 `new_listing` 등이 비로그인으로 조회됐음). 이제 모든 호출에 로그인이 필요하며, `fetch()`는 자격증명이 있으면 처음부터 로그인 세션으로 요청합니다.

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

> **주의 (https 필수)**: 로그인으로 받은 `JSESSIONID`는 `Secure` 쿠키(`domain=.krx.co.kr`)입니다. 데이터 요청을 `http://`로 보내면 쿠키가 실리지 않아, 로그인에 성공했어도 `LOGOUT`이 옵니다. 모든 요청은 `https://data.krx.co.kr`로 보내야 합니다.

---

## 5. 사용법 (이 레포)

`KRX_ID` / `KRX_PW`만 설정하면 `fetch()`가 로그인을 알아서 처리합니다. 세션을 만들 필요가 없습니다.

```python
from krx_data_api import fetch

df = fetch("all_stock_price", trdDd="20260526")                 # 전체 종목 시세
df = fetch("short_selling_individual", trdDd="20260526")        # 공매도 전종목
```

세션을 명시해야 할 때는 로그인된 싱글톤 세션을 넘깁니다. 로그인하지 않은 `requests.Session()`을 넘기면 재로그인 없이 그대로 `LOGOUT`이 납니다.

```python
from krx_data_api import fetch, get_krx_auth

s = get_krx_auth().session
df = fetch("listed_stocks", session=s)
```

싱글톤이라 한 번 로그인하면 **25분간 세션 재사용**, 만료 시 자동 재로그인합니다. KRX가 그보다 먼저 세션을 끊으면 `fetch()`가 `LOGOUT`을 받고 한 번 새로 로그인해 재시도합니다.
