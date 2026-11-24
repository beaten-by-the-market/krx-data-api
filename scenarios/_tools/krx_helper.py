# ── KRX 헬퍼 (모든 시나리오 노트북 공통) ─────────────────────────────────────
# 2026-09부터 KRX는 비로그인 요청을 거절합니다. KRX 정보데이터시스템 계정이 필요합니다.
# Colab: 왼쪽 🔑(Secrets)에 KRX_ID, KRX_PW 를 넣고 "노트북 액세스"를 켜세요.
#        Secrets에 없으면 입력창으로 묻습니다. 아이디·비밀번호는 출력하지 않습니다.
# 로컬: krx_data_api 가 작업 폴더의 .env(또는 패키지를 클론한 레포의 .env)에서 KRX_ID/KRX_PW 를 읽습니다.
import os, sys
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

IN_COLAB = "google.colab" in sys.modules

if IN_COLAB:
    from getpass import getpass
    for _k in ("KRX_ID", "KRX_PW"):
        if os.environ.get(_k):
            continue
        try:
            from google.colab import userdata
            _v = userdata.get(_k)
        except Exception:
            _v = None
        os.environ[_k] = _v or getpass(f"{_k}: ")

from krx_data_api import fetch  # noqa: E402  (import 시 .env 로드)
from krx_data_api.daily_snapshots import trading_days  # noqa: E402

if not (os.environ.get("KRX_ID") and os.environ.get("KRX_PW")):
    raise RuntimeError("KRX_ID / KRX_PW 가 없습니다. Colab Secrets 또는 .env 에 넣어 주세요.")

pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 40)


def num(s):
    """KRX JSON의 '1,234' 같은 콤마 문자열 → 숫자. '-'·빈 값은 NaN."""
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(",", "", regex=False).str.strip(),
                         errors="coerce")


def ymd(d):
    """날짜 → 'YYYYMMDD' (KRX 파라미터 형식)."""
    return pd.Timestamp(d).strftime("%Y%m%d")


def last_trading_day(asof=None):
    """asof(기본 오늘) 또는 그 이전의 마지막 매매거래일 → Timestamp.
    KRX는 휴장일 trdDd에 직전 거래일 데이터를 그대로 주므로 날짜를 이걸로 맞춰 씁니다."""
    end = pd.Timestamp(asof or date.today())
    days = trading_days(ymd(end - timedelta(days=14)), ymd(end))
    return pd.Timestamp(days[-1])


def eok(won, digits=0):
    """원 → 억원 숫자."""
    return (pd.Series(won) / 1e8).round(digits)


# 한글 차트 폰트
import matplotlib.pyplot as plt  # noqa: E402
try:
    import koreanize_matplotlib  # noqa: F401  (Colab: 위 셀에서 설치)
except ImportError:
    if sys.platform.startswith("win"):
        plt.rcParams["font.family"] = "Malgun Gothic"
    elif sys.platform == "darwin":
        plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False

print("KRX 준비 완료", "(Colab)" if IN_COLAB else "(로컬)", "· 로그인 계정 설정됨")
