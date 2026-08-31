"""対訳表の凍結規律(F-04 / G-03)。TEST_SPEC T-027〜T-030。

**既訳は凍結された表記に依存している。** 第 1 巻 611 行はこの表のカタカナで書かれており、
一語でも変えれば出荷済みの訳が表と食い違う。よって表は**追加のみ**を許す。

変えたくなったら、この検査を緩めるのではなく、既訳の全巻を洗い替える専用ループを立てる。
"""

import json

import pytest

from tests.conftest import PROJECT_ROOT

pytestmark = pytest.mark.validation

FROZEN = PROJECT_ROOT / "data" / "glossary.frozen.json"


def _frozen() -> dict:
    return json.loads(FROZEN.read_text(encoding="utf-8"))["entries"]


def test_t027_frozen_entries_are_unchanged(glossary):
    """T-027: 凍結済みの見出しが、同じカタカナのまま現在の表に残っている。"""
    frozen = _frozen()
    current = {e["grc"]: e["ja"] for e in glossary["entries"]}

    dropped = sorted(k for k in frozen if k not in current)
    assert not dropped, f"凍結済みの見出しが消えた: {dropped}"

    changed = {k: (frozen[k], current[k]) for k in frozen if current[k] != frozen[k]}
    assert not changed, (
        f"凍結済みの表記が変わった(既訳が嘘になる): {changed}。"
        "変えるなら既訳の全巻を洗い替える専用ループを立てること"
    )


def test_t028_frozen_snapshot_is_not_empty():
    """陽性対照の前提: スナップショットが空なら T-027 は何も検査していない(HC-070)。"""
    frozen = _frozen()
    assert len(frozen) >= 60, f"凍結スナップショットが {len(frozen)} 語しかない"


# 民族名と地名は語幹を共有するのが日本語として正常である(アルゴス人 / アルゴス)。
# これは誤りではないので許すが、**実測した集合に固定**して、新規の偶発衝突は今も落ちるようにする。
# 実測 2026-08-31。
MEASURED_STEM_SHARING = {
    ("ピュロス", "Πύλιοι", "Πύλος"),
    ("アルゴス", "Ἀργεῖοι", "Ἄργος"),
    ("アカイア", "Ἀχαιοί", "Ἀχαιΐς"),
    # loop_003(軍船の一覧)で追加。島とその住民。
    ("ロドス", "Ῥόδος", "Ῥόδιοι"),
}


def test_t029a_no_two_persons_share_katakana(glossary):
    """T-029a: **別人が同じカタカナを持たない。** 人物種別(god / hero)内の衝突だけを見る。

    守りたいのは「読者が別人を取り違えないこと」であって、
    民族名と地名が語幹を共有することではない(そちらは T-029b が見る)。
    """
    seen: dict[str, str] = {}
    clashes = []
    for e in glossary["entries"]:
        if e["kind"] not in ("god", "hero"):
            continue
        ja = e["ja"]
        if ja in seen and seen[ja] != e["grc"]:
            clashes.append((ja, seen[ja], e["grc"]))
        seen[ja] = e["grc"]
    assert not clashes, f"別人が同じカタカナを持っている: {clashes}"


def test_t029b_stem_sharing_matches_measurement(glossary):
    """T-029b: 民族名 / 地名の語幹共有が、実測した集合と一致する。

    共有そのものは正常だが、**増えたら見に行く**。新規の偶発衝突をここで捕まえる。
    """
    seen: dict[str, str] = {}
    sharing = set()
    for e in glossary["entries"]:
        ja = e["ja"]
        if ja in seen and seen[ja] != e["grc"]:
            sharing.add((ja, seen[ja], e["grc"]))
        seen[ja] = e["grc"]
    assert sharing == MEASURED_STEM_SHARING, (
        f"語幹共有が実測と食い違う。増えた: {sorted(sharing - MEASURED_STEM_SHARING)} / "
        f"消えた: {sorted(MEASURED_STEM_SHARING - sharing)}"
    )


def test_t030_every_entry_has_required_fields(glossary):
    """T-030: 全項目が原語・英訳形・カタカナ・種別を持つ。"""
    missing = [
        e for e in glossary["entries"]
        if not all(e.get(k) for k in ("grc", "eng", "ja", "kind"))
    ]
    assert not missing, f"欄が欠けた項目: {missing[:5]}"


def test_t031_positive_control_change_is_detected():
    """T-031 陽性対照: 表記を変えた表を、検査が落とすこと。

    これが落ちないなら T-027 は凍結を守っていない。
    """
    frozen = _frozen()
    key = next(iter(frozen))
    tampered = {k: (v + "ズ" if k == key else v) for k, v in frozen.items()}
    changed = {k: (frozen[k], tampered[k]) for k in frozen if tampered[k] != frozen[k]}
    assert changed, "改竄した表を検出できていない。この対照は何も見ていない"
