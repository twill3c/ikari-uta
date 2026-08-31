"""軍船の一覧から組んだ名簿の検査(F-12)。TEST_SPEC T-033〜T-036。

**隻数の合計は検算であって前提ではない。** 名簿を一件ずつ確かめて組み、
その結果として合計が外部権威と一致した。逆順にすると、合わせるための解釈を選んでしまう。
"""

import json

import pytest

from tests.conftest import PROJECT_ROOT

pytestmark = pytest.mark.validation

ROSTER = PROJECT_ROOT / "data" / "roster.json"
CATALOGUE_RANGE = (484, 759)          # アカイア側の一覧
EXTERNAL_SHIP_TOTAL = 1186            # 外部権威。イーリアス軍船目録の通説


def _roster() -> dict:
    if not ROSTER.exists():
        pytest.skip("名簿が未生成")
    return json.loads(ROSTER.read_text(encoding="utf-8"))


def test_t033_ship_total_matches_external_authority():
    """T-033: 隻数の合計が通説 1,186 と一致する(独立した錨との突合)。"""
    r = _roster()
    total = sum(c["ships"] for c in r["contingents"])
    assert total == r["ship_total"], "宣言した合計と明細の合計が食い違う"
    assert total == EXTERNAL_SHIP_TOTAL, (
        f"隻数合計 {total} が通説 {EXTERNAL_SHIP_TOTAL} と一致しない。"
        "一致させにいくのではなく、食い違う部隊を列挙して理由を書くこと"
    )


def test_t034_every_contingent_cites_real_lines(canonical_books):
    """T-034: 全部隊の行範囲と隻数の出典行が、第 2 巻に実在する行を指す。"""
    r = _roster()
    present = {ln["n"] for ln in canonical_books[2]["lines"]}
    lo, hi = CATALOGUE_RANGE
    for c in r["contingents"]:
        for key in ("from_line", "to_line", "ship_line"):
            n = c[key]
            assert n in present, f"{c['region']}: 行 {n} が第 2 巻に無い"
            assert lo <= n <= hi, f"{c['region']}: 行 {n} が一覧の範囲外"
        assert c["from_line"] <= c["ship_line"] <= c["to_line"], (
            f"{c['region']}: 隻数の出典行が部隊の行範囲の外にある"
        )


def test_t035_contingents_do_not_overlap_and_run_in_order():
    """T-035: 部隊の行範囲が重ならず、本文の順に並ぶ。"""
    r = _roster()
    spans = [(c["from_line"], c["to_line"], c["region"]) for c in r["contingents"]]
    for (a1, b1, n1), (a2, _, n2) in zip(spans, spans[1:]):
        assert b1 < a2, f"{n1} と {n2} の行範囲が重なる、または順序が逆"


def test_t036_every_contingent_has_a_named_leader():
    """T-036: 全部隊が名を持つ将を少なくとも一人挙げている。"""
    r = _roster()
    empty = [c["region"] for c in r["contingents"] if not c.get("leaders")]
    assert not empty, f"将が挙がっていない部隊: {empty}"


def test_t037_positive_control_a_wrong_count_is_caught():
    """T-037 陽性対照: 隻数を一つ書き換えた名簿を、合計検査が落とすこと。

    これが落ちないなら T-033 は何も検算していない。
    """
    r = _roster()
    tampered = [dict(c) for c in r["contingents"]]
    tampered[0]["ships"] += 1
    assert sum(c["ships"] for c in tampered) != EXTERNAL_SHIP_TOTAL, (
        "隻数を改竄しても合計が変わらない。この検算は働いていない"
    )
