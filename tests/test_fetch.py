"""取得器の検査。TEST_SPEC T-001〜T-002。"""

import pytest

from pipeline import fetch_perseus

pytestmark = pytest.mark.unit


class _RecordingFetcher(fetch_perseus.Fetcher):
    """HTTP を実際には叩かず、呼ばれたことだけを記録する。"""

    def get(self, url: str) -> bytes:  # noqa: D102
        self.calls.append(url)
        return b"<TEI/>"


def test_t001_cache_hit_makes_no_http_call(tmp_path):
    """T-001 / N-03: キャッシュが在れば HTTP を呼ばない。"""
    raw = tmp_path / "raw"
    raw.mkdir()
    for src in fetch_perseus.SOURCES:
        (raw / src.filename).write_bytes(b"<TEI/>")

    f = _RecordingFetcher()
    records = fetch_perseus.fetch_all(f, raw_dir=raw)

    assert f.calls == [], f"キャッシュ在りで HTTP を呼んだ: {f.calls}"
    assert all(r["cached"] for r in records)


def test_t001b_cache_miss_calls_http_once_per_source(tmp_path):
    """陽性対照: キャッシュが無ければ確かに取りに行く(検査が働いていることの確認)。"""
    raw = tmp_path / "raw"
    f = _RecordingFetcher()
    records = fetch_perseus.fetch_all(f, raw_dir=raw)

    assert len(f.calls) == len(fetch_perseus.SOURCES)
    assert not any(r["cached"] for r in records)


def test_t002_records_carry_provenance(tmp_path):
    """T-002: URN・ライセンス・帰属・sha256 が記録される。"""
    raw = tmp_path / "raw"
    records = fetch_perseus.fetch_all(_RecordingFetcher(), raw_dir=raw)
    assert records
    for r in records:
        for field in ("urn", "license", "attribution", "sha256"):
            assert r.get(field), f"{field} が空: {r}"
        assert r["urn"].startswith("urn:cts:greekLit:")
        assert r["license"] == "CC BY-SA 4.0"
