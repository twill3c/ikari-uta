"""和訳データの検査(G-03 表記ゆれ / G-04 字種)。

**訳の良し悪しは検査しない。** ここが見るのは「表記が揺れていないか」「別字種が混ざっていないか」
だけである(SPEC §1)。

字種検査は日本語本文にのみ当てる。原文フィールドのギリシャ文字は正常であり、
そこへ当てると誤検出になる(HC-074 陰性対照)。
"""

from __future__ import annotations

import re
import unicodedata

# 字種の範囲。範囲を禁ずる検査は、誤検出 0 を陰性対照で先に確かめること(HC-074)。
_RANGES: tuple[tuple[str, int, int], ...] = (
    ("cyrillic", 0x0400, 0x04FF),
    ("cyrillic", 0x0500, 0x052F),
    ("greek", 0x0370, 0x03FF),
    ("greek", 0x1F00, 0x1FFF),
    ("hangul", 0x1100, 0x11FF),
    ("hangul", 0x3130, 0x318F),
    ("hangul", 0xAC00, 0xD7AF),
)

# カタカナの連なり(長音・中黒を含む)を固有名詞の候補とする。
_KATAKANA_RUN = re.compile(r"[ァ-ヺーヽヾ・]{2,}")


def _kind_of(ch: str) -> str | None:
    cp = ord(ch)
    for kind, lo, hi in _RANGES:
        if lo <= cp <= hi:
            return kind
    cat = unicodedata.category(ch)
    if cat == "Cc" and ch not in "\n\t":
        return "control"
    if cat == "Cf":
        return "control"
    return None


def charset_violations(ja_books: dict) -> list[dict]:
    """訳文フィールドに現れてはならない字種を列挙する。"""
    out: list[dict] = []
    for book, data in sorted(ja_books.items()):
        for ln in data["lines"]:
            text = ln.get("ja") or ""
            for ch in text:
                kind = _kind_of(ch)
                if kind:
                    out.append(
                        {
                            "book": book,
                            "n": ln["n"],
                            "kind": kind,
                            "char": ch,
                            "codepoint": f"U+{ord(ch):04X}",
                        }
                    )
    return out


def glossary_terms(glossary: dict) -> set[str]:
    """対訳表が認めるカタカナ表記の全体(名前 + 別表記 + 非固有名詞の許可語)。"""
    terms: set[str] = set()
    for e in glossary.get("entries", []):
        if e.get("ja"):
            terms.add(e["ja"])
        for alt in e.get("ja_alt", []):
            terms.add(alt)
    terms.update(glossary.get("allow_katakana", []))
    return terms


def proper_nouns_outside_glossary(ja_books: dict, glossary: dict) -> list[dict]:
    """訳文のカタカナ連鎖のうち、対訳表に載っていないものを列挙する。

    表に載る語を長いものから順に取り除き、残ったカタカナ連鎖を違反とする。
    「アキレウス」が表に在れば、それを含む行から先に消えるので、
    残るのは表が知らない語だけになる。
    """
    known = sorted(glossary_terms(glossary), key=len, reverse=True)
    out: list[dict] = []
    for book, data in sorted(ja_books.items()):
        for ln in data["lines"]:
            text = ln.get("ja") or ""
            for term in known:
                if term in text:
                    text = text.replace(term, "　")
            for m in _KATAKANA_RUN.finditer(text):
                out.append({"book": book, "n": ln["n"], "term": m.group(0)})
    return out
