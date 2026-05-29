"""KRX 정보데이터시스템 화면(bld) → 친절한 이름 카탈로그.

각 엔드포인트는 dict로 정의된다:
    "bld": KRX bld 경로 (dbms/MDC/STAT/...)
    "method": "csv" 또는 "json" — 호출 방식
    "menu_id": Referer에 들어갈 menuId
    "defaults": 호출 시 기본 파라미터 (호출자가 같은 키를 주면 덮어씀)
    "post": 호출 후 적용할 후처리 함수 이름 리스트 (client._POST_PROCESSORS 참조)

같은 bld를 다른 method로 호출하고 싶으면 fetch() 호출 시 method="json" 같은
override를 전달할 수 있다. 새 파라미터·새 후처리도 fetch() 호출 시점에 자유롭게
머지된다.
"""

ENDPOINTS = {
    "listed_stocks": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT01901",
        "method": "csv",
        "menu_id": "MDC0201020201",
        "defaults": {"mktId": "ALL"},
        "post": ["read_csv_eucKR", "normalize_kosdaq_global"],
        "screen": "12005 전종목기본정보",
    },
    "all_stock_price": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
        "method": "csv",
        "menu_id": "MDC0201020201",
        "defaults": {"mktId": "ALL"},
        "post": ["read_csv_eucKR", "normalize_kosdaq_global"],
        "screen": "12001 전종목시세",
    },
    "individual_price_trend": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT01701",
        "method": "csv",
        "menu_id": "MDC0201020201",
        "defaults": {
            "adjStkPrc_check": "Y",
            "adjStkPrc": "2",
            "money": "1",
        },
        "post": ["read_csv_eucKR"],
        "screen": "12003 개별종목시세추이",
        "required": ["isuCd", "strtDd", "endDd"],
    },
    "delisted": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT23801",
        "method": "csv",
        "menu_id": "MDC0201020201",
        "defaults": {"mktId": "ALL", "isuCd": "ALL"},
        "post": ["read_csv_eucKR"],
        "screen": "20037 상장폐지종목 현황",
        "required": ["strtDd", "endDd"],
    },
    "new_listing": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT20001",
        "method": "json",
        "menu_id": "MDC02021301",
        "defaults": {
            "mktId": "ALL",
            "isurCd": "ALL",
            "isurCd2": "ALL",
            "listClssCd": "ALL",
            "secugrpTp": "ALL",
            "cntrIsoCd": "ALL",
        },
        "post": ["json_outblock_to_df"],
        "screen": "20001 신규상장종목 현황",
        "required": ["strtDd", "endDd"],
    },
    "treasury_individual": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT20601",
        "method": "csv",
        "menu_id": "MDC03010201",
        "defaults": {
            "trstkTpCd": "ALL",
            "trstkAcqstdispTpCd": "ALL",
            "mktId": "ALL",
            "money": "1",
        },
        "post": ["read_csv_eucKR"],
        "screen": "20005 자사주취득/처분내역(개별종목)",
        "required": ["isuCd", "strtDd", "endDd"],
    },
    "treasury_market": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT20701",
        "method": "csv",
        "menu_id": "MDC03010201",
        "defaults": {"mktId": "ALL", "money": "1"},
        "post": ["read_csv_eucKR"],
        "screen": "20005 자사주취득/처분내역(전체)",
        "required": ["strtDd", "endDd"],
    },
    "supervised": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT21401",
        "method": "json",
        "menu_id": "MDC0201020201",
        "defaults": {"mktId": "ALL"},
        "post": ["json_output_to_df"],
        "screen": "20012 관리종목현황",
    },
    "unfaithful_disclosure": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT22001",
        "method": "json",
        "menu_id": "MDC0201020201",
        "defaults": {"mktId": "ALL", "money": "1"},
        "post": ["json_output_to_df"],
        "screen": "20018 불성실공시법인 현황",
    },
    "listing_special": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT24401",
        "method": "csv",
        "menu_id": "MDC0202",
        "defaults": {"money": "1", "otherUnit": "1"},
        "post": ["read_csv_eucKR"],
        "screen": "상장특례 현황",
    },
    "listed_bonds": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT10801",
        "method": "csv",
        "menu_id": "MDC03010201",
        "defaults": {"money": "2"},
        "post": ["read_csv_eucKR"],
        "screen": "14011 상장채권 상세검색",
    },
    "equity_index": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT00301",
        "method": "csv",
        "menu_id": "MDC0201020201",
        "defaults": {"share": "2", "money": "3"},
        "post": ["read_csv_eucKR"],
        "screen": "지수 시세추이",
        "required": ["indIdx", "indIdx2", "strtDd", "endDd"],
    },
}


def get(name: str) -> dict:
    from .exceptions import UnknownEndpointError

    if name not in ENDPOINTS:
        raise UnknownEndpointError(
            f"Unknown endpoint: {name!r}. Available: {sorted(ENDPOINTS)}"
        )
    return ENDPOINTS[name]
