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
        "※ 数える対象は**英訳本文**である。英訳者が原文に無い名を補うことがあり"
        "(第18巻の Nereus は πατρὶ γέροντι「老いた父」に対する補い、"
        "Linos は底本が小文字 λίνον と印刷する語)、それらはここに新規として現れる。"
        "**登録の前に、その名が原文に実在するかを canonical で確かめること。**"
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


def check(tsv: str) -> int:
    """訳した直後の TSV を、その場で対訳表に照らす。

    T-015 と同じことを、巻を訳し終える前に一区切りごとに行うための入口。
    loop_014 と loop_016 で**同じ語(プローテシラーオス / 正: プロテシラーオス)を
    同じように誤った**。長音の有無のような差は記憶では防げないので、
    書いた直後に機械が言う経路を置く。凍結表記が正 —— 訳文の側を直す。

    **判定は T-015 と同じ実装(pipeline.checks)を呼ぶ。** 以前ここは
    「対訳表の語を含むか」という緩い包含判定を持っていて、
    アテーナイエー は アテーナイ を含むという理由で通り抜けた
    (loop_020 と loop_022 で二度)。二つの検査が別々の判定を持っていること自体が
    欠陥だったので、実装を一本にした —— この検査を通れば T-015 も通る。
    """
    sys.path.insert(0, str(ROOT))   # スクリプト直接起動でも pipeline を解決できるように
    from pipeline import checks

    glossary: dict = {"entries": [], "allow_katakana": []}
    for name in ("glossary.json", "glossary.catalogue.json"):
        path = ROOT / "data" / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        glossary["entries"].extend(data["entries"])
        glossary["allow_katakana"].extend(data.get("allow_katakana", []))

    lines = []
    for line in pathlib.Path(tsv).read_text(encoding="utf-8").splitlines():
        if "	" in line:
            n, ja = line.split("	", 1)
            lines.append({"n": int(n), "ja": ja})
    offenders = checks.proper_nouns_outside_glossary({0: {"lines": lines}}, glossary)

    if not offenders:
        print(f"OK: {tsv} に表外のカタカナは無い")
        return 0
    print(f"表外のカタカナ {len(offenders)} 件 —— 原語で引き直すこと:")
    for o in offenders:
        print(f"  行 {o['n']}: {o['term']}")
    return 1


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--grc":
        lookup(sys.argv[2])
        raise SystemExit(0)
    if len(sys.argv) > 2 and sys.argv[1] == "--check":
        raise SystemExit(check(sys.argv[2]))
    raise SystemExit(main(int(sys.argv[1])))
