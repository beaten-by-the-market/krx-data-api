"""시나리오 노트북 빌더: scenarios/_src/<유형>/<이름>.py → scenarios/<유형>/<이름>.ipynb (실행 결과 포함).

원본 형식 (셀 구분 주석)
    # %% [markdown]
    # # 제목
    # 설명 …
    # %%
    파이썬 코드 …

빌더가 하는 일
1. 첫 markdown 셀 아래에 "Colab에서 열기" 배지와 준비 셀 2개를 넣는다.
   - Colab일 때만 krx-data-api(GitHub)와 한글 폰트 패키지 설치
   - 공통 헬퍼(_tools/krx_helper.py 내용 그대로). Colab에서는 Secrets의 KRX_ID/KRX_PW를 환경변수로 넣는다.
2. 노트북을 실제로 실행해 출력까지 저장한다(--no-exec 이면 실행 안 함).
   실행 폴더는 레포 루트라서 로컬에서는 레포 .env 의 KRX_ID/KRX_PW 로 로그인한다.
   자격증명은 출력에 남지 않는다(헬퍼는 값을 출력하지 않음). 빌드 뒤 노트북에 자격증명이 들어갔는지 검사한다.

사용
    python scenarios/_tools/build.py                    # 전체
    python scenarios/_tools/build.py 1_bonds/01         # 경로에 이 문자열이 든 원본만
    python scenarios/_tools/build.py --no-exec …
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.platform.startswith("win"):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
REPO = SCEN.parent
SRC = SCEN / "_src"
GITHUB = "beaten-by-the-market/krx-data-api"
BRANCH = "main"

INSTALL_CELL = f"""# Colab에서만: krx-data-api 와 한글 차트 폰트 설치 (로컬에서는 건너뜀)
import sys
if "google.colab" in sys.modules:
    !pip -q install git+https://github.com/{GITHUB}.git koreanize-matplotlib"""


def parse(src: str) -> list[tuple[str, str]]:
    cells, kind, buf = [], None, []

    def flush():
        if kind is None:
            return
        text = "\n".join(buf).strip("\n")
        if kind == "markdown":
            text = "\n".join(re.sub(r"^# ?", "", ln) for ln in text.splitlines())
        if text.strip():
            cells.append((kind, text))

    for line in src.splitlines():
        if line.startswith("# %%"):
            flush()
            kind, buf = ("markdown" if "[markdown]" in line else "code"), []
        else:
            buf.append(line)
    flush()
    return cells


def _secrets() -> list[str]:
    """레포 .env / 환경변수의 KRX 자격증명 값(검사용, 출력하지 않음)."""
    vals = {os.environ.get("KRX_ID"), os.environ.get("KRX_PW")}
    env = REPO / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() in ("KRX_ID", "KRX_PW"):
                    vals.add(v.strip().strip('"').strip("'"))
    return [v for v in vals if v and len(v) >= 4]


def _leaks(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return any(v in text for v in _secrets())


def build(src_path: Path, execute: bool = True) -> Path:
    rel = src_path.relative_to(SRC).with_suffix(".ipynb")
    out = SCEN / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    cells = parse(src_path.read_text(encoding="utf-8"))
    if not cells or cells[0][0] != "markdown":
        raise SystemExit(f"{src_path}: 첫 셀은 제목 markdown 이어야 합니다")

    url = f"https://colab.research.google.com/github/{GITHUB}/blob/{BRANCH}/scenarios/{quote(rel.as_posix())}"
    badge = f"[![Colab에서 열기](https://colab.research.google.com/assets/colab-badge.svg)]({url})"
    helper = (HERE / "krx_helper.py").read_text(encoding="utf-8").strip()
    setup_md = ("## 0. 준비\n"
                "2026-09부터 KRX는 로그인하지 않은 요청을 거절합니다. "
                "Colab 왼쪽 🔑(Secrets)에 `KRX_ID`, `KRX_PW`(KRX 정보데이터시스템 계정)를 등록하고 "
                "이 노트북의 액세스를 켠 뒤 아래 두 셀을 실행하세요. "
                "두 번째 셀은 모든 시나리오에 공통인 헬퍼입니다(접어 두어도 됩니다). 계정 값은 출력하지 않습니다.")

    nb = nbformat.v4.new_notebook()
    nb.metadata = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                   "language_info": {"name": "python"},
                   "colab": {"provenance": [], "toc_visible": True}}
    nb.cells.append(nbformat.v4.new_markdown_cell(cells[0][1] + "\n\n" + badge))
    nb.cells.append(nbformat.v4.new_markdown_cell(setup_md))
    nb.cells.append(nbformat.v4.new_code_cell(INSTALL_CELL))
    nb.cells.append(nbformat.v4.new_code_cell(helper, metadata={"cellView": "form", "jupyter": {"source_hidden": True}}))
    for kind, text in cells[1:]:
        nb.cells.append(nbformat.v4.new_markdown_cell(text) if kind == "markdown" else nbformat.v4.new_code_cell(text))

    ok = True
    if execute:
        client = NotebookClient(nb, timeout=900, kernel_name="python3",
                                resources={"metadata": {"path": str(REPO)}})
        try:
            client.execute()
        except CellExecutionError as e:
            ok = False
            print(f"✗ {rel} — 실행 오류 (오류까지 저장함)\n{str(e)[-1500:]}")
    nbformat.write(nb, out)
    if _leaks(out):
        out.unlink()
        raise SystemExit(f"✗ {rel} — 출력에 KRX 자격증명이 들어 있어 파일을 지웠습니다. 원본을 고치세요.")
    if ok:
        print(f"✓ {rel}")
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    execute = "--no-exec" not in sys.argv
    srcs = sorted(p for p in SRC.rglob("*.py"))
    if args:
        srcs = [p for p in srcs if any(a in p.relative_to(SRC).as_posix() for a in args)]
    if not srcs:
        raise SystemExit("빌드할 원본이 없습니다")
    for p in srcs:
        build(p, execute)


if __name__ == "__main__":
    main()
