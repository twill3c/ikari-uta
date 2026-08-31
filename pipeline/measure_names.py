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
    print(
        "※ 突き合わせは対訳表の英語見出し(eng)と英訳本文の語。"
        "両者は同じ名前でも違う語になることがある"
        "(Γοργώ は表では Gorgon、本文では Gorgo)。"
    )
    print(
        "  したがって**新規の側には既登録語が紛れ、既出の側からは同じ数だけ漏れる**。"
        "守りは既出側なので、登録前に必ず原語で引き直すこと"
        "(python pipeline/measure_names.py --grc <原語の一部>)。"
    )
    print(f"\n■ 既出 {len(known)} 語 —— 表記は凍結済み。この綴りをそのまま使う")
    for w in sorted(known, key=lambda w: -counts[w]):
        print(f"  {w:<16} {known[w]}  ({counts[w]})")
    print(f"\n■ 新規 {len(fresh)} 語 —— 対訳表への登録が要る")
    for w in sorted(fresh, key=lambda w: -counts[w]):
        print(f"  {w:<16} ({counts[w]})")
    return 0


def lookup(fragment: str) -> None:
    """原語の一部で対訳表を引く。新規かどうかの最終判断はこちらで行う。"""
    for name in ("glossary.json", "glossary.catalogue.json"):
        path = ROOT / "data" / name
        if not path.exists():
            continue
        for e in json.loads(path.read_text(encoding="utf-8"))["entries"]:
            if fragment in e["grc"]:
                print(f"  {e['grc']} → {e['ja']}  (eng={e['eng']})")


KATAKANA = re.compile(r"[ァ-ヺー]{2,}")


def check(tsv: str) -> int:
    """訳した直後の TSV を、その場で対訳表に照らす。

    T-015 と同じことを、巻を訳し終える前に一区切りごとに行うための入口。
    loop_014 と loop_016 で**同じ語(プローテシラーオス / 正: プロテシラーオス)を
    同じように誤った**。長音の有無のような差は記憶では防げないので、
    書いた直後に機械が言う経路を置く。凍結表記が正 —— 訳文の側を直す。
    """
    known: set[str] = set()
    for name in ("glossary.json", "glossary.catalogue.json"):
        path = ROOT / "data" / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        known.update(e["ja"] for e in data["entries"])
        known.update(data.get("allow_katakana", []))

    offenders = []
    for i, line in enumerate(pathlib.Path(tsv).read_text(encoding="utf-8").splitlines(), 1):
        if "\t" not in line:
            continue
        n, ja = line.split("\t", 1)
        for term in KATAKANA.findall(ja):
            if not any(term in k or k in term for k in known):
                offenders.append((n, term))

    if not offenders:
        print(f"OK: {tsv} に表外のカタカナは無い")
        return 0
    print(f"表外のカタカナ {len(offenders)} 件 —— 原語で引き直すこと:")
    for n, term in offenders:
        print(f"  行 {n}: {term}")
    return 1


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--grc":
        lookup(sys.argv[2])
        raise SystemExit(0)
    if len(sys.argv) > 2 and sys.argv[1] == "--check":
        raise SystemExit(check(sys.argv[2]))
    raise SystemExit(main(int(sys.argv[1])))
