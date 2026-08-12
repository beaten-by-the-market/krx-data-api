"""관리종목 조기경보 대시보드용 정적 artifacts 생성.

스크리너 결과를 프론트엔드가 소비할 JSON 계약으로 변환한다. 배치(자격증명 있는
환경)에서 이 함수를 돌려 artifacts를 만들고, 정적 대시보드(GitHub Pages 등)가 읽는다.

- `stock_status_rows`: 캐시+유니버스 → 종목×사유별 상태·streak·D-day 카운트다운(순수).
- `build_dashboard_artifacts`: 위 결과 + 요약/대조/시계열/메타를 묶어 반환·저장.

규칙은 부칙 반영: 시가총액 미달 기준은 시기별(screener.MKTCAP_SCHEDULE), 주가 미달은
시행일(2026.7.1) 이후부터 산정(screener.PRICE_COUNT_START). 상태기계는 supervision.
공식(KRX supervised) 대조는 호출자가 supervised DataFrame을 넘길 때만 수행(네트워크 분리).

artifacts 스키마는 docs/dashboard_design.md 참고.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from . import daily_snapshots as ds
from . import screener as scr
from . import supervision as sv

# 상태 라벨(퍼널)
S_APPROACHING = "approaching"
S_DESIGNATED = "designated"
S_RELEASE_PENDING = "release_pending"
S_DELISTING_RISK = "delisting_risk"
S_DELISTING_CONFIRMED = "delisting_confirmed"
S_BELOW = "below"          # 현재 미달이나 아직 임박(streak<approach) 전
S_NORMAL = "normal"

DEFAULT_APPROACH = 20        # 미달 연속 이 값 이상이면 '임박'
DEFAULT_REL_PENDING = 30     # 지정 후 이상 연속 이 값 이상이면 '해제임박'


def _vlist(series) -> list:
    return [None if pd.isna(v) else int(v) for v in series]


def _trailing_streak(pairs, thr_fn, want_below: bool) -> int:
    """(date,value) 끝에서부터 연속(미달 want_below=True/이상 False) 일수. None 스킵."""
    run = 0
    for d, v in reversed(pairs):
        if v is None:
            continue
        if (v < thr_fn(d)) == want_below:
            run += 1
        else:
            break
    return run


def _last_below_run_start(pairs, thr_fn):
    """가장 최근의 '미달' 연속 run 시작일(카운트 시작일). 없으면 None. None(스킵)은 무시."""
    run_start = None
    last_start = None
    in_run = False
    for d, v in pairs:
        if v is None:
            continue
        if v < thr_fn(d):
            if not in_run:
                run_start = d
                in_run = True
            last_start = run_start
        else:
            in_run = False
    return last_start


def stock_status_rows(
    cache_df: pd.DataFrame,
    universe: set,
    *,
    approach_threshold: int = DEFAULT_APPROACH,
    release_pending_threshold: int = DEFAULT_REL_PENDING,
    official_cap: Optional[set] = None,
    official_price: Optional[set] = None,
    official_dates: Optional[dict] = None,
) -> dict:
    """종목×사유별 현재 상태·streak·D-day를 계산한다(비정상 종목만 반환).

    official_* 를 주면 각 행에 공식(KRX) 지정 여부·최초지정일을 채운다.

    Returns dict: {rows, counts, my_cap(set), my_price(set)}
    """
    official_cap = official_cap or set()
    official_price = official_price or set()
    official_dates = official_dates or {}

    close_w = ds.to_wide(cache_df, "종가")
    cap_w = ds.to_wide(cache_df, "시가총액").reindex(index=close_w.index)
    dates = close_w.index.tolist()
    meta = scr._meta_by_code(cache_df)
    vol_w = (ds.to_wide(cache_df, "거래량").reindex(index=close_w.index)
             if "거래량" in cache_df.columns else None)

    rows = []
    counts = {"mktcap_designated": 0, "price_designated": 0, "approaching": 0,
              "release_pending": 0, "delisting_risk": 0, "imminent_D5": 0, "below": 0}
    my_cap, my_price = set(), set()

    for code in close_w.columns:
        if code not in meta.index:
            continue
        m = meta.loc[code]
        srt = str(m["단축코드"])
        market = m["시장"]
        if srt not in universe:
            continue
        closes = _vlist(close_w[code].values)
        caps = _vlist(cap_w[code].values)
        # 거래량 0(매매거래정지 등)인 날은 매매거래일 아님 → 스킵(None).
        if vol_w is not None and code in vol_w.columns:
            for i, vv in enumerate(vol_w[code].values):
                if not pd.isna(vv) and int(vv) == 0:
                    closes[i] = None
                    caps[i] = None
        last_close = next((v for v in reversed(closes) if v is not None), None)
        last_cap = next((v for v in reversed(caps) if v is not None), None)

        for reason in ("mktcap", "price"):
            if reason == "mktcap":
                sched = scr.MKTCAP_SCHEDULE.get(market)
                if not sched:
                    continue
                thr_fn = (lambda s: (lambda d: scr._schedule_lookup(s, d)))(sched)
                pairs = list(zip(dates, caps))
                cur_thr = scr.mktcap_threshold_won(market, dates[-1])
                cur_val = last_cap
                off_set = official_cap
            else:
                if market not in scr.PRICE_MARKETS:
                    continue
                thr_fn = lambda d: sv.PRICE_THRESHOLD
                pairs = [(d, c) for d, c in zip(dates, closes)
                         if d >= scr.PRICE_COUNT_START]
                if not pairs:
                    continue
                cur_thr = sv.PRICE_THRESHOLD
                cur_val = last_close
                off_set = official_price

            events = sv.run_state_machine(pairs, thr_fn)
            designated = bool(events) and events[-1].kind == sv.DESIGNATE
            gap = round((cur_val - cur_thr) / cur_thr * 100, 1) if (cur_val is not None and cur_thr) else None
            cd = {"basis": "trading_days", "to_designation": None,
                  "to_release": None, "to_delisting": None, "to_early_delisting": None}
            delisting = None

            if designated:
                suf = _trailing_streak(pairs, thr_fn, want_below=False)
                streak, kind = suf, "sufficient"
                state = S_RELEASE_PENDING if suf >= release_pending_threshold else S_DESIGNATED
                if suf > 0:
                    cd["to_release"] = sv.RELEASE_DAYS - suf
                # 상폐 회복창(주가=제54조13호가 / 시총=제54조12호) 평가
                eff = (events[-1].effective_date or dates[-1]) if events else dates[-1]
                if reason == "price":
                    rr = sv.evaluate_price_recovery_failure(dates, closes, eff)
                    window = sv.PRICE_DELIST_WINDOW_DAYS
                    delisting = {"recovery_status": rr.status, "observed": rr.observed_days,
                                 "reason": "주가"}
                else:  # mktcap: 유가=제48조9호(45연속) / 코스닥=제54조12호(10연속 or 누적30)
                    rec = scr.MKTCAP_DELIST_RECOVERY.get(market, {"consec_days": 10, "cumul_days": 30})
                    rr = sv.evaluate_mktcap_recovery_failure(
                        dates, caps, eff, thr_fn,
                        consec_days=rec["consec_days"], cumul_days=rec["cumul_days"])
                    window = sv.MKTCAP_DELIST_WINDOW_DAYS
                    delisting = {"recovery_status": rr.status, "observed": rr.observed_days,
                                 "recovered_by": rr.recovered_by, "reason": "시총"}
                cd["to_delisting"] = max(window - rr.observed_days, 0)
                if rr.status in ("상폐확정", "조기상폐확정"):
                    state = S_DELISTING_CONFIRMED
                    counts["delisting_risk"] += 1
                elif state != S_RELEASE_PENDING and cd["to_delisting"] <= 15:
                    # 회복창 15거래일 이하 남았는데 미회복 → 상폐 임박
                    state = S_DELISTING_RISK
                    counts["delisting_risk"] += 1
                (my_cap if reason == "mktcap" else my_price).add(srt)
                counts["mktcap_designated" if reason == "mktcap" else "price_designated"] += 1
            else:
                deff = _trailing_streak(pairs, thr_fn, want_below=True)
                streak, kind = deff, "deficient"
                if deff >= approach_threshold:
                    state = S_APPROACHING
                    cd["to_designation"] = sv.DESIGNATE_DAYS - deff
                    counts["approaching"] += 1
                    if cd["to_designation"] <= 5:
                        counts["imminent_D5"] += 1
                elif deff >= 1:
                    # 현재 미달이나 아직 임박 전(streak < approach_threshold)
                    state = S_BELOW
                    cd["to_designation"] = sv.DESIGNATE_DAYS - deff
                    counts["below"] += 1
                else:
                    state = S_NORMAL

            if state == S_NORMAL:
                continue
            if state == S_RELEASE_PENDING:
                counts["release_pending"] += 1

            rows.append({
                "code": srt, "name": m["종목명"], "market": market, "reason": reason,
                "state": state, "streak": streak, "streak_kind": kind,
                "target": sv.DESIGNATE_DAYS if not designated else sv.RELEASE_DAYS,
                "value": cur_val, "threshold": int(cur_thr) if cur_thr else None, "gap_pct": gap,
                "official": srt in off_set,
                "official_design_date": official_dates.get(srt) if srt in off_set else None,
                "estimated_effective": events[-1].effective_date if (designated and events) else None,
                "count_start_date": _last_below_run_start(pairs, thr_fn),
                "countdown": cd, "delisting": delisting,
            })

    return {"rows": rows, "counts": counts, "my_cap": my_cap, "my_price": my_price}


def _official_from_supervised(supervised: pd.DataFrame, universe: Optional[set] = None):
    # LIST_BZ_RSN_NM은 다중사유를 콤마로 결합("시가총액 미달,주가 미달(동전주)")하므로 부분매칭.
    # "시가총액 미달"은 "종류주식 시가총액 미달"(우선주)도 잡으니 유니버스로 스코핑해 제외한다.
    def _codes(needle):
        m = supervised["LIST_BZ_RSN_NM"].astype(str).str.contains(needle, regex=False, na=False)
        codes = set(supervised[m]["ISU_CD"].astype(str).str.zfill(6))
        return (codes & universe) if universe is not None else codes
    dates = {str(r["ISU_CD"]).zfill(6): str(r["FST_DESIGN_DD"]).replace("/", "")
             for _, r in supervised.iterrows()}
    return _codes("시가총액 미달"), _codes("주가 미달"), dates


def build_dashboard_artifacts(
    cache_df: pd.DataFrame,
    universe: set,
    *,
    supervised: Optional[pd.DataFrame] = None,
    admin_issue: Optional[pd.DataFrame] = None,
    actions_by_code: Optional[dict] = None,
    generated_at: Optional[str] = None,
    series_codes: Optional[list] = None,
    series_top: int = 8,
    out_json: Optional[str] = None,
    **row_kwargs,
) -> dict:
    """대시보드 artifacts(meta·counts·reconcile·rows·series)를 만든다.

    supervised : KRX 관리종목현황 DataFrame(fetch("supervised")). 주면 공식 대조.
        None이면 official_available=False로 추정만.
    admin_issue : KIND 관리종목 지정목록 DataFrame(종목명·지정일·지정사유,
        krx_kind_data_api.fetch("admin_issue")). 주면 지정 종목 행에 KIND 지정일
        (`kind_design_date`)을 종목명 매칭으로 붙인다.
    series_codes : 드릴다운 시계열을 넣을 단축코드 목록. 없으면 임박·지정 상위 series_top.
    out_json : 주면 전체 artifacts를 하나의 JSON으로 저장(대시보드 embed용).
    """
    official_available = supervised is not None
    off_cap, off_price, off_dates = (
        _official_from_supervised(supervised, universe=universe) if official_available else (set(), set(), {})
    )
    res = stock_status_rows(
        cache_df, universe,
        official_cap=off_cap, official_price=off_price, official_dates=off_dates,
        **row_kwargs,
    )
    rows, counts, my_cap, my_price = res["rows"], res["counts"], res["my_cap"], res["my_price"]

    # KIND 관리종목 지정일(종목명 매칭). admin_issue는 코드가 없어 종목명으로 조인한다.
    kind_map = {}
    if admin_issue is not None and "종목명" in admin_issue.columns and "지정일" in admin_issue.columns:
        for _, a in admin_issue.iterrows():
            nm = str(a["종목명"]).strip()
            kd = str(a["지정일"]).replace("/", "").replace("-", "").strip()[:8]
            if nm and len(kd) == 8:
                kind_map[nm] = kd
    designated_states = {S_DESIGNATED, S_RELEASE_PENDING, S_DELISTING_RISK, S_DELISTING_CONFIRMED}
    for r in rows:
        r["kind_design_date"] = (
            kind_map.get(str(r["name"]).strip()) if r["state"] in designated_states else None
        )

    def _recon(mine, off):
        return {
            "official": len(off) if official_available else None,
            "matched": len(mine & off) if official_available else None,
            "estimate_only": len(mine - off),
            "missed": len(off - mine) if official_available else None,
        }
    reconcile = {"mktcap": _recon(my_cap, off_cap), "price": _recon(my_price, off_price)}

    close_w = ds.to_wide(cache_df, "종가")
    cap_w = ds.to_wide(cache_df, "시가총액").reindex(index=close_w.index)
    dates = close_w.index.tolist()
    meta_idx = scr._meta_by_code(cache_df)
    srt_to_std = {str(meta_idx.loc[c]["단축코드"]): c for c in close_w.columns if c in meta_idx.index}

    if series_codes is None:
        # 기본: 비정상(rows에 포함된) 전 종목의 시계열을 넣는다. rows가 비정상만이라
        # 개수가 제한적이므로 용량 부담이 작고, 드릴다운에서 '샘플 미포함' 안내가 안 뜬다.
        series_codes = [r["code"] for r in rows]
    series = {}
    for srt in series_codes:
        std = srt_to_std.get(srt)
        if std is None:
            continue
        r = next((x for x in rows if x["code"] == srt), None)
        series[srt] = {"name": r["name"] if r else srt,
                       "market": r["market"] if r else "",
                       "dates": dates,
                       "close": _vlist(close_w[std].values),
                       "mktcap": _vlist(cap_w[std].values)}
        if actions_by_code and srt in actions_by_code:
            series[srt]["actions"] = actions_by_code[srt]

    meta = {
        "as_of": dates[-1] if dates else None,
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "rule": {"mktcap_schedule": scr.MKTCAP_SCHEDULE, "price_threshold": sv.PRICE_THRESHOLD,
                 "designate_days": sv.DESIGNATE_DAYS, "release_days": sv.RELEASE_DAYS,
                 "price_count_start": scr.PRICE_COUNT_START,
                 "delist_window_days": sv.PRICE_DELIST_WINDOW_DAYS},
        "universe_count": len(universe),
        "cache": {"first": dates[0] if dates else None, "last": dates[-1] if dates else None,
                  "trading_days": len(dates)},
        "official_available": official_available,
        "disclaimer": ("공개 규정·공개 시장데이터 기반 비공식 추정치입니다. KRX 공식 판정이 "
                       "아닙니다. 시가총액 기준은 부칙 경과규정에 따라 시기별로 다르며, 주가 "
                       "미달은 2026.7.1 이후부터 산정합니다. 투자판단의 근거로 사용하지 마십시오."),
        "countdown_note": "연속 지속 가정 하의 최단 잔여 거래일. 기준을 회복/이탈하면 리셋됩니다.",
    }

    artifacts = {"meta": meta, "counts": counts, "reconcile": reconcile,
                 "rows": rows, "series": series}
    if out_json is not None:
        import json
        import os as _os
        _os.makedirs(_os.path.dirname(_os.path.abspath(out_json)), exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(artifacts, f, ensure_ascii=False)
    return artifacts
