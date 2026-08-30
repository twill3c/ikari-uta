"""経路 B — 生バイト列の線形走査で行番号を数える(行数オラクル)。

**経路 A(parse_tei)と実装を共有しない。** A は要素の親子関係を見る。B はバイト列の
出現順序だけを見る。木構造の解釈を共有しないので、両者の一致は恒等式ではない(HC-045)。

ここで `xml.etree` を import してはならない。import した時点でこのオラクルは
経路 A の写しになり、照合が何も検査しなくなる。
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = PROJECT_ROOT / "data" / "raw" / "tlg0012.tlg001.perseus-grc2.xml"
ORACLE_PATH = PROJECT_ROOT / "data" / "oracle" / "line_counts.json"

# 走査は「開始タグの出現順」だけを見る。入れ子の深さも閉じタグも見ない。
_BOOK_OPEN = re.compile(
    rb'<div\b[^>]*\bsubtype="Book"[^>]*\bn="(\d+)"|<div\b[^>]*\bn="(\d+)"[^>]*\bsubtype="Book"',
    re.IGNORECASE,
)
_LINE_OPEN = re.compile(rb'<l\b[^>]*\bn="(\d+)"', re.IGNORECASE)
_TOKEN = re.compile(
    rb'<div\b[^>]*?>|<l\b[^>]*?>',
    re.IGNORECASE,
)


def scan(src: Path | str = DEFAULT_SRC) -> list[dict]:
    """バイト列を先頭から舐め、巻ごとの行番号列を出現順に集める。"""
    blob = Path(src).read_bytes()

    books: list[dict] = []
    current: dict | None = None

    for m in _TOKEN.finditer(blob):
        tok = m.group(0)
        if tok[:4].lower() == b"<div":
            bm = _BOOK_OPEN.match(tok)
            if bm:
                n = bm.group(1) or bm.group(2)
                current = {"book": int(n), "line_numbers": []}
                books.append(current)
            continue
        lm = _LINE_OPEN.match(tok)
        if lm:
            if current is None:
                raise ValueError("巻の外に <l> が現れた")
            current["line_numbers"].append(int(lm.group(1)))

    if not books:
        raise ValueError("巻が 1 つも見つからない")

    for b in books:
        ns = b["line_numbers"]
        if not ns:
            raise ValueError(f"巻 {b['book']}: 行が 1 つも無い")
        b["count"] = len(ns)
        b["max"] = max(ns)
        b["missing"] = sorted(set(range(1, b["max"] + 1)) - set(ns))

    books.sort(key=lambda b: b["book"])
    return books


def build_oracle(src: Path | str = DEFAULT_SRC) -> dict:
    books = scan(src)
    return {
        "measured_on": date.today().isoformat(),
        "source": Path(src).name,
        "path": "B (linear byte scan)",
        "books": len(books),
        "extant_lines": sum(b["count"] for b in books),
        "sum_of_maxima": sum(b["max"] for b in books),
        "per_book": [
            {"book": b["book"], "count": b["count"], "max": b["max"], "missing": b["missing"]}
            for b in books
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="行数オラクルの生成(経路 B)")
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=ORACLE_PATH)
    args = ap.parse_args()

    oracle = build_oracle(args.src)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(oracle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    gaps = {b["book"]: b["missing"] for b in oracle["per_book"] if b["missing"]}
    print(f"巻 {oracle['books']} / 実在行 {oracle['extant_lines']:,} / 最大値の和 {oracle['sum_of_maxima']:,}")
    print(f"差 {oracle['sum_of_maxima'] - oracle['extant_lines']} 行 → 欠番 {gaps}")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
