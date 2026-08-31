"""出荷物の検査。TEST_SPEC T-020〜T-025。

「課金経路を持たない」は主張ではなく検査で担保する(N-01/N-02)。
"""

import json
import re
from pathlib import Path

import pytest

from tests.conftest import OUT_DIR, PROJECT_ROOT

pytestmark = pytest.mark.integration


def _out_html() -> list[Path]:
    if not OUT_DIR.exists():
        pytest.skip("出荷物が未生成")
    files = sorted(OUT_DIR.rglob("*.html"))
    if not files:
        pytest.skip("出荷 HTML が無い")
    return files


def test_t020_no_server_functions():
    """T-020 / N-01: サーバ関数を持たない。"""
    assert not (PROJECT_ROOT / "api").exists(), "api/ が存在する(サーバ関数の経路)"
    assert not (OUT_DIR / "api").exists(), "out/api/ が存在する"
    vercel = PROJECT_ROOT / "vercel.json"
    if vercel.exists():
        conf = json.loads(vercel.read_text(encoding="utf-8"))
        for key in ("functions", "crons", "rewrites", "redirects"):
            if key in ("functions", "crons"):
                assert key not in conf, f"vercel.json に {key} がある(課金経路)"


def test_t021_no_external_network_in_shipped_js():
    """T-021 / N-01: 出荷 JS の通信先が相対パスのみ。"""
    files = list(OUT_DIR.rglob("*.js")) + _out_html() if OUT_DIR.exists() else []
    if not files:
        pytest.skip("出荷物が未生成")
    # http(s):// を伴う fetch / XMLHttpRequest / WebSocket / import() を禁ずる。
    pattern = re.compile(
        r"""(fetch|XMLHttpRequest|WebSocket|importScripts)\s*\(\s*['"`]https?://""",
        re.IGNORECASE,
    )
    offenders = []
    for p in files:
        body = p.read_text(encoding="utf-8", errors="replace")
        for m in pattern.finditer(body):
            offenders.append(f"{p.relative_to(PROJECT_ROOT)}: {m.group(0)}")
    assert not offenders, f"外部通信の呼び出し: {offenders}"


def test_t021b_positive_control_external_fetch_is_caught(tmp_path):
    """陽性対照: 外部 fetch を書いたファイルをパターンが捕まえること。"""
    pattern = re.compile(
        r"""(fetch|XMLHttpRequest|WebSocket|importScripts)\s*\(\s*['"`]https?://""",
        re.IGNORECASE,
    )
    assert pattern.search('fetch("https://example.com/x.json")')
    # 陰性対照: 相対パスの取得は違反ではない
    assert not pattern.search('fetch("data/book-01.json")')


def test_t022_no_llm_api_in_build_path():
    """T-022 / N-02: ビルド経路に LLM API 呼び出しが無い。

    翻訳は開発時に生成してコミットする。ビルドでモデルを呼ばない。
    引用・言及(この docstring のような説明文)と、使用・依存を分けるため、
    検査対象は実行されるコードに限り、コメント行は除く。
    """
    targets = list((PROJECT_ROOT / "pipeline").glob("*.py"))
    build = PROJECT_ROOT / "build.py"
    if build.exists():
        targets.append(build)
    banned = re.compile(r"(api\.anthropic\.com|openai\.com|anthropic\.Anthropic\()")
    offenders = []
    for p in targets:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if banned.search(code):
                offenders.append(f"{p.name}:{i}")
    assert not offenders, f"ビルド経路に LLM 呼び出し: {offenders}"


def test_t023_attribution_on_every_page():
    """T-023 / G-05 / F-07: 全 HTML に帰属・ライセンス・機械翻訳の明示がある。"""
    required = ["Perseus", "CC BY-SA 4.0", "機械翻訳"]
    for p in _out_html():
        body = p.read_text(encoding="utf-8")
        missing = [r for r in required if r not in body]
        assert not missing, f"{p.name} に不足: {missing}"


def test_t024_untranslated_books_marked():
    """T-024 / F-08: 未訳の巻が「準備中」と明示される。"""
    index = OUT_DIR / "index.html"
    if not index.exists():
        pytest.skip("index.html が未生成")
    body = index.read_text(encoding="utf-8")
    manifest = json.loads((OUT_DIR / "data" / "manifest.json").read_text(encoding="utf-8"))
    translated = [b for b in manifest["books"] if b["translated"]]
    untranslated = [b for b in manifest["books"] if not b["translated"]]
    assert translated, "訳済みの巻が 1 つも無い"
    assert untranslated, "未訳の巻が無い。この検査は loop_001 時点で意味を持つべきである"
    assert "準備中" in body, "未訳を示す表示が index に無い"


def test_t025_per_book_json_split():
    """T-025 / N-06: 配信 JSON が巻ごとに分かれ、全巻一括ファイルが無い。"""
    data_dir = OUT_DIR / "data"
    if not data_dir.exists():
        pytest.skip("配信データが未生成")
    books = sorted(data_dir.glob("book-*.json"))
    assert len(books) >= 24, f"巻別 JSON が {len(books)} 件しかない"
    manifest = data_dir / "manifest.json"
    assert manifest.exists()
    # 全巻を 1 枚に束ねたファイルが紛れていないこと
    big = [p for p in data_dir.glob("*.json") if p.stat().st_size > 3_000_000]
    assert not big, f"巨大な一括ファイル: {[p.name for p in big]}"


def test_t032_progress_figure_matches_data():
    """T-032: 目次が表示する訳済み行数が、実データの訳済み行数と一致する。

    「訳済みの巻の原文行数」を足すと、部分訳の巻で進捗を過大に見せる。
    数が正しくても図が嘘をつく型の欠陥なので、表示側を実データに突き合わせる。
    """
    index = OUT_DIR / "index.html"
    manifest_path = OUT_DIR / "data" / "manifest.json"
    if not index.exists() or not manifest_path.exists():
        pytest.skip("出荷物が未生成")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = sum(b["translated_lines"] for b in manifest["books"])

    # 巻別 JSON から独立に数え直す(manifest を鵜呑みにしない)
    counted = 0
    for b in manifest["books"]:
        payload = json.loads(
            (OUT_DIR / "data" / f"book-{b['book']:02d}.json").read_text(encoding="utf-8")
        )
        counted += sum(1 for ln in payload["lines"] if "ja" in ln)
    assert counted == expected, f"manifest の訳済み {expected} が実データ {counted} と食い違う"

    body = index.read_text(encoding="utf-8")
    assert f"{expected:,} 行 /" in body, (
        f"目次に訳済み {expected:,} 行が出ていない。過大表示の疑い"
    )
