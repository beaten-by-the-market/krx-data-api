"""krx-data-api — KRX 정보데이터시스템(data.krx.co.kr) 호출 클라이언트.

빠른 시작
---------
>>> from krx_data_api import fetch
>>> df = fetch("listed_stocks")                                  # 전종목 기본정보
>>> df = fetch("all_stock_price", trdDd="20260526")             # 전종목 시세
>>> df = fetch("individual_price_trend",
...            isuCd="KR7005930003", strtDd="20250101", endDd="20260101")

로그인 필요한 엔드포인트
-----------------------
>>> df = fetch("short_selling_individual", trdDd="20260526", auth=True)  # 예시

KRX_ID / KRX_PW 환경변수(또는 .env)에서 자격증명을 읽어 25분 싱글톤 세션을 유지.
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
