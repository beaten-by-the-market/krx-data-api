"""krx-data-api — KRX 정보데이터시스템(data.krx.co.kr) 호출 클라이언트.

인증
----
2026-09부터 KRX는 비로그인 요청을 화면 구분 없이 'LOGOUT'으로 거절합니다.
KRX_ID / KRX_PW 환경변수(또는 호출하는 쪽 작업 폴더의 .env)만 있으면
fetch()가 알아서 로그인하고 25분짜리 싱글톤 세션을 재사용합니다.
세션을 직접 만들어 넘기지 마세요. 넘긴 세션은 그대로 쓰고 재로그인하지
않습니다. 꼭 넘겨야 하면 get_krx_auth().session을 넘기세요.

빠른 시작
---------
>>> from krx_data_api import fetch
>>> df = fetch("listed_stocks")                                  # 전종목 기본정보
>>> df = fetch("all_stock_price", trdDd="20260526")             # 전종목 시세
>>> df = fetch("individual_price_trend",
...            isuCd="KR7005930003", strtDd="20250101", endDd="20260101")
"""

from .client import fetch, list_endpoints, endpoint_info, register_post_processor
from .auth import get_krx_auth, reset_krx_auth, KRXAuth
from .exceptions import (
    KRXError,
    KRXAuthError,
    KRXAuthRequiredError,
    KRXFetchError,
    UnknownEndpointError,
)

__all__ = [
    "fetch",
    "list_endpoints",
    "endpoint_info",
    "register_post_processor",
    "get_krx_auth",
    "reset_krx_auth",
    "KRXAuth",
    "KRXError",
    "KRXAuthError",
    "KRXAuthRequiredError",
    "KRXFetchError",
    "UnknownEndpointError",
]

__version__ = "0.1.0"
