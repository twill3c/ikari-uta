"""英訳抽出器の検査(HC-082 の回帰ガード)。

要点は**フィクスチャが混合内容を含むこと**である。単一要素だけのフィクスチャでは、
区切りを入れない実装も入れる実装も同じ出力を返し、陽性対照が発火しない。
"""

import re
from xml.etree import ElementTree as ET

import pytest

from pipeline import parse_english

pytestmark = pytest.mark.unit

TEI = "http://www.tei-c.org/ns/1.0"

# 混合内容: milestone が本文の途中に挟まる。実データと同じ形(SPEC §3.1)。
MIXED = f"""<div xmlns="{TEI}" type="textpart" subtype="book" n="1">
 <p><milestone unit="line" n="1"/>the wrath of Achilles<milestone unit="line" n="5"/>one
 that the son of Priam<milestone unit="line" n="10"/>rejoiced in the sign</p>
</div>"""

# 陰性対照: 混合内容を含まない。ここでは両実装が同じ出力を返す(＝対照として無効)。
FLAT = f"""<div xmlns="{TEI}" type="textpart" subtype="book" n="1">
 <p><milestone unit="line" n="1"/>the wrath of Achilles</p>
</div>"""


def _naive_segments(div: ET.Element) -> str:
    """HC-082 で壊れていた実装。要素境界に区切りを入れない。"""
    return re.sub(r"\s+", " ", "".join(div.itertext())).strip()


def _fixed_text(div: ET.Element) -> str:
    return " ".join(s["text"] for s in parse_english.book_segments(div))


def test_fixture_actually_contains_mixed_content():
    """この対照が意味を持つ前提の表明: フィクスチャが混合内容であること(HC-070)。"""
    div = ET.fromstring(MIXED)
    ps = list(div.iter(f"{{{TEI}}}p"))
    assert ps, "p が無い"
    inline = [c for p in ps for c in p if c.tail and c.tail.strip()]
    assert inline, "本文の途中に要素が挟まっていない。このフィクスチャでは対照が発火しない"


def test_positive_control_naive_join_concatenates_words():
    """陽性対照: 区切りを入れない実装は語を結合させる。"""
    div = ET.fromstring(MIXED)
    naive = _naive_segments(div)
    assert "Achillesone" in naive, (
        "壊れた実装が語を結合していない。この対照は何も捕まえていない"
    )


def test_fixed_extractor_does_not_concatenate():
    """本実装は語を結合させない。"""
    div = ET.fromstring(MIXED)
    fixed = _fixed_text(div)
    assert "Achillesone" not in fixed
    assert "Priamrejoiced" not in fixed
    for word in ("Achilles", "one", "Priam", "rejoiced"):
        assert re.search(rf"\b{word}\b", fixed), f"{word} が語として現れない: {fixed}"


def test_negative_control_flat_fixture_cannot_discriminate():
    """陰性対照: 混合内容が無ければ両実装は一致する。

    これが一致することを示しておかないと、上の陽性対照が
    「混合内容だから捕まえた」のか「たまたま」なのかが言えない。
    """
    div = ET.fromstring(FLAT)
    assert _naive_segments(div) == _fixed_text(div)


def test_declared_anchor_exception_actually_exists(raw_eng):
    """除外リストに挙げた異常が実データに実在すること(緩みすぎ防止)。

    底本が直れば、この表明が落ちて「除外はもう要らない」と教えてくれる。
    """
    books = {b["book"]: b for b in parse_english.parse_books(raw_eng)}
    for book, x, y in parse_english.KNOWN_ANCHOR_REGRESSIONS:
        anchors = [s["from_line"] for s in books[book]["segments"]]
        pairs = list(zip(anchors, anchors[1:]))
        assert (x, y) in pairs, (
            f"巻 {book} の宣言済み例外 {x}→{y} が実データに無い。除外を外せる"
        )


