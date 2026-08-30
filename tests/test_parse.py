"""経路 A(DOM)と経路 B(走査)の二経路照合。TEST_SPEC T-003〜T-012。

このファイルの期待値の出所:
- 「24 巻」「15,687」「15,693」「欠番 6 行」は 2026-08-31 に底本 XML を開いて実測した値
  (SPEC §3.1 に記録)。実測日と実測値をここに残す(HC-016)。
- 15,693 は「イーリアスの行数」として広く流通する外部権威由来の数字でもある。
  本プロジェクトはこれを **行番号最大値の和** として解釈できることを実測で示した。
"""

import pytest

from pipeline import line_oracle, parse_tei

pytestmark = pytest.mark.unit

# --- 実測値(2026-08-31、底本 tlg0012.tlg001.perseus-grc2.xml)-------------------
MEASURED_BOOKS = 24
MEASURED_EXTANT_LINES = 15687          # 実在する <l> 要素
EXTERNAL_SUM_OF_MAXIMA = 15693         # 外部権威と一致する値(= 各巻の行番号最大値の和)
MEASURED_MISSING = {9: [458, 459, 460, 461], 11: [543], 14: [269]}


def test_t003_dom_path_parses_books(raw_grc):
    """T-003: 経路 A が 24 巻を返し、全行が数値の行番号を持つ。"""
    books = parse_tei.parse_books(raw_grc)
    assert len(books) == MEASURED_BOOKS
    for b in books:
        assert b["lines"], f"巻 {b['book']} が空"
        for ln in b["lines"]:
            assert isinstance(ln["n"], int)
            assert ln["n"] > 0


def test_t004_duplicate_line_number_raises(tmp_path):
    """T-004: 行番号の重複は黙って通さず例外にする(HC-075)。"""
    broken = tmp_path / "dup.xml"
    broken.write_text(_tei_doc([("1", "alpha"), ("2", "beta"), ("2", "gamma")]), encoding="utf-8")
    with pytest.raises(ValueError, match="重複"):
        parse_tei.parse_books(broken)


def test_t005_non_monotonic_line_number_raises(tmp_path):
    """T-005: 行番号の非単調は例外にする。"""
    broken = tmp_path / "back.xml"
    broken.write_text(_tei_doc([("1", "alpha"), ("5", "beta"), ("3", "gamma")]), encoding="utf-8")
    with pytest.raises(ValueError, match="単調"):
        parse_tei.parse_books(broken)


def test_t006_two_paths_agree_on_line_number_sets(raw_grc):
    """T-006: 経路 A と経路 B の行番号集合が巻ごとに一致する。"""
    a = {b["book"]: {ln["n"] for ln in b["lines"]} for b in parse_tei.parse_books(raw_grc)}
    b_ = {r["book"]: set(r["line_numbers"]) for r in line_oracle.scan(raw_grc)}
    assert a.keys() == b_.keys()
    for book in sorted(a):
        assert a[book] == b_[book], f"巻 {book} で集合が食い違う"


def test_t007_two_paths_agree_on_order(raw_grc):
    """T-007: 結論(集合)だけでなく出現順序列も一致する(HC-065 — 経路も比べる)。"""
    a = {b["book"]: [ln["n"] for ln in b["lines"]] for b in parse_tei.parse_books(raw_grc)}
    b_ = {r["book"]: list(r["line_numbers"]) for r in line_oracle.scan(raw_grc)}
    for book in sorted(a):
        assert a[book] == b_[book], f"巻 {book} で順序列が食い違う"


def test_t008_positive_control_compacted_oracle_is_rejected(raw_grc):
    """T-008 陽性対照: 欠番を詰めて連番にした贋オラクルを照合が落とすこと。

    これが落ちないなら、T-006/T-007 は経路を見ていない。
    """
    real = {r["book"]: list(r["line_numbers"]) for r in line_oracle.scan(raw_grc)}
    forged = {bk: list(range(1, len(ns) + 1)) for bk, ns in real.items()}
    # 欠番のある巻でだけ贋物は本物とずれる。ずれる巻が実在することをまず表明する。
    differing = [bk for bk in real if real[bk] != forged[bk]]
    assert set(differing) == set(MEASURED_MISSING), (
        "贋物と本物がずれる巻が、実測した欠番のある巻と一致しない"
    )
    a = {b["book"]: [ln["n"] for ln in b["lines"]] for b in parse_tei.parse_books(raw_grc)}
    for bk in differing:
        assert a[bk] != forged[bk], f"巻 {bk} で贋オラクルを落とせていない"


def test_t009_sum_of_maxima_matches_external_authority(raw_grc):
    """T-009: 各巻の行番号最大値の和が、流通値 15,693 と一致する。"""
    total = sum(max(r["line_numbers"]) for r in line_oracle.scan(raw_grc))
    assert total == EXTERNAL_SUM_OF_MAXIMA


def test_t010_extant_lines_fewer_than_sum_of_maxima(raw_grc):
    """T-010: 実在行は最大値の和より 6 行少ない。通説の数字は行数ではない。"""
    extant = sum(len(r["line_numbers"]) for r in line_oracle.scan(raw_grc))
    assert extant == MEASURED_EXTANT_LINES
    assert extant < EXTERNAL_SUM_OF_MAXIMA
    assert EXTERNAL_SUM_OF_MAXIMA - extant == sum(len(v) for v in MEASURED_MISSING.values())


def test_t011_gaps_are_preserved_not_compacted(raw_grc):
    """T-011: 欠番が正準データで保持される。第 9 巻は 457 の次が 462。"""
    books = {b["book"]: [ln["n"] for ln in b["lines"]] for b in parse_tei.parse_books(raw_grc)}
    for book, missing in MEASURED_MISSING.items():
        ns = books[book]
        present = set(ns)
        for m in missing:
            assert m not in present, f"巻 {book} 行 {m} は底本に無いはずだが存在する"
        lo = min(missing) - 1
        hi = max(missing) + 1
        assert ns[ns.index(lo) + 1] == hi, f"巻 {book} で {lo} の次が {hi} になっていない"


def test_t012_line_number_is_stored_not_derived(raw_grc):
    """T-012: 行番号は明示保持され、添字から導出されていない。

    添字+1 と行番号がずれる巻が実在することを示す。ずれる巻が無ければ、
    添字で代用しても気づけないので、この不変量は意味を持つ。
    """
    books = parse_tei.parse_books(raw_grc)
    diverging = [
        b["book"] for b in books if any(ln["n"] != i + 1 for i, ln in enumerate(b["lines"]))
    ]
    assert set(diverging) == set(MEASURED_MISSING), (
        "添字+1 と行番号がずれる巻が、欠番のある巻と一致しない"
    )


def _tei_doc(lines: list[tuple[str, str]]) -> str:
    body = "\n".join(f'<l n="{n}">{t}</l>' for n, t in lines)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>\n'
        '<div type="edition"><div type="textpart" subtype="Book" n="1">\n'
        f"{body}\n"
        "</div></div></body></text></TEI>\n"
    )
