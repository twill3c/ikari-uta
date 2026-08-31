"""定型句の一貫性(T-032)。同じ原文行には同じ訳を当てる。

**この検査は非循環である。** 鍵にするのは「底本で同一の行」という原文側の事実で、
私が作ったものではない。

**なぜ 0 でなく実測値で止めるか。** 着手時点で既訳に 263 組の割れがある。
これを一括で直すのは、既訳の全巻を洗い替える専用ループの仕事であって、
検査を緩めることでも、この場で急いで直すことでもない(HC-002 / F-04 の凍結と同じ考え)。
**直せない量をゲートにしない。代わりに増やさないことをゲートにする。**
"""

import pytest

from pipeline.measure_formula import divergences

pytestmark = pytest.mark.validation

# 実測 2026-08-31(loop_020、第 1〜19 巻訳了時点)。
# 新しい巻を訳して**新たな揺れを持ち込んだとき**にだけ、この数は増える。
# 既存の割れを直せば減る。減った場合もここを更新する(緩めすぎの見張りを残さないため)。
MEASURED_DIVERGENCES = 263

# **原文が代名詞しか持たないために、訳し分けが正しい行。**
# 底本で同一の行でも、指す人物が文脈で変われば日本語では別の名を補うことになる。
# これは揺れではないので、実測の例外として名指しで許す。
# 増やすときは、必ず「原文のどこが代名詞か」を書き添えること。
ALLOWED_CONTEXT_DIVERGENCE = {
    # ὃ δὲ(彼は)だけで主語を書かない行。第5巻はテューデウスの子、第20巻はアイネイアース。
    "σμερδαλέα ἰάχων· ὃ δὲ χερμάδιον λάβε χειρὶ",
}


def test_t032_formulaic_divergence_does_not_grow():
    div = [d for d in divergences() if d[0] not in ALLOWED_CONTEXT_DIVERGENCE]
    assert len(div) <= MEASURED_DIVERGENCES, (
        f"同一の原文行に異なる訳を当てた組が {len(div)} 組に増えた"
        f"(実測 {MEASURED_DIVERGENCES})。新しく持ち込んだ揺れがある。"
        " python pipeline/measure_formula.py --list で確認すること"
    )
    assert len(div) >= MEASURED_DIVERGENCES - 20, (
        f"割れが {len(div)} 組まで減っている(実測 {MEASURED_DIVERGENCES})。"
        "直したのなら MEASURED_DIVERGENCES を更新すること —— 緩すぎる見張りを残さない"
    )


def test_t032d_allowed_exceptions_still_diverge():
    """例外に挙げた行が、実際に今も割れていること。

    直った行を例外に残すと、見張りが緩んだまま気づけない(T-029a と同じ考え)。
    """
    actual = {g for g, _ in divergences()}
    stale = ALLOWED_CONTEXT_DIVERGENCE - actual
    assert not stale, f"例外に挙げた行が割れていない(緩めすぎの見張り): {sorted(stale)}"


def test_t032b_oracle_is_not_empty():
    """陽性対照の前提: 比較できる組がそもそも無ければ、T-032 は何も見ていない。"""
    from pipeline.measure_formula import load, normalize
    grc, ja = load()
    comparable = sum(1 for g, locs in grc.items() if len([k for k in locs if k in ja]) >= 2)
    assert comparable >= 300, f"比較できる原文行が {comparable} 種しかない"


def test_t032c_positive_control_detects_injected_drift():
    """陽性対照: 一致している組の片方を書き換えたら、検出できること。"""
    from pipeline.measure_formula import load, normalize
    grc, ja = load()
    agreeing = None
    for g, locs in grc.items():
        have = [k for k in locs if k in ja]
        if len(have) >= 2 and len({normalize(ja[k]) for k in have}) == 1:
            agreeing = have
            break
    assert agreeing, "一致している組が一つも無い。この対照は何も見ていない"
    tampered = dict(ja)
    tampered[agreeing[0]] = tampered[agreeing[0]] + "ズ"
    assert len({normalize(tampered[k]) for k in agreeing}) > 1, (
        "改竄した訳を検出できていない"
    )
