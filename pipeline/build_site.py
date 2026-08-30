"""出荷物を生成する(F-06 / F-07 / F-08 / N-01 / N-06)。

**このスクリプトは外部を一切呼ばない。** 訳は開発時に生成済みで、ここでは組み替えるだけである。
ビルドに LLM もネットワークも要らないことが、課金経路ゼロの根拠になっている(N-02)。

配信 JSON は巻ごとに分ける(N-06)。目次で全巻を配ると、読み始める前に数 MB を落とすことになる。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = PROJECT_ROOT / "data" / "canonical"
ENGLISH_DIR = PROJECT_ROOT / "data" / "english"
JA_DIR = PROJECT_ROOT / "data" / "ja"
OUT_DIR = PROJECT_ROOT / "out"
ASSETS = PROJECT_ROOT / "site"

ATTRIBUTION = (
    "原文: Homer, <i>Ilias</i>, ed. D. B. Monro &amp; T. W. Allen (Oxford, 1920). "
    "英訳: A. T. Murray (Loeb, 1924). "
    'いずれも <a href="https://github.com/PerseusDL/canonical-greekLit">Perseus Digital Library</a>, '
    "Tufts University — <b>CC BY-SA 4.0</b>。本サイトの生成データも同ライセンスで継承する。"
)

DISCLAIMER = (
    "日本語訳は <b>Claude による機械翻訳</b>であり、学術的な定訳ではない。"
    "本サイトが検査で保証するのは<b>行の対応と表記の一貫性</b>であって、訳の正確さではない。"
)


def footer() -> str:
    return f"""<footer>
 <p class="attr">{ATTRIBUTION}</p>
 <p class="warn">{DISCLAIMER}</p>
 <p class="meta">怒り歌(ikari-uta) — <a href="https://github.com/PerseusDL/canonical-greekLit">底本</a> ·
 行番号は底本のものをそのまま用いる(欠番あり)</p>
