"""Murray 英訳を、原文行番号に錨づけた区間列として取り出す(F-06 / F-13 の材料)。

**混合内容の要素境界には区切りを入れる(HC-082)。** この底本は本文の途中に
`<milestone unit="line"/>` が挟まる。`"".join(el.itertext())` で連結すると
その位置で語が結合し(`Achaeansone` 等)、例外を出さないまま名前を取りこぼす。

分解能の限界を明記しておく: 行アンカーは 5 行おきである(SPEC §3.1 実測)。
**英訳に行単位の一致を要求してはならない。** ここが返すのは「±5 行の窓」である。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

TEI_NS = "http://www.tei-c.org/ns/1.0"
Q = f"{{{TEI_NS}}}"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = PROJECT_ROOT / "data" / "raw" / "tlg0012.tlg001.perseus-eng3.xml"
ENGLISH_DIR = PROJECT_ROOT / "data" / "english"

_WS = re.compile(r"\s+")

# 底本側の非増加アンカーは全 24 巻 3,143 アンカー中 3 件のみ(2026-08-31 実測)。
# **2 つは別の現象であり、扱いを分ける。**
#
# (1) 同値アンカー — 同じ 5 行窓の中に段落境界が 2 つあるだけで、±5 行の窓モデルを
#     壊さない。よって一般に許す。ただし集合を実測値に固定し、増えたら見に行く。
#     **母集団で数が変わることに注意する。** 生の milestone では 2 件だが、
#     区間では 1 件になる。第 20 巻は milestone n="1" が間に文字を挟まず 2 回続き、
#     前者が空区間として正しく捨てられるためである(実測 2026-08-31)。
#     どちらの数も正しい。数える対象を言わずに定数を置くと、正しい実装が落ちる。
# (2) 逆行アンカー 1 件 — 第 13 巻 830 → 825。こちらは錨づけの誤りである。
#     **緩めるのはこの 1 件だけ**で、他の逆行は今後も例外で止める。
KNOWN_ANCHOR_REGRESSIONS: frozenset[tuple[int, int, int]] = frozenset({(13, 830, 825)})
MEASURED_DUPLICATE_ANCHORS_RAW: frozenset[tuple[int, int]] = frozenset({(2, 720), (20, 1)})
MEASURED_DUPLICATE_ANCHORS_SEGMENTS: frozenset[tuple[int, int]] = frozenset({(2, 720)})


def _collapse(parts: list[str]) -> str:
    """要素境界を空白で区切ってから畳む。区切りを入れるのがこの関数の要点である。"""
    return _WS.sub(" ", " ".join(parts)).strip()


def book_segments(book_div: ET.Element) -> list[dict]:
    """1 巻分を、行アンカーごとの区間に切る。"""
    segments: list[dict] = []
    buf: list[str] = []
    anchor: int | None = None

    def flush() -> None:
        text = _collapse(buf)
        buf.clear()
        if anchor is not None and text:
            segments.append({"from_line": anchor, "text": text})

    def walk(el: ET.Element) -> None:
        nonlocal anchor
        if el.tag == f"{Q}milestone" and el.get("unit") == "line":
            v = el.get("n")
            if v and v.isdigit():
                flush()
                anchor = int(v)
        else:
            if el.text:
                buf.append(el.text)
            for child in el:
                walk(child)
        if el.tail:
            buf.append(el.tail)

    walk(book_div)
    flush()
    return segments


def parse_books(src: Path | str = DEFAULT_SRC) -> list[dict]:
    root = ET.parse(str(src)).getroot()
    divs = [d for d in root.iter(f"{Q}div") if (d.get("subtype") or "").lower() == "book"]
    if not divs:
        raise ValueError("英訳に巻の div が見つからない")

    books: list[dict] = []
    for div in divs:
        v = div.get("n")
        if v is None or not v.isdigit():
            raise ValueError(f"英訳の巻番号が数値でない: {v!r}")
        segs = book_segments(div)
        if not segs:
            raise ValueError(f"英訳 巻 {v}: 区間が 1 つも取れない")
        anchors = [s["from_line"] for s in segs]
        for x, y in zip(anchors, anchors[1:]):
            # 同値は許す(同じ窓に段落境界が 2 つあるだけ)。逆行だけを止める。
            if y < x and (int(v), x, y) not in KNOWN_ANCHOR_REGRESSIONS:
                raise ValueError(f"英訳 巻 {v}: 行アンカーが逆行する({x} → {y})")
        books.append({"book": int(v), "segments": segs, "anchor_count": len(segs)})

    books.sort(key=lambda b: b["book"])
    return books


def concatenation_suspects(books: list[dict], vocabulary: set[str]) -> list[str]:
    """既知の 2 語の連結でしか説明できない綴りを探す(HC-082 の実データ全域検査)。

    語彙に無い語のうち、既知語 A + 既知語 B にちょうど割れるものを疑わしいとして返す。
    """
    known = {w.lower() for w in vocabulary if len(w) >= 3}
    suspects: list[str] = []
    seen: set[str] = set()
    for b in books:
        for seg in b["segments"]:
            for tok in re.findall(r"[A-Za-z]{6,}", seg["text"]):
                low = tok.lower()
                if low in known or low in seen:
                    continue
                for i in range(3, len(low) - 2):
                    if low[:i] in known and low[i:] in known:
                        suspects.append(tok)
                        seen.add(low)
                        break
    return suspects


def main() -> int:
    ap = argparse.ArgumentParser(description="英訳 → 行アンカー区間(照合・表示用)")
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=ENGLISH_DIR)
    args = ap.parse_args()

    books = parse_books(args.src)
    args.out.mkdir(parents=True, exist_ok=True)
    for b in books:
        dest = args.out / f"book-{b['book']:02d}.json"
        dest.write_text(json.dumps(b, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    total = sum(b["anchor_count"] for b in books)
    print(f"巻 {len(books)} / 行アンカー区間 {total:,}")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
