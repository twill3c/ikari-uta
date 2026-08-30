import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_GRC = PROJECT_ROOT / "data" / "raw" / "tlg0012.tlg001.perseus-grc2.xml"
RAW_ENG = PROJECT_ROOT / "data" / "raw" / "tlg0012.tlg001.perseus-eng3.xml"
CANONICAL_DIR = PROJECT_ROOT / "data" / "canonical"
JA_DIR = PROJECT_ROOT / "data" / "ja"
ORACLE = PROJECT_ROOT / "data" / "oracle" / "line_counts.json"
GLOSSARY = PROJECT_ROOT / "data" / "glossary.json"
OUT_DIR = PROJECT_ROOT / "out"


def _require(path: Path):
    if not path.exists():
        pytest.skip(f"未生成: {path.relative_to(PROJECT_ROOT)}(先に pipeline を走らせる)")
    return path


@pytest.fixture(scope="session")
def raw_grc() -> Path:
    return _require(RAW_GRC)


@pytest.fixture(scope="session")
def raw_eng() -> Path:
    return _require(RAW_ENG)


@pytest.fixture(scope="session")
def oracle() -> dict:
    return json.loads(_require(ORACLE).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def glossary() -> dict:
    return json.loads(_require(GLOSSARY).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def canonical_books() -> dict[int, dict]:
    _require(CANONICAL_DIR)
    books = {}
    for p in sorted(CANONICAL_DIR.glob("book-*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        books[int(d["book"])] = d
    if not books:
        pytest.skip("正準データが空")
    return books


@pytest.fixture(scope="session")
def ja_books() -> dict[int, dict]:
    if not JA_DIR.exists():
        pytest.skip("和訳データ未生成")
    books = {}
    for p in sorted(JA_DIR.glob("book-*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        books[int(d["book"])] = d
    if not books:
        pytest.skip("和訳データが空")
    return books