</footer>"""


def load_books() -> list[dict]:
    books = []
    for path in sorted(CANONICAL_DIR.glob("book-*.json")):
        canon = json.loads(path.read_text(encoding="utf-8"))
        n = canon["book"]

        eng_path = ENGLISH_DIR / f"book-{n:02d}.json"
        eng = json.loads(eng_path.read_text(encoding="utf-8")) if eng_path.exists() else None

        ja_path = JA_DIR / f"book-{n:02d}.json"
        ja = json.loads(ja_path.read_text(encoding="utf-8")) if ja_path.exists() else None

        books.append({"canon": canon, "eng": eng, "ja": ja})
    return books


def write_book_json(entry: dict, out_data: Path) -> dict:
    canon, eng, ja = entry["canon"], entry["eng"], entry["ja"]
    n = canon["book"]
    ja_map = {ln["n"]: ln["ja"] for ln in ja["lines"]} if ja else {}

    lines = [
        {"n": ln["n"], "grc": ln["grc"], **({"ja": ja_map[ln["n"]]} if ln["n"] in ja_map else {})}
        for ln in canon["lines"]
    ]
    payload = {
        "book": n,
        "line_count": canon["line_count"],
        "line_max": canon["line_max"],
        "missing": canon["missing"],
        "translated": ja is not None,
        "lines": lines,
        "english": eng["segments"] if eng else [],
    }
    (out_data / f"book-{n:02d}.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return {
        "book": n,
        "line_count": canon["line_count"],
        "line_max": canon["line_max"],
        "missing": canon["missing"],
        "translated": ja is not None,
    }


def render_index(manifest: dict) -> str:
    rows = []
    for b in manifest["books"]:
        n = b["book"]
        state = (
            '<span class="ok">訳あり</span>'
            if b["translated"]
            else '<span class="todo">準備中</span>'
        )
        gap = (
            f'<span class="gap" title="底本の欠番">欠 {", ".join(map(str, b["missing"]))}</span>'
            if b["missing"]
            else ""
        )
        link = (
            f'<a href="read.html?book={n}">第 {n} 巻</a>'
            if b["translated"]
            else f'<a href="read.html?book={n}">第 {n} 巻</a>'
        )
        rows.append(
            f'<li class="{"has" if b["translated"] else "not"}">{link}'
            f'<span class="cnt">{b["line_count"]:,} 行</span>{state}{gap}</li>'
        )

    total = manifest["extant_lines"]
    maxsum = manifest["sum_of_maxima"]
    done = sum(b["line_count"] for b in manifest["books"] if b["translated"])

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>怒り歌 — イーリアスを原文の行番号のまま読む</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
 <h1>怒り歌</h1>
 <p class="sub">ホメロス『イーリアス』全 24 巻を、<b>原文の行番号を保ったまま</b>日本語で読む</p>
</header>
<main>
<section class="facts">
 <h2>底本の実測</h2>
 <p>行番号は底本のものをそのまま用いる。<b>連番ではない。</b></p>
 <table>
  <tr><th>巻</th><td>24</td></tr>
  <tr><th>実在する行</th><td><b>{total:,}</b></td></tr>
  <tr><th>行番号の最大値の和</th><td>{maxsum:,}</td></tr>
  <tr><th>差</th><td>{maxsum - total} 行(編者が本文から除き、番号だけ残した行)</td></tr>
  <tr><th>訳済み</th><td>{done:,} 行 / {total:,} 行</td></tr>
 </table>
 <p class="note">「イーリアスは 15,693 行」という数字は、実は<b>各巻の行番号の最大値を足したもの</b>である。
 実際に本文がある行は {total:,} 行しかない。差の {maxsum - total} 行は第 9 巻 458–461・第 11 巻 543・第 14 巻 269 で、
 校訂者が本文から除きながら番号を残したものである。第 9 巻は 457 の次が 462 になる。</p>
</section>
<section>
 <h2>巻</h2>
 <ol class="books">{"".join(rows)}</ol>
</section>
</main>
{footer()}
</body>
</html>
"""


def render_reader() -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>怒り歌 — 読む</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="reader">
 <p class="home"><a href="index.html">← 目次</a></p>
 <h1 id="title">読み込み中</h1>
 <nav class="views">
  <label><input type="checkbox" id="v-ja" checked> 和訳</label>
  <label><input type="checkbox" id="v-grc"> 原文</label>
  <label><input type="checkbox" id="v-eng"> 英訳</label>
 </nav>
 <p id="status" class="status"></p>
</header>
<main><div id="text" class="text"></div></main>
{footer()}
<script src="reader.js"></script>
</body>
</html>
"""


def build() -> dict:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    out_data = OUT_DIR / "data"
    out_data.mkdir(parents=True)

    entries = load_books()
    books = [write_book_json(e, out_data) for e in entries]
    manifest = {
        "books": books,
        "extant_lines": sum(b["line_count"] for b in books),
        "sum_of_maxima": sum(b["line_max"] for b in books),
        "source": {
            "urn": "urn:cts:greekLit:tlg0012.tlg001.perseus-grc2",
            "edition": "Monro & Allen, Editio Tertia (Oxford)",
            "license": "CC BY-SA 4.0",
            "attribution": "Perseus Digital Library, Tufts University",
        },
    }
    (out_data / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    (OUT_DIR / "index.html").write_text(render_index(manifest), encoding="utf-8")
    (OUT_DIR / "read.html").write_text(render_reader(), encoding="utf-8")
    for name in ("style.css", "reader.js"):
        shutil.copyfile(ASSETS / name, OUT_DIR / name)

    return manifest


def main() -> int:
    m = build()
    done = sum(b["line_count"] for b in m["books"] if b["translated"])
    print(f"巻 {len(m['books'])} / 実在行 {m['extant_lines']:,} / 訳済み {done:,} 行")
    print(f"→ {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
