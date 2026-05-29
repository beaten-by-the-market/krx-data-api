from __future__ import annotations

from typing import Any, Callable, Optional

import pandas as pd
import requests

from . import endpoints, transport
from .exceptions import KRXAuthRequiredError, KRXFetchError


def _read_csv_eucKR(raw: bytes, **_: Any) -> pd.DataFrame:
    return pd.read_csv(transport.csv_to_buffer(raw), encoding="EUC-KR")


def _normalize_kosdaq_global(df: pd.DataFrame, **_: Any) -> pd.DataFrame:
    if "시장구분" in df.columns:
        df["시장구분"] = df["시장구분"].replace("KOSDAQ GLOBAL", "KOSDAQ")
    return df


def _json_output_to_df(payload: dict, **_: Any) -> pd.DataFrame:
    """`getJsonData.cmd`가 `{"output": [...]}` 형태로 줄 때."""
    rows = payload.get("output") or payload.get("OutBlock_1") or []
    return pd.DataFrame(rows)


def _json_outblock_to_df(payload: dict, **_: Any) -> pd.DataFrame:
    """`{"OutBlock_1": [...]}` 형태가 우선인 응답."""
    rows = payload.get("OutBlock_1") or payload.get("output") or []
    return pd.DataFrame(rows)


_POST_PROCESSORS: dict[str, Callable[..., Any]] = {
    "read_csv_eucKR": _read_csv_eucKR,
    "normalize_kosdaq_global": _normalize_kosdaq_global,
    "json_output_to_df": _json_output_to_df,
    "json_outblock_to_df": _json_outblock_to_df,
}


def register_post_processor(name: str, func: Callable[..., Any]) -> None:
    """외부에서 커스텀 후처리를 추가하고 싶을 때."""
    _POST_PROCESSORS[name] = func


def fetch(
    name: str,
    *,
    method: Optional[str] = None,
    menu_id: Optional[str] = None,
    session: Optional[requests.Session] = None,
    post: Optional[list[str]] = None,
    auth: bool = False,
    **params: Any,
) -> pd.DataFrame:
    """카탈로그에 등록된 KRX 엔드포인트를 호출해 DataFrame으로 반환.

    Parameters
    ----------
    name : 카탈로그 이름 (endpoints.ENDPOINTS의 키)
    method : "csv" 또는 "json"으로 override. None이면 카탈로그의 기본값.
    menu_id : Referer에 들어갈 menuId override. None이면 카탈로그 기본값.
    session : 재사용할 requests.Session. None이면 매 호출마다 새 세션.
    post : 카탈로그의 post를 override하고 싶을 때 (보통 불필요)
    auth : True면 get_krx_auth()의 로그인된 세션을 사용 (보호 엔드포인트용)
    **params : bld에 전달할 추가/오버라이드 파라미터 (defaults에 머지됨)
    """
    spec = endpoints.get(name)
    bld = spec["bld"]
    method = method or spec["method"]
    menu_id = menu_id or spec["menu_id"]

    merged = {**spec.get("defaults", {}), **params}

    missing = [k for k in spec.get("required", []) if k not in merged]
    if missing:
        raise KRXFetchError(
            f"Endpoint {name!r} missing required params: {missing}"
        )

    if auth and session is None:
        from .auth import get_krx_auth

        session = get_krx_auth().session

    user_supplied_session = session is not None

    def _call() -> Any:
        if method == "csv":
            return transport.csv_download(
                bld, merged, session=session, menu_id=menu_id
            )
        if method == "json":
            return transport.json_data(
                bld, merged, session=session, menu_id=menu_id
            )
        raise KRXFetchError(f"Unknown method: {method!r}")

    try:
        initial: Any = _call()
    except KRXAuthRequiredError:
        # KRX가 비로그인 세션에 OTP 발급을 거부했다 (응답='LOGOUT').
        # 호출자가 세션을 직접 주입한 경우는 의도가 있다고 보고 재시도하지 않음.
        if user_supplied_session:
            raise
        from .auth import get_krx_auth

        session = get_krx_auth().session
        initial = _call()

    # 호출자가 method를 override했는데 post는 명시 안 한 경우,
    # 카탈로그의 post가 다른 method를 가정한다면(예: CSV용 read_csv_eucKR)
    # 그대로 적용하면 타입 불일치가 난다. 새 method에 맞는 기본 후처리로 자동 교체.
    if post is None and method != spec["method"]:
        if method == "json":
            processors = ["json_output_to_df"]
        elif method == "csv":
            processors = ["read_csv_eucKR"]
        else:
            processors = []
    else:
        processors = post if post is not None else spec.get("post", [])
    result: Any = initial
    for proc_name in processors:
        if proc_name not in _POST_PROCESSORS:
            raise KRXFetchError(f"Unknown post processor: {proc_name!r}")
        result = _POST_PROCESSORS[proc_name](result)

    if isinstance(result, pd.DataFrame):
        return result
    if isinstance(result, dict):
        return pd.DataFrame(result.get("output") or result.get("OutBlock_1") or [])
    if isinstance(result, (bytes, bytearray)):
        return pd.read_csv(transport.csv_to_buffer(bytes(result)), encoding="EUC-KR")
    raise KRXFetchError(
        f"Post-processing left non-DataFrame result of type {type(result).__name__}"
    )


def list_endpoints() -> list[str]:
    return sorted(endpoints.ENDPOINTS)


def endpoint_info(name: str) -> dict:
    return dict(endpoints.get(name))
