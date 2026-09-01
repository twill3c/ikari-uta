"""登場者一覧・地名一覧(T-033〜T-036)。

**索引は原文側で作る。** 訳文から名を拾えば、自分の書いたものを自分で数えるだけで
循環する。底本のギリシア語の中で語幹を探し、その当たり外れを**英訳という
独立の証人**で実測する。

**0 をゲートにしない。** 語幹の前方一致は近似であり、実測 90.2% である。
100% は達成できない —— ギリシア語の格変化と、英訳が別の語を使う場合
(風の名・父称)があるからだ。直せないものをゲートにしない(HC-002)。
代わりに**下がらないこと**を見張る。
"""

import pytest

from pipeline.build_index import build, measure, to_records

pytestmark = pytest.mark.validation

# 実測 2026-09-01(loop_026)。標本 1,691 箇所。
MEASURED_ACCURACY = 0.902
# 綴りでは分けられない群の数。増減したら中身を見に行く。
MEASURED_AMBIGUOUS = 76


def test_t033_index_accuracy_does_not_fall():
    """T-033: 英訳との一致率が、実測から落ちていない。"""
    m = measure()
    assert m["rate"] >= MEASURED_ACCURACY - 0.02, (
        f"英訳との一致が {m['rate']*100:.1f}% に落ちた(実測 {MEASURED_ACCURACY*100:.1f}%)。"
        " 語幹の作り方か対訳表の変更が索引を壊している"
    )


def test_t034_ambiguous_groups_are_measured():
    """T-034: 綴りで分けられない群の数が、実測と一致する。

    増えたら新しい衝突が入った合図であり、減ったら見張りが緩んでいる合図である。
    """
    amb = sum(1 for g in build()["groups"] if g["ambiguous"])
    assert abs(amb - MEASURED_AMBIGUOUS) <= 3, (
        f"曖昧な群が {amb} 個(実測 {MEASURED_AMBIGUOUS})。中身を確かめること"
    )


def test_t035_major_names_present_with_plausible_counts():
    """T-035 陽性対照: 主要な名が索引にあり、桁が妥当である。

    索引が静かに壊れる形は「数が減る」ではなく「名が消える」である。
    実際 loop_026 の途中で、語幹を作れなかったヘーラーが**索引から丸ごと消え**、
    その出現を綴りの似た名が横取りしていた。数だけ見ていたら気づけなかった。
    """
    recs = to_records()
    counts = {r["ja"]: r["count"] for page in recs.values() for r in page}
    for ja, low in [("アキレウス", 150), ("ヘクトール", 120), ("ゼウス", 300),
                    ("ヘーラー", 60), ("アテーネー", 80), ("トロイア", 300),
                    ("アガメムノーン", 100), ("パトロクロス", 80)]:
        assert ja in counts, f"{ja} が索引から消えている"
        assert counts[ja] >= low, f"{ja} の出現が {counts[ja]} 行しかない(下限 {low})"


def test_t036_occurrences_point_at_real_lines():
    """T-036: 索引が指す (巻, 行) が、すべて底本に実在する。

    欠番(第9巻458-461など)を指していれば、読む画面で行方不明になる。
    """
    import json
    from pipeline.build_index import ROOT
    real = set()
    for f in sorted((ROOT / "data" / "canonical").glob("book-*.json")):
        b = int(f.stem[-2:])
        for l in json.loads(f.read_text(encoding="utf-8"))["lines"]:
            real.add((b, l["n"]))
    bad = []
    for page in to_records().values():
        for r in page:
            bad += [(r["ja"], b, n) for b, n in r["occ"] if (b, n) not in real]
    assert not bad, f"底本に無い行を指している: {bad[:5]}"
