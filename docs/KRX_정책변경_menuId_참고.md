# KRX 호출 참고 - 정책 변경 배경 & menuId

`krx-data-api` 패키지 사용법은 [README.md](../README.md)를 참고하세요.
이 문서에는 README에 없는 배경 정보만 남깁니다 (엔드포인트·bld 목록은 README 카탈로그로 일원화).

---

## 2026-05 정책 변경 (왜 로그인이 필요한가)

- 비로그인 세션에서 OTP를 요청하면 응답이 `'LOGOUT'` 6글자 문자열 (HTTP 200, content-type=octet-stream).
- 비로그인 세션에서 JSON API를 호출하면 본문이 `'LOGOUT'` (HTTP 400, content-type=text/html).
- 이전에는 공개 화면(전종목 기본정보 등)도 비로그인으로 가능했음. 변경 후로는 모든 호출이 KRX 자체계정 로그인 필수.
- 새 패키지 `krx-data-api`는 이 시그널(`LOGOUT`)을 자동 감지해 로그인 후 재시도하는 구조.
  자세한 인증 매뉴얼은 [KRX_로그인_세션_매뉴얼.md](KRX_로그인_세션_매뉴얼.md).

---

## menuId (Referer)

`fetch(..., menu_id=...)` 또는 카탈로그의 `menu_id`로 지정. KRX는 Referer의 menuId를
비교적 관대하게 처리하지만, 화면 계열에 맞추면 안전합니다.

| menuId | 용도 |
|--------|------|
| `MDC0201020201` | 주식·기본정보 화면 (기본값) |
| `MDC0201020302` | 투자자별 거래실적 |
| `MDC03010201` | 자사주·채권 화면 |
| `MDC0202` | 상장폐지·상장특례 등 |
| `MDC0203` | 공매도 통계 |
| `MDC02021301` | 신규/이전상장 |
| `MDC0201020101` | 기업정보 |

---

## OTP/헤더 흐름 (디버깅 참고)

직접 호출이 필요할 때의 저수준 흐름은 `krx_data_api/transport.py`에 구현돼 있습니다.

- CSV: `GenerateOTP/generate.cmd` (OTP 발급) → `download_csv/download.cmd` (OTP로 다운로드) → EUC-KR 디코딩
- JSON: `bldAttendant/getJsonData.cmd` 직접 호출
- 공통 헤더: `Referer`(menuId 포함), `User-Agent`

> 과거 30여 개 .py에서 반복되던 직접 호출 코드(수동 OTP 2단계, JSON 평탄화 루프 등)는
> 이제 `transport.csv_download` / `transport.json_data` / `fetch()`로 대체됐습니다.
> 옛 코드 스니펫이 필요하면 git 히스토리를 참고하세요.
