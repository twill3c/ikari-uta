"""出荷物を実ブラウザで検品する(HC-041 / HC-078)。

**この道具は、失敗を終了コードで知らせる。** 取得に失敗した画面を撮っても
「撮影しました」と出るような検品は、検品していないのと同じである。

見るのは一つの幅ではない(HC-078)。横の溢れと縦の伸びすぎを機械で測り、
撮った画像は人間が目で見る。代理指標は目視の代わりではなく、目視を忘れたときの網である。
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "out"
SHOTS = PROJECT_ROOT / "out-shots"

WIDTHS = [(390, "narrow"), (768, "medium"), (1280, "wide")]
MAX_PAGE_HEIGHT = 200_000  # 15,687 行を出しうるので通常のページより緩い。柱化の網としては効く


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D102
        pass


def serve(directory: Path):
    handler = functools.partial(Quiet, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def _has_untranslated_book() -> bool:
    """未訳の巻が残っているか。出荷物そのものから読む(仕様の写しではなく実測)。"""
    manifest = json.loads((OUT_DIR / "data" / "manifest.json").read_text(encoding="utf-8"))
    return any(b["translated_lines"] < b["line_count"] for b in manifest["books"])


def check(page, url: str, label: str, must_contain: list[str], failures: list[str]) -> None:
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    resp = page.goto(url, wait_until="networkidle")
    if resp is None or not resp.ok:
        failures.append(f"{label}: 取得に失敗した({resp.status if resp else 'no response'})")
        return

    body = page.inner_text("body")
    for needle in must_contain:
        if needle not in body:
            failures.append(f"{label}: 「{needle}」が画面に出ていない")
    if errors:
        failures.append(f"{label}: コンソールエラー {errors[:3]}")

    for width, wname in WIDTHS:
        page.set_viewport_size({"width": width, "height": 900})
        page.wait_for_timeout(120)
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        height = page.evaluate("() => document.documentElement.scrollHeight")
        if overflow > 2:
            failures.append(f"{label}@{wname}({width}px): 横に {overflow}px 溢れている")
        if height > MAX_PAGE_HEIGHT:
            failures.append(f"{label}@{wname}({width}px): 縦が {height}px と伸びすぎ(柱化を疑う)")
        SHOTS.mkdir(exist_ok=True)
        page.screenshot(path=str(SHOTS / f"{label}-{wname}.png"), full_page=False)


def check_index_links(page, base: str, failures: list[str]) -> None:
    """索引の行リンクを実際に踏んで、その行が読む画面に現れることを確かめる。

    T-036 はデータの上で「実在する行を指している」ことを見る。
    こちらは**踏んだ先に本当に出るか**を実ブラウザで見る —— 別のことである。
    """
    page.goto(f"{base}/people.html", wait_until="networkidle")
    href = page.eval_on_selector("ol.names .occ a", "a => a.getAttribute('href')")
    if not href or "#l" not in href:
        failures.append(f"索引の行リンクが取れない: {href!r}")
        return
    want = href.split("#l")[1]
    page.goto(f"{base}/{href}", wait_until="networkidle")
    page.wait_for_timeout(200)
    if page.locator(f"#l{want}").count() == 0:
        failures.append(f"索引のリンク先に行 {want} が無い({href})")
    # 陰性対照: 底本に無い行を指したら、その行は現れないこと
    page.goto(f"{base}/read.html?book=9#l459", wait_until="networkidle")
    page.wait_for_timeout(200)
    if page.locator("#l459").count():
        failures.append("欠番 9:459 が行として描かれている(この対照は何も見ていない)")


def check_gap_note(page, base: str, failures: list[str]) -> None:
    """欠番注記の陽性・陰性対照(HC-041)。

    出るべき場合(行が描かれている)と、出るべきでない場合(行が 1 本も描かれない)の
    両方を押さえる。片方だけでは対照にならない。

    **陰性対照は自分の前提を作る。** 以前はこれを「第 9 巻はまだ未訳だから行が出ない」に
    依存させていたが、第 9 巻を訳した時点でその前提が消え、対照は
    「アプリが壊れた」ではなく「対照の足場が無くなった」を報告した(loop_010)。
    訳の進み具合で足場が消えないよう、表示切替を全部外して行 0 本を**こちらで作る**。
    """
    note = "行は底本にない"
    page.goto(f"{base}/read.html?book=9", wait_until="networkidle")

    # 陰性対照: 表示切替を全部外す → 行が 1 本も描かれないので注記も出ない。
    # この前提は訳の進捗に依存しない。
    page.uncheck("#v-ja")
    page.wait_for_timeout(150)
    # 「行が 0 本」は #text が空であることではない —— 層を選んでいない旨の案内は出る。
    # 数えるのは行そのもの(.ln)。
    drawn = page.locator("#text .ln").count()
    if drawn:
        failures.append(f"欠番注記の陰性対照が壊れている: 全部外したのに行が {drawn} 本描かれている")
    if note in page.inner_text("#text"):
        failures.append("欠番注記: 行が 1 本も描かれていないのに注記が出ている(宙に浮いた注記)")

    # 陽性対照: 原文を出せば行が描かれ、その間に注記が出る
    page.check("#v-grc")
    page.wait_for_timeout(150)
    body = page.inner_text("#text")
    if note not in body:
        failures.append("欠番注記: 原文を表示しても注記が出ない(この検査は何も見ていない)")
    if "458・459・460・461" not in body:
        failures.append("欠番注記: 第 9 巻の欠番 458–461 が注記に出ていない")


def main() -> int:
    ap = argparse.ArgumentParser(description="出荷物の実ブラウザ検品")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    if not (args.out / "index.html").exists():
        print(f"出荷物が無い: {args.out}", file=sys.stderr)
        return 2

    httpd, port = serve(args.out)
    base = f"http://127.0.0.1:{port}"
    failures: list[str] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            # 「準備中」は**未訳の巻が残っている間だけ**画面に出る文言である。
            # 期待値に直書きすると、全 24 巻を訳し終えた日に、この検査は
            # 「アプリが壊れた」と報告する —— 実際には正常に完成しただけなのに(HC-102)。
            # そこで前提を manifest から作り、どちらの局面でも正しく判定する。
            expect = ["怒り歌", "15,687", "Perseus", "機械翻訳"]
            if _has_untranslated_book():
                expect.append("準備中")
            check(page, f"{base}/index.html", "index", expect, failures)
            if not _has_untranslated_book():
                page.goto(f"{base}/index.html", wait_until="networkidle")
                if "準備中" in page.inner_text("body"):
                    failures.append("index: 全巻訳し終えているのに「準備中」が残っている")
            check(page, f"{base}/read.html?book=1", "read-book01",
                  ["第 1 巻", "611 行", "怒りを歌え", "Perseus", "機械翻訳"], failures)
            # 「準備中」は入れない —— 第 9 巻は loop_010 で訳し終えた。
            # 未訳の巻を見たいときは、その時点で未訳の巻を manifest から取る。
            check(page, f"{base}/read.html?book=9", "read-book09",
                  ["第 9 巻", "709 行", "底本の欠番"], failures)
            # 索引の 2 ページ。**行へ跳ぶリンクが実在の行を指すこと**は T-036 が見る。
            # ここで見るのは、画面に出ていることと、限界の但し書きが消えていないこと。
            check(page, f"{base}/people.html", "people",
                  ["登場者一覧", "アキレウス", "ヘクトール", "綴りでは分けられない",
                   "英訳を独立の証人として"], failures)
            check(page, f"{base}/places.html", "places",
                  ["地名一覧", "トロイア", "イーデー", "綴りでは分けられない"], failures)
            check_index_links(page, base, failures)
            check_gap_note(page, base, failures)
            browser.close()
    finally:
        httpd.shutdown()

    if failures:
        print("検品 NG:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"検品 OK / 画像 → {SHOTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
