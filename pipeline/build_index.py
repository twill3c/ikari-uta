"""対訳表の名を、原文の中で探して出現行の索引を作る。

**なぜ原文側で探すか。** 訳文から拾うのは循環する —— 私が書いた訳を私が数えるだけになる。
底本のギリシア語の中で語幹を探せば、鍵は私の作ったものではない。

**語形変化があるので、完全一致では引けない。** 名は格変化する
(Ἀχιλλεύς / Ἀχιλῆος / Ἀχιλῆϊ / Ἀχιλλῆα)。そこで気息・アクセントを落として
正規化し、主格語尾を剥いだ語幹で探す。**これは近似であり、当たり外れがある。**
だから同梱の measure で英訳を独立の証人として突き合わせ、精度を実測する。

**この道具に原理的にできないこと。** 同名異人は文字列では分けられない。
第16巻には三人のクサントス(川・人・馬)がいて、綴りは同じである。
索引はそれを一つにまとめてしまう —— 隠さず、そう表示する。
"""
from __future__ import annotations

import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 主格語尾。長いものから順に剥ぐ。剥いだ後が短くなりすぎる場合は剥がない。
# 主格だけでなく複数形の語尾も剥ぐ。剥がないと Δαναοί が「δαναοι」のまま残り、
# Δανάη の語幹「δανα」に Δαναῶν が吸われて**別人に付く**(実際そうなった)。
# 同じ語幹に落ちるなら、それは**綴りでは分けられない**という事実であり、
# 誤って一方に付けるより、まとめて曖昧と表示するほうが正しい。
ENDINGS = [
    "ειας", "οισι", "ιος", "ευς", "εια", "ηες", "οις", "ους", "ων", "οι",
    "ος", "ης", "ας", "ες", "ις", "υς", "ον", "αι", "η", "α", "ω",
]
MIN_STEM = 4

# **語幹が規則的でない見出し。** ギリシア語には主格と斜格で語幹が変わる名がある。
# Ζεύς の属格・与格・対格は Διός / Διί / Δία で、主格からは辿れない。
# ここに書かない限り、それらの出現は綴りの似た別の名に付く —— 実際、
# 一覧の小さな町 Δῖον が Zeus の斜格 259 箇所を丸ごとさらっていた。
IRREGULAR = {
    "Ζεύς": ["δι"],
}


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", s).lower()


def stem_of(grc: str) -> str | None:
    """対訳表の見出しから、探索用の語幹を作る。

    以前は語幹が MIN_STEM に満たない見出しを **None にして黙って落としていた**。
    その結果 Ἥρη(ヘーラー)をはじめ 12 の見出しが索引から丸ごと消え、
    さらに悪いことに、その出現を綴りの似た長い名が横取りしていた
    (Ἄργος の語幹が作れず、ἄργεος が Ἀργεάς に付いていた)。
    今は短い語幹も返し、代わりに **当てる語の長さに上限**を課す(max_len 参照)。
    """
    base = strip_accents(re.sub(r"[((].*?[))]", "", grc)).strip()
    if not base:
        return None
    for e in ENDINGS:
        if base.endswith(e) and len(base) - len(e) >= 2:
            return base[: -len(e)]
    return base or None


def max_len(stem: str) -> int:
    """その語幹で当てて良い語の最大長。

    語幹が短いほど、無関係な語を巻き込む危険が大きい。
    ギリシア語の格変化は語尾を数文字伸ばす程度なので、そこで切る。
    """
    return len(stem) + (3 if len(stem) < MIN_STEM else 6)


def load_glossary() -> list[dict]:
    out = []
    for name in ("glossary.json", "glossary.catalogue.json"):
        p = ROOT / "data" / name
        if p.exists():
            out.extend(json.loads(p.read_text(encoding="utf-8"))["entries"])
    return out


WORD = re.compile(r"[Ͱ-Ͽἀ-ῼ]+")


def capitalized_words(grc: str) -> list[str]:
    """行の中の**大文字で始まる語**だけを、正規化して返す。

    底本は固有名詞を大文字で始める。これを使わずに語幹だけで探すと、
    Ἐπειός の語幹 επει が ἐπεὶ(「〜のとき」)に当たって 704 箇所という
    でたらめな数になる —— 実際に最初の版がそうなった。
    Χείρων は χείρ(手)に、Πρωτώ は πρῶτος(第一の)に当たっていた。
    """
    out = []
    for w in WORD.findall(grc):
        first = unicodedata.normalize("NFD", w[0])[0]
        if first.isupper():
            out.append(strip_accents(w))
    return out


def load_lines() -> list[tuple[int, int, list[str]]]:
    rows = []
    for f in sorted((ROOT / "data" / "canonical").glob("book-*.json")):
        b = int(f.stem[-2:])
        for l in json.loads(f.read_text(encoding="utf-8"))["lines"]:
            rows.append((b, l["n"], capitalized_words(l["grc"])))
    return rows


def build() -> dict:
    """各見出しについて、語幹が現れる (巻, 行) を集める。"""
    entries = load_glossary()
    lines = load_lines()

    # 同じ語幹を持つ見出しは、文字列では分けられない。まとめて記録する。
    by_stem: dict[str, list[dict]] = {}
    for e in entries:
        for s in [stem_of(e["grc"])] + IRREGULAR.get(e["grc"], []):
            if s:
                by_stem.setdefault(s, []).append(e)

    # 長い語幹から先に当てる(Ἀχιλλ が Ἀχ に呑まれないように)
    stems = sorted(by_stem, key=len, reverse=True)
    hits: dict[str, list[tuple[int, int]]] = {s: [] for s in stems}
    # 語幹は語の**先頭**に一致させる。ギリシア語の格変化は語尾を変えるので、
    # 部分一致ではなく前方一致が正しい。
    for b, n, words in lines:
        for w in words:
            for s in stems:
                if w.startswith(s) and len(w) <= max_len(s):
                    hits[s].append((b, n))
                    break          # 最長の語幹ひとつだけに数える

    out = []
    for s in stems:
        occ = hits[s]
        if not occ:
            continue
        group = by_stem[s]
        out.append({
            "stem": s,
            "entries": group,
            "occurrences": occ,
            "count": len(occ),
            "ambiguous": len(group) > 1,
        })
    return {"groups": sorted(out, key=lambda g: -g["count"])}


