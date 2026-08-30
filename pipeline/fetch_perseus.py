"""Perseus canonical-greekLit から底本 XML を取得する(F-01 / N-03 / N-04)。

取得対象は 2 本。

- tlg0012.tlg001.perseus-grc2 — 原文(Monro & Allen, Editio Tertia)
- tlg0012.tlg001.perseus-eng3 — A. T. Murray 英訳(Loeb, 1924)。照合用

キャッシュが在れば HTTP を叩かない(N-03)。取得物は data/raw/ に置き git 管理外(N-04)。
再取得の同一性は data/sources.json の sha256 で確かめられる。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_RAW = (
    "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit"
    "/master/data/tlg0012/tlg001"
)

MIN_INTERVAL_SEC = 1.2  # N-03


@dataclass(frozen=True)
class Source:
    key: str
    urn: str
    filename: str
    role: str
    note: str


SOURCES: tuple[Source, ...] = (
    Source(
        key="grc",
        urn="urn:cts:greekLit:tlg0012.tlg001.perseus-grc2",
        filename="tlg0012.tlg001.perseus-grc2.xml",
        role="原文",
        note="Homeri Opera, ed. D. B. Monro & T. W. Allen, Editio Tertia, Oxford: Clarendon Press",
    ),
    Source(
        key="eng",
        urn="urn:cts:greekLit:tlg0012.tlg001.perseus-eng3",
        filename="tlg0012.tlg001.perseus-eng3.xml",
        role="英訳(照合用)",
        note="A. T. Murray, Loeb Classical Library, London: W. Heinemann, 1924",
    ),
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
SOURCES_JSON = PROJECT_ROOT / "data" / "sources.json"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Fetcher:
    """HTTP 呼び出しを 1 箇所に閉じ込める。テストはここを差し替えて命中を検査する。"""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._last_call_at: float | None = None

    def get(self, url: str) -> bytes:
        if self._last_call_at is not None:
            elapsed = time.monotonic() - self._last_call_at
            if elapsed < MIN_INTERVAL_SEC:
                time.sleep(MIN_INTERVAL_SEC - elapsed)
        self.calls.append(url)
        req = urllib.request.Request(
            url, headers={"User-Agent": "ikari-uta/0.1 (fleet research; contact via repo)"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (固定 https)
            body = resp.read()
        self._last_call_at = time.monotonic()
        return body


def fetch_all(
    fetcher: Fetcher | None = None, *, force: bool = False, raw_dir: Path | None = None
) -> list[dict]:
    """全ソースを取得し、メタ情報を返す。キャッシュ命中時は fetcher を呼ばない。"""
    fetcher = fetcher or Fetcher()
    raw_dir = raw_dir or RAW_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    for src in SOURCES:
        dest = raw_dir / src.filename
        cached = dest.exists() and not force
        if not cached:
            body = fetcher.get(f"{REPO_RAW}/{src.filename}")
            dest.write_bytes(body)
        records.append(
            {
                "key": src.key,
                "urn": src.urn,
                "role": src.role,
                "note": src.note,
                "filename": src.filename,
                "bytes": dest.stat().st_size,
                "sha256": sha256_of(dest),
                "cached": cached,
                "license": "CC BY-SA 4.0",
                "attribution": "Perseus Digital Library, Tufts University",
            }
        )
    return records


def main() -> int:
    ap = argparse.ArgumentParser(description="Perseus 底本 XML の取得")
    ap.add_argument("--force", action="store_true", help="キャッシュを無視して再取得する")
    args = ap.parse_args()

    records = fetch_all(force=args.force)
    SOURCES_JSON.parent.mkdir(parents=True, exist_ok=True)
    SOURCES_JSON.write_text(
        json.dumps({"sources": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for rec in records:
        state = "キャッシュ" if rec["cached"] else "取得"
        print(f"{state}: {rec['filename']}  {rec['bytes']:,} bytes  sha256={rec['sha256'][:16]}…")
    print(f"→ {SOURCES_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