def test_duplicate_anchors_match_measurement(raw_eng):
    """同値アンカーの集合が実測(2026-08-31)と一致する。母集団ごとに別に測る。

    生の milestone では 2 件、区間では 1 件。第 20 巻は milestone n="1" が
    間に文字を挟まず 2 回続き、前者が空区間として捨てられるため。
    **どちらの数も正しい。** 母集団を言わずに定数を置くと正しい実装が落ちる(HC-040)。
    """
    # 母集団 1: 生の milestone
    root = ET.parse(str(raw_eng)).getroot()
    raw_dups = set()
    for div in root.iter(f"{{{TEI}}}div"):
        if (div.get("subtype") or "").lower() != "book":
            continue
        ns = [
            int(m.get("n"))
            for m in div.iter(f"{{{TEI}}}milestone")
            if m.get("unit") == "line" and (m.get("n") or "").isdigit()
        ]
        raw_dups |= {(int(div.get("n")), x) for x, y in zip(ns, ns[1:]) if x == y}
    assert raw_dups == set(parse_english.MEASURED_DUPLICATE_ANCHORS_RAW), (
        f"生 milestone の同値が実測と食い違う: {sorted(raw_dups)}"
    )

    # 母集団 2: 区間
    seg_dups = set()
    for b in parse_english.parse_books(raw_eng):
        ns = [s["from_line"] for s in b["segments"]]
        seg_dups |= {(b["book"], x) for x, y in zip(ns, ns[1:]) if x == y}
    assert seg_dups == set(parse_english.MEASURED_DUPLICATE_ANCHORS_SEGMENTS), (
        f"区間の同値が実測と食い違う: {sorted(seg_dups)}"
    )

    # 差は「空区間が落ちた分」でちょうど説明がつくこと
    assert raw_dups - seg_dups == {(20, 1)}


def test_undeclared_anchor_regression_still_raises(raw_eng):
    """陽性対照: 宣言していない逆行は今も例外になること。

    除外の仕掛けが検査そのものを骨抜きにしていないかを確かめる。
    """
    div = ET.fromstring(
        f"""<div xmlns="{TEI}" type="textpart" subtype="book" n="1">
 <p><milestone unit="line" n="10"/>alpha<milestone unit="line" n="5"/>beta</p>
</div>"""
    )
    segs = parse_english.book_segments(div)
    anchors = [s["from_line"] for s in segs]
    regressions = [
        (1, x, y)
        for x, y in zip(anchors, anchors[1:])
        if y <= x and (1, x, y) not in parse_english.KNOWN_ANCHOR_REGRESSIONS
    ]
    assert regressions, "宣言外の逆行が検出されない。除外が広すぎる"


def test_anchor_resolution_is_five_lines(raw_eng):
    """実データの行アンカー間隔。SPEC §3.1 の実測値(2026-08-31)を回帰で押さえる。"""
    books = parse_english.parse_books(raw_eng)
    gaps = []
    for b in books:
        ns = [s["from_line"] for s in b["segments"]]
        gaps += [y - x for x, y in zip(ns, ns[1:])]
    assert gaps, "アンカーが取れていない"
    assert max(gaps) <= 15, f"アンカー間隔が実測(最大 15)を超えた: {max(gaps)}"
    five = sum(1 for g in gaps if g == 5)
    assert five / len(gaps) > 0.9, f"間隔 5 の割合が実測(0.98)から外れた: {five}/{len(gaps)}"


def test_no_concatenation_in_real_data(raw_eng):
    """実データ全域: 既知 2 語の連結でしか説明できない綴りが無いこと(HC-082)。"""
    books = parse_english.parse_books(raw_eng)
    vocab = set()
    for b in books:
        for seg in b["segments"]:
            vocab.update(w.lower() for w in re.findall(r"[A-Za-z]+", seg["text"]))
    suspects = parse_english.concatenation_suspects(books, vocab)
    assert not suspects, f"語の連結が疑われる綴り: {suspects[:20]}"