def main() -> int:
    idx = build()
    total = sum(g["count"] for g in idx["groups"])
    amb = [g for g in idx["groups"] if g["ambiguous"]]
    print(f"見出し群 {len(idx['groups'])} / 出現 {total:,} 箇所")
    print(f"うち**同じ語幹に複数の見出しが乗る群**: {len(amb)}(文字列では分けられない)")
    print("\n上位 12:")
    for g in idx["groups"][:12]:
        names = " / ".join(e["ja"] for e in g["entries"])
        print(f"  {g['count']:>5}  {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------- 精度の実測

def _english_segments() -> dict[int, list[tuple[int, str]]]:
    out: dict[int, list[tuple[int, str]]] = {}
    for f in sorted((ROOT / "data" / "english").glob("book-*.json")):
        b = int(f.stem[-2:])
        out[b] = sorted((s["from_line"], s["text"]) for s in
                        json.loads(f.read_text(encoding="utf-8"))["segments"])
    return out


def _segment_for(segs: list[tuple[int, str]], n: int) -> str:
    """行 n を含む英訳の段落。英訳は行単位ではなく段落単位に付く。"""
    prev = ""
    for start, text in segs:
        if start > n:
            break
        prev = text
    return prev


def measure(sample_per_group: int = 3) -> dict:
    """**英訳を独立の証人にして、当たりを検算する。**

    語幹の前方一致は近似である。当たったと言う (巻, 行) について、
    その行を含む英訳の段落に、対訳表の英語見出しが現れるかを見る。
    英訳は私が書いたものではないので、この突き合わせは循環しない。

    段落は複数行にまたがるので、これは**行単位の正解ではない**。
    「近くに出るはず」という緩い検算であり、そう扱う。
    """
    idx = build()
    segs = _english_segments()
    ok = miss = 0
    misses: list[dict] = []
    for g in idx["groups"]:
        engs = [e["eng"].lower() for e in g["entries"]]
        for b, n in g["occurrences"][:sample_per_group]:
            text = _segment_for(segs.get(b, []), n).lower()
            # 英語見出しも語形が変わる(Achilles / Achilles'）ので前方 5 文字で見る
            if any(e[:5] and e[:5] in text for e in engs):
                ok += 1
            else:
                miss += 1
                if len(misses) < 25:
                    misses.append({"ja": g["entries"][0]["ja"], "eng": engs[0],
                                   "book": b, "n": n})
    return {"ok": ok, "miss": miss, "misses": misses,
            "rate": ok / (ok + miss) if ok + miss else 0.0}


def unregistered() -> list[tuple[str, int]]:
    """**どの見出しにも当たらなかった、大文字始まりの語。** 未登録の名の候補。"""
    entries = load_glossary()
    stems = sorted({s for s in (stem_of(e["grc"]) for e in entries) if s},
                   key=len, reverse=True)
    counts: dict[str, int] = {}
    for _, _, words in load_lines():
        for w in words:
            if not any(w.startswith(s) for s in stems):
                counts[w] = counts.get(w, 0) + 1
    return sorted(counts.items(), key=lambda x: -x[1])


# ---------------------------------------------------------------- 出荷用の整形

KIND_PAGE = {
    "god": "people", "hero": "people", "horse": "people",
    "place": "places", "people": "places",
}


def to_records() -> dict[str, list[dict]]:
    """索引を、見出しごとの一覧に畳む。

    同じ語幹に複数の見出しが乗る群は、**分けられないという事実を持ったまま**
    それぞれの見出しに同じ出現を配る。数を二重に見せないため、
    表示側では「綴りでは分けられない」と明示する。
    """
    idx = build()
    recs: dict[str, dict] = {}
    for g in idx["groups"]:
        # **原語で数える。** 和名で比べると、同じカタカナを持つ見出しどうし
        # (三人のクサントス)が「自分自身」として除かれ、
        # まさに示すべき曖昧さが画面から消える —— 実際そうなった。
        others = [(e["grc"], e["ja"]) for e in g["entries"]]
        for e in g["entries"]:
            # 同じ存在の別の原語形(Ἀθηναίη は Ἀθήνη の異形)は一つに畳む。
            # 畳まないと、画面に「アテーネー」が二度並び、出現も分かれて見える。
            key = e.get("variant_of") or e["grc"]
            r = recs.setdefault(key, {
                "grc": key, "ja": e["ja"], "eng": e["eng"],
                "kind": e["kind"], "camp": e.get("camp"), "note": e.get("note"),
                "occ": [], "shared_with": [],
            })
            r["occ"].extend(g["occurrences"])
            if g["ambiguous"]:
                r["shared_with"] = [
                    f"{ja}({grc})" for grc, ja in others if grc != e["grc"]
                ]
    pages: dict[str, list[dict]] = {"people": [], "places": []}
    for r in recs.values():
        r["occ"] = sorted(set(map(tuple, r["occ"])))
        r["count"] = len(r["occ"])
        if r["count"]:
            pages[KIND_PAGE.get(r["kind"], "places")].append(r)
    for k in pages:
        pages[k].sort(key=lambda r: (-r["count"], r["ja"]))
    return pages
