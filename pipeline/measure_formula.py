"""同じギリシア語の行が、同じ和訳になっているかを測る(定型句の揺れ)。

**なぜ要るか。** 対訳表の凍結は固有名詞しか守らない。だが叙事詩の本文は
定型句でできており、同じ行が巻をまたいで何度も現れる。そこが揺れても
既存の検査は何も言わない —— 実際 loop_018/019/020 で「橄欖/オリーブ」
「油/オリーブ油」「番紅花/サフラン」と三度続けて割れ、三度とも
`measure_names --check` が**たまたまカタカナだったから**捕まえただけだった。

**この道具は非循環である。** 突き合わせるのは訳文どうしではなく、
「底本で同一の行」という原文側の事実を鍵にする。鍵は私が作っていない。

    python pipeline/measure_formula.py            # 全体の集計
    python pipeline/measure_formula.py 19         # その巻に関わる割れだけ
    python pipeline/measure_formula.py --list     # 割れている組を全部出す
"""
from __future__ import annotations

import collections
import difflib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 語りの中の引用では敬体になる(第1巻 374-379 行など)。これは意図した差なので、
# 揺れとして数えない。句読点の違いも同様に落とす。
POLITE = [("ました", "た"), ("ません", "ない"), ("ましょう", "よう"),
          ("でした", "だった"), ("ます", "る"), ("です", "だ")]


def normalize(s: str) -> str:
    s = re.sub(r"[、。「」『』・\s]", "", s)
    for a, b in POLITE:
        s = s.replace(a, b)
    return s


def load() -> tuple[dict[str, list[tuple[int, int]]], dict[tuple[int, int], str]]:
    grc: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    for f in sorted((ROOT / "data" / "canonical").glob("book-*.json")):
        b = int(f.stem[-2:])
        for l in json.loads(f.read_text(encoding="utf-8"))["lines"]:
            grc[l["grc"].strip()].append((b, l["n"]))
    ja: dict[tuple[int, int], str] = {}
    for p in sorted((ROOT / "data" / "ja").glob("book-*.json")):
        b = int(p.stem[-2:])
        for l in json.loads(p.read_text(encoding="utf-8"))["lines"]:
            if l.get("ja"):
                ja[(b, l["n"])] = l["ja"].strip()
    return grc, ja


def divergences() -> list[tuple[str, list[tuple[tuple[int, int], str]]]]:
    """同一の原文行に、正規化しても異なる訳が当たっている組。"""
    grc, ja = load()
    out = []
    for g, locs in grc.items():
        have = [k for k in locs if k in ja]
        if len(have) < 2:
            continue
        if len({normalize(ja[k]) for k in have}) > 1:
            out.append((g, [(k, ja[k]) for k in have]))
    return sorted(out, key=lambda x: x[1][0][0])


def existing(book: int) -> dict[int, str]:
    """これから訳す巻の各行のうち、**同じ原文行がすでに他巻で訳されている**ものを返す。

    T-032 は出荷前に揺れを捕まえるが、捕まえてから直すより、
    書く前に既訳を手元に置くほうが速い。同じ道具を、門ではなく地図として使う。

    **そのまま貼ってはならない。** 底本で同一の行でも、前後の構文枠が違えば
    日本語の語尾は変わる(第20巻78行と第22巻267行は同じ行だが、
    一方は「命じていた」の目的語、一方は「〜するまでは」の内容だった)。
    枠に依らない形に両方を書き直すのが正しい直し方で、片方を写すことではない。
    """
    grc, ja = load()
    target = {}
    for g, locs in grc.items():
        here = [n for b, n in locs if b == book]
        if not here:
            continue
        others = [(b, n) for b, n in locs if b != book and (b, n) in ja]
        if not others:
            continue
        vals = {normalize(ja[k]) for k in others}
        if len(vals) != 1:          # 既訳どうしが割れている行は、勝手に選ばない
            continue
        for n in here:
            target[n] = ja[others[0]]
    return dict(sorted(target.items()))


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "--existing":
        rows = existing(int(argv[1]))
        for n, v in rows.items():
            print(f"{n}	{v}")
        print(f"\n# 既訳のある行 {len(rows)} 本(第 {argv[1]} 巻)")
        return 0

    div = divergences()
    if "--list" in argv or (argv and argv[0].isdigit()):
        book = int(argv[0]) if argv and argv[0].isdigit() else None
        shown = [d for d in div if book is None or any(k[0] == book for k, _ in d[1])]
        for g, occ in shown:
            print(f"\n原文: {g}")
            for (b, n), v in occ:
                print(f"  {b:>2}巻 {n:>4}行: {v}")
        print(f"\n{len(shown)} 組" + (f"(第 {book} 巻に関わるもの)" if book else ""))
        return 0

    buckets: collections.Counter[str] = collections.Counter()
    for _, occ in div:
        vals = sorted({normalize(v) for _, v in occ})
        r = difflib.SequenceMatcher(None, vals[0], vals[1]).ratio()
        buckets["ほぼ同一 (>=0.9)" if r >= 0.9 else
                "近い (0.7-0.9)" if r >= 0.7 else "大きく違う (<0.7)"] += 1
    print(f"同一の原文行に異なる訳が当たっている組: {len(div)}")
    for k in ("ほぼ同一 (>=0.9)", "近い (0.7-0.9)", "大きく違う (<0.7)"):
        print(f"  {k}: {buckets[k]}")
    print("\n※ 敬体(引用中の語り)と句読点の差は落としてある。")
    print("※ この数は**据え置きの実測値**であり、直す対象ではなく増やさない対象。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
