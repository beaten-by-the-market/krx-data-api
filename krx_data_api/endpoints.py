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
        "method": "json",
        "menu_id": "MDC0201",
        "defaults": {"mktId": "ALL", "share": "1", "csvxls_isNo": "false"},
        "post": ["json_outblock_to_df"],
        "screen": "12005 전종목기본정보",
    },
    "listed_stocks_csv": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT01901",
        "method": "csv",
        "menu_id": "MDC0201020201",
        "defaults": {"mktId": "ALL"},
        "post": ["read_csv_eucKR", "normalize_kosdaq_global"],
        "screen": "12005 전종목기본정보 (CSV)",
    },
    "all_stock_price": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
        "method": "json",
        "menu_id": "MDC0201020201",
        "defaults": {"mktId": "ALL"},
        "post": ["json_outblock_to_df"],
        "screen": "12001 전종목시세",
    },
    "all_stock_price_csv": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
        "method": "csv",
        "menu_id": "MDC0201020201",
        "defaults": {"mktId": "ALL"},
        "post": ["read_csv_eucKR", "normalize_kosdaq_global"],
        "screen": "12001 전종목시세 (CSV)",
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
    "investor_trading_individual": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT02301",
        "method": "csv",
        "menu_id": "MDC0201020302",
        "defaults": {
            "inqTpCd": "1",
            "trdVolVal": "2",
            "askBid": "3",
            "tboxisuCd_finder_stkisu0_0": "",
            "codeNmisuCd_finder_stkisu0_0": "",
            "param1isuCd_finder_stkisu0_0": "ALL",
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
        },
        "post": ["read_csv_eucKR"],
        "screen": "12009 투자자별 거래실적(개별종목)",
        "required": ["isuCd", "isuCd2", "strtDd", "endDd"],
    },
    "investor_trading_individual_json": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT02301",
        "method": "json",
        "menu_id": "MDC0201020302",
        "defaults": {
            "inqTpCd": "1",
            "trdVolVal": "2",
            "askBid": "3",
            "tboxisuCd_finder_stkisu0_0": "",
            "codeNmisuCd_finder_stkisu0_0": "",
            "param1isuCd_finder_stkisu0_0": "ALL",
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
        },
        "post": ["json_output_to_df"],
        "screen": "12009 투자자별 거래실적(개별종목) (JSON)",
        "required": ["isuCd", "isuCd2", "strtDd", "endDd"],
    },
    # MDCSTAT02303: 같은 12009 화면의 "일별추이" 탭.
    # 02301(기간합계, 투자자 유형이 행)과 달리 날짜가 행, 투자자 유형이 열이다.
    # askBid: 1=매수, 2=매도, 3=순매수 / trdVolVal: 1=거래량, 2=거래대금.
    "investor_trading_individual_daily": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT02303",
        "method": "csv",
        "menu_id": "MDC0201020302",
        "defaults": {
            "inqTpCd": "2",       # 일별추이
            "trdVolVal": "2",     # 거래대금 (1=거래량)
            "askBid": "3",        # 순매수 (1=매수, 2=매도)
            "detailView": "1",
            "tboxisuCd_finder_stkisu0_0": "",
            "isuCd2": "",
            "codeNmisuCd_finder_stkisu0_0": "",
            "param1isuCd_finder_stkisu0_0": "ALL",
            "money": "1",
            "csvxls_isNo": "false",
        },
        "post": ["read_csv_eucKR"],
        "screen": "12009 투자자별 거래실적(개별종목) 일별추이",
        "required": ["isuCd", "strtDd", "endDd"],
    },
    "investor_trading_individual_daily_json": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT02303",
        "method": "json",
        "menu_id": "MDC0201020302",
        "defaults": {
            "inqTpCd": "2",
            "trdVolVal": "2",
            "askBid": "3",
            "detailView": "1",
            "tboxisuCd_finder_stkisu0_0": "",
            "isuCd2": "",
            "codeNmisuCd_finder_stkisu0_0": "",
            "param1isuCd_finder_stkisu0_0": "ALL",
            "money": "1",
            "csvxls_isNo": "false",
        },
        "post": ["json_output_to_df"],
        "screen": "12009 투자자별 거래실적(개별종목) 일별추이 (JSON)",
        "required": ["isuCd", "strtDd", "endDd"],
    },
    "delisted": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT23801",
        "method": "csv",
        "menu_id": "MDC0202",
        "defaults": {
            "mktId": "ALL",
            "tboxisuCd_finder_listdelisu0_1": "전체",
            "isuCd": "ALL",
            "isuCd2": "ALL",
            "codeNmisuCd_finder_listdelisu0_1": "",
            "param1isuCd_finder_listdelisu0_1": "",
            "share": "1",
            "csvxls_isNo": "true",
        },
        "post": ["read_csv_eucKR"],
        "screen": "20037 상장폐지종목 현황",
        "required": ["strtDd", "endDd"],
    },
    "delisted_json": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT23801",
        "method": "json",
        "menu_id": "MDC0202",
        "defaults": {
            "mktId": "ALL",
            "tboxisuCd_finder_listdelisu0_1": "전체",
            "isuCd": "ALL",
            "isuCd2": "ALL",
            "codeNmisuCd_finder_listdelisu0_1": "",
            "param1isuCd_finder_listdelisu0_1": "",
            "share": "1",
            "csvxls_isNo": "true",
        },
        "post": ["json_output_to_df"],
        "screen": "20037 상장폐지종목 현황 (JSON)",
        "required": ["strtDd", "endDd"],
    },
    # 주의: MDCSTAT23902(상폐시세)는 원주가만 제공하며 수정주가 옵션이 없습니다.
    # adjStkPrc 계열 파라미터를 보내도 KRX가 무시합니다.
    # 상폐종목 수정주가가 필요하면 individual_price_trend(MDCSTAT01701)를 쓰세요.
    # (상폐종목도 조회되며, adjBasDd는 상장폐지일 기준을 권장. 상폐 후 이벤트가
    #  없으므로 기준일을 오늘로 둬도 결과는 동일합니다.)
    "delisted_stock_price": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT23902",
        "method": "csv",
        "menu_id": "MDC0202",
        "defaults": {
            "isuCd2": "",
            "tboxisuCd_finder_listdelisu0_0": "",
            "codeNmisuCd_finder_listdelisu0_0": "",
            "param1isuCd_finder_listdelisu0_0": "",
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
        },
        "post": ["read_csv_eucKR"],
        "screen": "MDCSTAT23902 delisted stock price data",
        "required": ["isuCd", "strtDd", "endDd"],
    },
    "delisted_stock_price_json": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT23902",
        "method": "json",
        "menu_id": "MDC0202",
        "defaults": {
            "isuCd2": "",
            "tboxisuCd_finder_listdelisu0_0": "",
            "codeNmisuCd_finder_listdelisu0_0": "",
            "param1isuCd_finder_listdelisu0_0": "",
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
        },
        "post": ["json_output_to_df"],
        "screen": "MDCSTAT23902 delisted stock price data (JSON)",
        "required": ["isuCd", "strtDd", "endDd"],
    },
    "new_listing": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT20001",
        "method": "csv",
        "menu_id": "MDC0201",
        "defaults": {
            "mktId": "ALL",
            "tboxisurCd_finder_comnm0_0": "전체",
            "isurCd": "ALL",
            "isurCd2": "ALL",
            "codeNmisurCd_finder_comnm0_0": "",
            "param1isurCd_finder_comnm0_0": "",
            "leadTpComp": "",
            "listClssCd": "ALL",
            "secugrpTp": "ALL",
            "cntrIsoCd": "ALL",
            "share": "1",
            "csvxls_isNo": "true",
        },
        "post": ["read_csv_eucKR"],
        "screen": "20001 신규상장종목 현황",
        "required": ["strtDd", "endDd"],
    },
    "new_listing_json": {
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
        "screen": "20001 신규상장종목 현황 (JSON)",
        "required": ["strtDd", "endDd"],
    },
    "offering_price_change_rate": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT20201",
        "method": "csv",
        "menu_id": "MDC02020103",
        "defaults": {
            "mktId": "ALL",
            "tboxisuCd_finder_stkisu0_0": "전체",
            "isuCd": "ALL",
            "isuCd2": "ALL",
            "codeNmisuCd_finder_stkisu0_0": "",
            "param1isuCd_finder_stkisu0_0": "ALL",
            "KNX": "KNX",
            # KRX 화면의 "수정주가 적용" 체크 값입니다.
            # fetch(..., adjusted_price=False)로 호출하면 client에서 제거합니다.
            "inqCondTpCd": "Y",
            "share": "1",
            "money": "1",
            "csvxls_isNo": "true",
        },
        "post": ["read_csv_eucKR"],
        "screen": "20003 공모가대비 등락률",
        "required": ["strtDd", "endDd"],
    },
    "offering_price_change_rate_json": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT20201",
        "method": "json",
        "menu_id": "MDC02020103",
        "defaults": {
            "mktId": "ALL",
            "tboxisuCd_finder_stkisu0_9": "전체",
            "isuCd": "ALL",
            "isuCd2": "ALL",
            "codeNmisuCd_finder_stkisu0_9": "",
            "param1isuCd_finder_stkisu0_9": "ALL",
            "KNX": "KNX",
            "inqCondTpCd": "Y",
            "share": "1",
            "money": "1",
            "csvxls_isNo": "true",
        },
        "post": ["json_output_to_df"],
        "screen": "20003 공모가대비 등락률 (JSON)",
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
    # listing_special과 bld는 같지만(MDCSTAT24401) 파라미터/호출방식이 달라
    # 별도 화면(코스닥상장기업 주관사별 IPO 현황의 공모가 대비 주가수익률)을 서비스한다.
    "ipo_price_return": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT24401",
        "method": "json",
        "menu_id": "MDC02021301",
        "defaults": {
            "isuCd": "ALL",
            "isuCd2": "ALL",
            "param1isuCd_finder_stkisu4_1": "KSQ",  # 코스닥
            "majagntComCd": "",                      # 주관사 = 전체
            "tecComType": "TEC",                     # 기업구분 = 기술성장기업
            "listTrack": "",                         # 상장트랙 = 전체
            "money": "1",
            "otherUnit": "1",
            "csvxls_isNo": "false",
        },
        "post": ["json_output_to_df"],
        "screen": "20043 공모가 대비 주가수익률",
    },
    "vi_triggered": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT22401",
        "method": "json",
        "menu_id": "MDC0202",
        "defaults": {
            "mktId": "ALL",
            "inqTpCd1": "01",   # 조회구분 = 일별
            "viKindCd": "ALL",  # VI유형 = 전체(동적/정적)
            "isuCd": "ALL",
            "isuCd2": "ALL",
            "param1isuCd_finder_stkisu1_0": "ALL",
        },
        "post": ["json_output_to_df"],
        "screen": "20023 변동성완화장치 발동종목 현황",
        "required": ["strtDd", "endDd"],
    },
    "vi_triggered_csv": {
        "bld": "dbms/MDC/STAT/issue/MDCSTAT22401",
        "method": "csv",
        "menu_id": "MDC0202",
        "defaults": {
            "mktId": "ALL",
            "inqTpCd1": "01",
            "viKindCd": "ALL",
            "tboxisuCd_finder_stkisu1_0": "전체",
            "isuCd": "ALL",
            "isuCd2": "ALL",
            "codeNmisuCd_finder_stkisu1_0": "",
            "param1isuCd_finder_stkisu1_0": "ALL",
            "csvxls_isNo": "true",
        },
        "post": ["read_csv_eucKR"],
        "screen": "20023 변동성완화장치 발동종목 현황 (CSV)",
        "required": ["strtDd", "endDd"],
    },
    "short_selling_individual": {
        "bld": "dbms/MDC/STAT/srt/MDCSTAT30101",
        "method": "json",
        "menu_id": "MDC0203",
        "defaults": {
            "searchType": "1",  # 조회구분 = 전종목
            "mktId": "STK",
            "secugrpId": ["STMFRTSCIFDRFS", "SRSW", "BC"],
            "inqCond": "STMFRTSCIFDRFSSRSWBC",
            "tboxisuCd_finder_srtisu1_2": "",
            "isuCd": "",
            "isuCd2": "",
            "codeNmisuCd_finder_srtisu1_2": "",
            "param1isuCd_finder_srtisu1_2": "",
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
        },
        "post": ["json_output_to_df"],
        "screen": "32001 개별종목 공매도 거래",
    },
    "listed_bonds": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT10801",
        "method": "json",
        "menu_id": "MDC03010201",
        "defaults": {"money": "2"},
        "post": ["json_output_to_df"],
        "screen": "14011 상장채권 상세검색",
    },
    "listed_bonds_csv": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT10801",
        "method": "csv",
        "menu_id": "MDC03010201",
        "defaults": {"money": "2"},
        "post": ["read_csv_eucKR"],
        "screen": "14011 상장채권 상세검색 (CSV)",
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
