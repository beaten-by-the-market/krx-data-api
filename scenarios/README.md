# 케이스 시나리오 노트북

`krx_data_api.fetch()`로 KRX 정보데이터시스템 데이터를 받아 질문 하나에 답하는 Colab 노트북 모음입니다.
각 노트북은 실행 결과까지 저장돼 있어 열기만 해도 결과를 볼 수 있고, Colab에서 바로 다시 실행할 수 있습니다.

| 번호 | 시나리오 | 쓰는 엔드포인트 | 설명 |
|---|---|---|---|
| 1-01 | [당일 상장채권](1_bonds/01_listed_bonds_by_date.ipynb) | `listed_bonds`, `listed_bonds_csv` | [하루·기간별 신규 상장 채권 목록과 건수](1_bonds/01_listed_bonds_by_date.md) |
| 2-01 | [주가 변동성 시나리오](2_stock_price/01_price_scenario_fan.ipynb) | `listed_stocks`, `individual_price_trend` | [과거 일별 수익률 부트스트랩으로 그린 가격 범위 (예측 아님)](2_stock_price/01_price_scenario_fan.md) |

## Colab에서 실행
1. 노트북 맨 위의 **Colab에서 열기** 배지를 누릅니다.
2. 왼쪽 🔑(Secrets)에 `KRX_ID`, `KRX_PW`(KRX 정보데이터시스템 계정)를 넣고 노트북 액세스를 켭니다. 2026-09부터 KRX는 로그인하지 않은 요청을 거절합니다.
3. 위에서부터 차례로 실행합니다. 첫 준비 셀이 `pip install git+https://github.com/beaten-by-the-market/krx-data-api.git`로 패키지를 설치합니다.

## 고치고 다시 만들기
- 원본은 `_src/<유형>/<번호_이름>.py`입니다(`# %% [markdown]` / `# %%`로 셀 구분, 첫 셀은 제목 markdown). `.ipynb`는 직접 고치지 마세요.
- `python scenarios/_tools/build.py 1_bonds/01` — 원본을 노트북으로 바꾸고 레포 루트에서 **실제로 실행**해 출력까지 저장합니다. 인자를 빼면 전체를 다시 만듭니다. 로컬에서는 레포 `.env`의 `KRX_ID`/`KRX_PW`로 로그인합니다.
- 빌더는 저장한 노트북에 `.env`의 자격증명 값이 들어 있으면 파일을 지우고 멈춥니다.
- `_tools/krx_helper.py`는 모든 노트북의 두 번째 준비 셀에 그대로 들어갑니다. 고친 뒤에는 전체를 다시 만드세요.
- 출력 확인: `python scenarios/_tools/show.py scenarios/1_bonds/01_listed_bonds_by_date.ipynb`
- 빌드에는 `nbformat`, `nbclient`, `ipykernel`, `matplotlib`이 필요합니다.
