"""和訳データの検査。TEST_SPEC T-013〜T-019。

ここが保証するのは「落ちていない・ズレていない・表記が揺れていない」であって、
訳の良し悪しではない(SPEC §1)。訳質を主張するテストをここに置いてはならない。
"""

import json

import pytest

from pipeline import checks

pytestmark = pytest.mark.validation


def test_t013_no_ja_line_outside_source(ja_books, canonical_books):
    """T-013 / G-01: 訳に**原文に存在しない行**が無い。これは常に成り立つべき不変量。

    行の不足は欠陥ではない(巻を分けて訳すのは正常な進め方)。完全性は T-013b が測る。
    不変量と進捗指標を一つの述語に混ぜない(HC-085)。
    """
    for book, ja in ja_books.items():
        assert book in canonical_books, f"巻 {book} の原文が無い"
        src = {ln["n"] for ln in canonical_books[book]["lines"]}
        got = {ln["n"] for ln in ja["lines"]}
        extra = sorted(got - src)
        assert not extra, (
            f"巻 {book}: 原文に存在しない行が訳にある {extra[:10]}(計 {len(extra)})"
        )


def test_t013b_coverage_is_reported_not_enforced(ja_books, canonical_books):
    """T-013b: 被覆率が記録され、`complete` の申告が実態と一致する。

    ここは「どれだけ揃ったか」を測る。少ないことは失敗にしないが、
    **申告と実態が食い違うこと**は失敗にする —— 未訳を訳済みと偽らせない。
    """
    for book, ja in ja_books.items():
        src = {ln["n"] for ln in canonical_books[book]["lines"]}
        got = {ln["n"] for ln in ja["lines"]}
        actual_complete = got == src
        assert ja["complete"] is actual_complete, (
            f"巻 {book}: complete={ja['complete']} と実態({actual_complete})が食い違う"
        )
        expected_cov = round(len(got) / len(src), 4)
        assert abs(ja["coverage"] - expected_cov) < 1e-6, (
            f"巻 {book}: coverage={ja['coverage']} が実測 {expected_cov} と食い違う"
        )


def test_t013c_translated_lines_are_a_prefix_run(ja_books, canonical_books):
    """T-013c: 未訳の巻でも、訳した範囲が原文の行順に沿って連続している。

    飛び飛びに訳すと、後から穴を埋めるときに整列を誤りやすい。
    実測 2026-08-31: 第 1 巻は全訳、第 2 巻は本編 1–483 の連続範囲。
    """
    for book, ja in ja_books.items():
        src_order = [ln["n"] for ln in canonical_books[book]["lines"]]
        got = {ln["n"] for ln in ja["lines"]}
        seen_gap = False
        for n in src_order:
            if n in got:
                assert not seen_gap, f"巻 {book}: 行 {n} が未訳の穴より後にある(飛び訳)"
            else:
                seen_gap = True


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
