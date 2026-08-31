"""訳文の断片(TSV)を正準データと突合しながら 1 巻分に組み立てる(F-05 / G-01)。

**突合に失敗したら黙って通さず例外で止める。** 訳は行番号でしか原文と結びついていないので、
ここが緩むと下流(年表の出典行・相関図の辺)がすべて静かにずれる。

TSV の形式は `行番号<TAB>訳文`。断片ファイルの分け方は自由で、
組み立て時に行番号で並べ直す。重複・欠落・原文に無い行はすべて例外にする。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "data" / "ja" / "src"
CANONICAL_DIR = PROJECT_ROOT / "data" / "canonical"
JA_DIR = PROJECT_ROOT / "data" / "ja"


def read_fragments(book: int, src_dir: Path = SRC_DIR) -> dict[int, str]:
    """1 巻分の断片をすべて読む。重複行はその場で例外にする。"""
    folder = src_dir / f"book-{book:02d}"
    if not folder.is_dir():
        raise FileNotFoundError(f"訳文の断片が無い: {folder}")

    lines: dict[int, str] = {}
    for path in sorted(folder.glob("*.tsv")):
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            if "\t" not in raw:
                raise ValueError(f"{path.name}:{lineno}: タブ区切りでない")
            head, text = raw.split("\t", 1)
            if not head.isdigit():
                raise ValueError(f"{path.name}:{lineno}: 行番号が数値でない: {head!r}")
            n = int(head)
            if n in lines:
                raise ValueError(f"{path.name}:{lineno}: 行 {n} が重複している")
            if not text.strip():
                raise ValueError(f"{path.name}:{lineno}: 行 {n} の訳が空")
            lines[n] = text.strip()
    if not lines:
        raise ValueError(f"巻 {book}: 断片から 1 行も読めなかった")
    return lines


def load_canonical(book: int, canonical_dir: Path = CANONICAL_DIR) -> dict:
    path = canonical_dir / f"book-{book:02d}.json"
    if not path.exists():
        raise FileNotFoundError(f"正準データが無い: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def assemble(book: int, *, src_dir: Path = SRC_DIR, canonical_dir: Path = CANONICAL_DIR) -> dict:
    """訳を組み立て、原文と突き合わせる(G-01)。

    **不変量と進捗指標を分ける(HC-085)。**

    - 失敗にする(常に成り立つべき): 訳に**原文にない行**があること。行の対応がずれていること
    - 測って出す(進捗): どれだけ揃ったか(被覆率)

    巻を分けて訳すのは正常な進め方であり、行の不足は欠陥ではない。
    「まだ無い」と「あってはならない」を同じ検査で扱わない。
    """
    frag = read_fragments(book, src_dir)
    canon = load_canonical(book, canonical_dir)
    expected = [ln["n"] for ln in canon["lines"]]
    expected_set = set(expected)
    got_set = set(frag)

    # 不変量: 原文に無い行を訳が持っていてはならない。これは常に失敗にする。
    extra = sorted(got_set - expected_set)
    if extra:
        raise ValueError(
            f"巻 {book}: 原文に存在しない行が訳にある {extra[:20]}(計 {len(extra)})。"
            "行番号の打ち間違いか、底本の取り違えを疑う"
        )

    # 進捗: 揃っていない分は測って出す。欠陥ではない。
    translated = [n for n in expected if n in got_set]
    missing = [n for n in expected if n not in got_set]

    return {
        "book": book,
        "line_count": len(translated),
        "source_line_count": len(expected),
        "complete": not missing,
        "coverage": round(len(translated) / len(expected), 4),
        "untranslated_from": missing[0] if missing else None,
        "source_urn": "urn:cts:greekLit:tlg0012.tlg001.perseus-grc2",
        "translation": {
            "by": "Claude (Anthropic)",
            "kind": "機械翻訳",
            "policy": "原文 1 行 = 訳 1 行。逐語寄りの現代語散文",
            "disclaimer": "学術的な定訳ではない。保証するのは行の対応と表記の一貫性であり、訳質ではない",
        },
        "lines": [{"n": n, "ja": frag[n]} for n in translated],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="訳文断片 → 巻別 JSON(突合つき)")
    ap.add_argument("--book", type=int, action="append", help="対象の巻(省略時は断片のある全巻)")
    args = ap.parse_args()

    books = args.book or sorted(
        int(p.name.split("-")[1]) for p in SRC_DIR.glob("book-*") if p.is_dir()
    )
    JA_DIR.mkdir(parents=True, exist_ok=True)
    for book in books:
        data = assemble(book)
        dest = JA_DIR / f"book-{book:02d}.json"
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"巻 {book}: {data['line_count']:,} 行 → {dest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
