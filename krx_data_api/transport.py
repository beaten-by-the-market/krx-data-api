from __future__ import annotations

from io import BytesIO
from typing import Optional

import requests

from .exceptions import KRXAuthRequiredError, KRXFetchError

BASE = "http://data.krx.co.kr"
OTP_URL = f"{BASE}/comm/fileDn/GenerateOTP/generate.cmd"
CSV_URL = f"{BASE}/comm/fileDn/download_csv/download.cmd"
JSON_URL = f"{BASE}/comm/bldAttendant/getJsonData.cmd"

DEFAULT_MENU_ID = "MDC0201020201"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)


def _referer(menu_id: str) -> str:
    return f"{BASE}/contents/MDC/MDI/mdiLoader/index.cmd?menuId={menu_id}"


def _headers(menu_id: str) -> dict:
    return {"Referer": _referer(menu_id), "User-Agent": USER_AGENT}


def csv_download(
    bld: str,
    params: dict,
    *,
    session: Optional[requests.Session] = None,
    menu_id: str = DEFAULT_MENU_ID,
) -> bytes:
    """KRX CSV 다운로드 (OTP 2단계). 응답 바이트를 그대로 반환 — 디코딩은 호출부에서."""
    s = session or requests.Session()
    otp_payload = {
        "locale": "ko_KR",
        "share": "1",
        "csvxls_isNo": "false",
        "name": "fileDown",
        **params,
        "url": bld,
    }
    headers = _headers(menu_id)
    otp = s.post(OTP_URL, data=otp_payload, headers=headers).text
    if otp.strip() == "LOGOUT":
        raise KRXAuthRequiredError(
            f"KRX refused to issue OTP for bld={bld} (response='LOGOUT'). "
            "Login session required — set KRX_ID/KRX_PW env vars or pass "
            "session=get_krx_auth().session."
        )
    resp = s.post(CSV_URL, data={"code": otp}, headers=headers)
    if not resp.ok or not resp.content:
        raise KRXFetchError(
            f"CSV download failed: bld={bld} status={resp.status_code} "
            f"bytes={len(resp.content)} otp_preview={otp[:40]!r}"
        )
    return resp.content


def json_data(
    bld: str,
    params: dict,
    *,
    session: Optional[requests.Session] = None,
    menu_id: str = DEFAULT_MENU_ID,
) -> dict:
    """KRX getJsonData.cmd 호출. JSON dict 반환."""
    s = session or requests.Session()
    payload = {"bld": bld, "locale": "ko_KR", **params}
    resp = s.post(JSON_URL, data=payload, headers=_headers(menu_id))
    # 비로그인 세션이면 본문이 'LOGOUT' (HTTP 400). OTP 경로와 동일한 시그널.
    if resp.text.strip() == "LOGOUT":
        raise KRXAuthRequiredError(
            f"KRX refused JSON request for bld={bld} (response='LOGOUT'). "
            "Login session required."
        )
    if not resp.ok:
        raise KRXFetchError(
            f"JSON fetch failed: bld={bld} status={resp.status_code} "
            f"body_preview={resp.text[:80]!r}"
        )
    try:
        return resp.json()
    except ValueError as e:
        raise KRXFetchError(f"JSON parse failed for bld={bld}: {e}") from e


def csv_to_buffer(content: bytes) -> BytesIO:
    return BytesIO(content)
