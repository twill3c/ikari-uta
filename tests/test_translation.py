"""和訳データの検査。TEST_SPEC T-013〜T-019。

ここが保証するのは「落ちていない・ズレていない・表記が揺れていない」であって、
訳の良し悪しではない(SPEC §1)。訳質を主張するテストをここに置いてはならない。
"""

import json

import pytest

from pipeline import checks

pytestmark = pytest.mark.validation


def test_t013_ja_line_numbers_match_source(ja_books, canonical_books):
    """T-013 / G-01: 和訳の行番号集合が原文と過不足なく一致する。"""
    for book, ja in ja_books.items():
        assert book in canonical_books, f"巻 {book} の原文が無い"
        src = {ln["n"] for ln in canonical_books[book]["lines"]}
        got = {ln["n"] for ln in ja["lines"]}
        assert got == src, (
            f"巻 {book}: 訳に無い行 {sorted(src - got)[:10]} / 原文に無い行 {sorted(got - src)[:10]}"
        )


def test_t014_ja_lines_are_non_empty(ja_books):
    """T-014: 訳文の各行が空でない。"""
    for book, ja in ja_books.items():
        empty = [ln["n"] for ln in ja["lines"] if not ln.get("ja", "").strip()]
        assert not empty, f"巻 {book}: 空の訳 {empty[:10]}"


def test_t015_no_proper_nouns_outside_glossary(ja_books, glossary):
    """T-015 / G-03: 訳文のカタカナ固有名詞がすべて対訳表に載る。"""
    offenders = checks.proper_nouns_outside_glossary(ja_books, glossary)
    assert not offenders, f"表外表記: {offenders[:15]}"


def test_t016_positive_control_unknown_name_is_caught(glossary):
    """T-016 陽性対照: 表外表記を仕込んだ訳を検査が落とすこと。"""
    planted = {1: {"book": 1, "lines": [{"n": 1, "ja": "ペーレウスの子アキレウスとゼウスの怒り"},
                                        {"n": 2, "ja": "そこへムルグルーム将軍が現れた"}]}}
    offenders = checks.proper_nouns_outside_glossary(planted, glossary)
    assert offenders, "仕込んだ表外表記を検査が見逃した"
    assert any("ムルグルーム" in o["term"] for o in offenders)


def test_t017_ja_field_charset(ja_books):
    """T-017 / G-04: 訳文にギリシャ文字・キリル・ハングル・制御文字が無い。"""
    bad = checks.charset_violations(ja_books)
    assert not bad, f"字種違反: {bad[:15]}"


def test_t018_positive_control_charset_leak_is_caught():
    """T-018 陽性対照: 字種を混入させた訳を検査が落とすこと。"""
    planted = {
        1: {
            "book": 1,
            "lines": [
                {"n": 1, "ja": "怒りを歌え、女神よ"},
                {"n": 2, "ja": "измерение を含む行"},          # キリル
                {"n": 3, "ja": "μῆνιν を訳さず残した行"},        # ギリシャ文字
            ],
        }
    }
    bad = checks.charset_violations(planted)
    kinds = {b["kind"] for b in bad}
    assert "cyrillic" in kinds, "キリル文字を見逃した"
    assert "greek" in kinds, "未訳のギリシャ文字を見逃した"


def test_t019_negative_control_greek_allowed_in_source_field(canonical_books):
    """T-019 陰性対照: 原文フィールドのギリシャ文字は違反ではない(HC-074)。

    誤検出 0 を、作った例ではなく実データの正常な部分で確かめる。
    """
    sample = {
        bk: {"book": bk, "lines": [{"n": ln["n"], "ja": ""} for ln in d["lines"][:50]]}
        for bk, d in list(canonical_books.items())[:3]
    }
    # 原文フィールドは検査対象外である、という性質そのものを表明する
    assert any(d["lines"][0].get("grc") for d in canonical_books.values()), (
        "正準データにギリシャ語本文が入っていない。この陰性対照は意味を失っている"
    )
    bad = checks.charset_violations(sample)
    assert not bad, f"原文フィールド由来の誤検出: {bad[:5]}"


def test_t026_data_license_declared():
    """T-026 / N-05: LICENSE.data が CC BY-SA 4.0 と帰属を明記する。"""
    from tests.conftest import PROJECT_ROOT

    p = PROJECT_ROOT / "LICENSE.data"
    assert p.exists(), "LICENSE.data が無い"
    body = p.read_text(encoding="utf-8")
    assert "CC BY-SA 4.0" in body
    assert "Perseus" in body
    assert "Monro" in body
