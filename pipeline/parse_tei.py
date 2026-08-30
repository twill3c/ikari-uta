"""経路 A — TEI を DOM として walk し、正準データを作る(F-02 / F-03)。

**行番号は明示的に保持する。添字から導出してはならない。**
底本には編者が本文から除いて番号だけ残した行がある(第 9 巻 458–461 / 第 11 巻 543 /
第 14 巻 269 — SPEC §3.1)。添字と行番号を同一視すると、そこから下流が黙って 4 行ずれる。

仮定が崩れたらその場で例外にする(HC-075)。行番号の重複・非単調・非数値は、
黙って違う結果を出すのではなく `ValueError` で止める。
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from xml.etree import ElementTree as ET

TEI_NS = "http://www.tei-c.org/ns/1.0"
Q = f"{{{TEI_NS}}}"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = PROJECT_ROOT / "data" / "raw" / "tlg0012.tlg001.perseus-grc2.xml"
CANONICAL_DIR = PROJECT_ROOT / "data" / "canonical"

_WS = re.compile(r"\s+")


def _line_text(el: ET.Element) -> str:
    """<l> の本文を取り出す。子の milestone/q は構造なので落とし、文字だけを連ねる。"""
    text = "".join(el.itertext())
    # TEI の改行・字下げは組版の都合。1 行 = 1 行として扱うため空白は 1 つに畳む。
    return _WS.sub(" ", text).strip()


def _book_divs(root: ET.Element) -> list[ET.Element]:
    divs = [d for d in root.iter(f"{Q}div") if (d.get("subtype") or "").lower() == "book"]
    if not divs:
        raise ValueError("巻の div が 1 つも見つからない(subtype='Book' を期待)")
    return divs


def parse_books(src: Path | str = DEFAULT_SRC) -> list[dict]:
    """底本 XML を巻・行に分解する。仮定が崩れたら例外で止める。"""
    root = ET.parse(str(src)).getroot()
    books: list[dict] = []

    for div in _book_divs(root):
        raw_n = div.get("n")
        if raw_n is None or not raw_n.isdigit():
            raise ValueError(f"巻番号が数値でない: {raw_n!r}")
        book_no = int(raw_n)

        lines: list[dict] = []
        seen: set[int] = set()
        prev: int | None = None

        for el in div.iter(f"{Q}l"):
            v = el.get("n")
            if v is None or not v.isdigit():
                raise ValueError(f"巻 {book_no}: 行番号が数値でない: {v!r}")
            n = int(v)
            if n in seen:
                raise ValueError(f"巻 {book_no}: 行番号 {n} が重複している")
            if prev is not None and n <= prev:
                raise ValueError(f"巻 {book_no}: 行番号が単調増加でない({prev} → {n})")
            seen.add(n)
            prev = n
            lines.append({"n": n, "grc": _line_text(el)})

        if not lines:
            raise ValueError(f"巻 {book_no}: 行が 1 つも無い")

        present = {ln["n"] for ln in lines}
        missing = sorted(set(range(1, max(present) + 1)) - present)
        books.append(
            {
                "book": book_no,
                "line_count": len(lines),
                "line_max": max(present),
                "missing": missing,
                "lines": lines,
            }
        )

    books.sort(key=lambda b: b["book"])
    return books


def normalize_greek(s: str) -> str:
    """比較用の正規化。表示用の本文には使わない。"""
    return unicodedata.normalize("NFC", s)


def main() -> int:
    ap = argparse.ArgumentParser(description="TEI → 正準データ(経路 A)")
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=CANONICAL_DIR)
    args = ap.parse_args()

    books = parse_books(args.src)
    args.out.mkdir(parents=True, exist_ok=True)
    for b in books:
        dest = args.out / f"book-{b['book']:02d}.json"
        dest.write_text(json.dumps(b, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    total = sum(b["line_count"] for b in books)
    max_sum = sum(b["line_max"] for b in books)
    gaps = {b["book"]: b["missing"] for b in books if b["missing"]}
    print(f"巻 {len(books)} / 実在行 {total:,} / 行番号最大値の和 {max_sum:,} / 差 {max_sum - total}")
    print(f"欠番: {gaps}")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
