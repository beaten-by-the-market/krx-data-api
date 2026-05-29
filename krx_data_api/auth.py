"""KRX 데이터마켓 자체계정 로그인 세션.

근거: docs/KRX_로그인_세션_매뉴얼.md (2026-05-27 라이브 검증)

핵심 규칙:
- _error_code == "CD001"만 성공. CD007도 MBR_NO가 발급되지만 위장 성공이므로 거부.
- 싱글톤. 세션 25분 재사용, 만료 시 자동 재로그인.
- credentials는 KRX_ID / KRX_PW 환경변수 (또는 .env)에서 읽음.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Optional

import requests

try:
    from dotenv import load_dotenv

    # cwd의 .env 우선 로드
    load_dotenv()
    # 추가로 패키지가 설치된 디렉터리(krx-data-api/)의 .env도 시도.
    # 사용자가 어느 cwd에서 호출하든 패키지 자체 자격증명이 발견되도록.
    _pkg_env = Path(__file__).resolve().parent.parent / ".env"
    if _pkg_env.exists():
        load_dotenv(_pkg_env, override=False)
except Exception:
    pass

from .exceptions import KRXAuthError
from .transport import USER_AGENT

LOGIN_PAGE = (
    "https://data.krx.co.kr/contents/MDC/COMS/client/view/login.jsp?site=mdc"
)
LOGIN_API = "https://data.krx.co.kr/contents/MDC/COMS/client/MDCCOMS001D1.cmd"

SESSION_TTL_SECONDS = 25 * 60  # KRX 세션은 약 30분, 안전 마진으로 25분


class KRXAuth:
    def __init__(self, mbr_id: str, pw: str) -> None:
        self._mbr_id = mbr_id
        self._pw = pw
        self._session: Optional[requests.Session] = None
        self._login_at: float = 0.0
        self._lock = threading.Lock()
        self._mbr_no: Optional[str] = None

    @property
    def session(self) -> requests.Session:
        with self._lock:
            if self._session is None or self._expired():
                self._login()
            return self._session  # type: ignore[return-value]

    @property
    def mbr_no(self) -> Optional[str]:
        return self._mbr_no

    def _expired(self) -> bool:
        return (time.monotonic() - self._login_at) > SESSION_TTL_SECONDS

    def _login(self) -> None:
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT})

        s.get(LOGIN_PAGE)

        resp = s.post(
            LOGIN_API,
            data={"mbrId": self._mbr_id, "pw": self._pw, "skipDup": "Y"},
            headers={
                "Referer": LOGIN_PAGE,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        try:
            body = resp.json()
        except ValueError as e:
            raise KRXAuthError(
                f"Login response not JSON (HTTP {resp.status_code})"
            ) from e

        code = body.get("_error_code")
        if code != "CD001":
            # CD001 외에는 모두 위장 성공 (MBR_NO가 돌아와도 세션은 인증되지 않음).
            # 라이브로 확인된 사례:
            #   CD007: skipDup 처리 -MBR_NO 발급되나 인증 안 됨
            #   CD010: 비밀번호 변경 필요 -KRX 사이트에서 비번 변경 후 재시도
            msg = body.get("_error_message") or body.get("_error_msg")
            hint = ""
            if code == "CD010":
                hint = (
                    " -KRX 사이트에 직접 로그인해서 비밀번호를 변경한 뒤 "
                    "새 비밀번호로 재시도하세요."
                )
            elif code == "CD007":
                hint = (
                    " -KRX가 중복 로그인 등으로 skipDup 처리를 요구합니다. "
                    "잠시 후 재시도하거나 다른 세션을 종료하세요."
                )
            raise KRXAuthError(
                f"Login failed: _error_code={code!r} message={msg!r}{hint}"
            )

        self._session = s
        self._login_at = time.monotonic()
        self._mbr_no = body.get("MBR_NO")


_singleton_lock = threading.Lock()
_singleton: Optional[KRXAuth] = None


def get_krx_auth(
    mbr_id: Optional[str] = None, pw: Optional[str] = None
) -> KRXAuth:
    """싱글톤 KRXAuth 반환. credentials를 직접 넘기지 않으면 환경변수 사용.

    환경변수: KRX_ID, KRX_PW
    """
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            mbr_id = mbr_id or os.getenv("KRX_ID")
            pw = pw or os.getenv("KRX_PW")
            if not mbr_id or not pw:
                raise KRXAuthError(
                    "KRX credentials not set. Provide mbr_id/pw or set "
                    "KRX_ID / KRX_PW env vars (or .env)."
                )
            _singleton = KRXAuth(mbr_id, pw)
        return _singleton


def reset_krx_auth() -> None:
    """테스트나 credential 교체 시 싱글톤 초기화."""
    global _singleton
    with _singleton_lock:
        _singleton = None
