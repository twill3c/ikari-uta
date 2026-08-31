"""巻ごとの固有名詞を、対訳表に照らして二本立てで出す。

HC-092。「表に無い語」だけを出すと新規登録の必要は分かるが、**すでに凍結
された表記との衝突は防げない**。着手前に既出側も並べて提示することが、
表記揺れの予防になる。凍結表記は変えない —— 訳文の側を合わせる。

    python pipeline/measure_names.py 7
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAP = re.compile(r"\b([A-Z][a-z]{2,})\b")
# 行頭の英訳に現れる普通の語。固有名詞ではないので候補から外す。
NOISE = frozenset({
    "Aloud", "Bid", "Hath", "Presently", "Soft", "Unhappy", "Then", "But",
    "And", "For", "Now", "Thus", "There", "When", "Yet", "Nay", "The", "His",
    "Her", "They", "That", "This", "With", "From", "Who", "She", "Him",
})


def load_glossary() -> dict[str, str]:
    """英語見出し → 和名。本体と一覧の両方を混ぜる(G-03 と同じ範囲)。"""
    out: dict[str, str] = {}
    for name in ("glossary.json", "glossary.catalogue.json"):
        path = ROOT / "data" / name
        if not path.exists():
            continue
        for e in json.loads(path.read_text(encoding="utf-8"))["entries"]:
            out.setdefault(e["eng"], e["ja"])
    return out


def main(book: int) -> int:
    eng = json.loads((ROOT / "data" / "english" / f"book-{book:02d}.json").read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for seg in eng["segments"]:
        for w in CAP.findall(seg["text"]):
            if w not in NOISE:
                counts[w] = counts.get(w, 0) + 1

    gloss = load_glossary()
    known = {w: gloss[w] for w in counts if w in gloss}
    fresh = {w: c for w, c in counts.items() if w not in gloss}

    print(f"=== 第 {book} 巻 ===")
    print(f"\n■ 既出 {len(known)} 語 —— 表記は凍結済み。この綴りをそのまま使う")
    for w in sorted(known, key=lambda w: -counts[w]):
        print(f"  {w:<16} {known[w]}  ({counts[w]})")
    print(f"\n■ 新規 {len(fresh)} 語 —— 対訳表への登録が要る")
    for w in sorted(fresh, key=lambda w: -counts[w]):
        print(f"  {w:<16} ({counts[w]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1])))
