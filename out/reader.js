/* 怒り歌 — リーダー。
 *
 * 通信は同一オリジンの相対パスのみ(N-01)。外部を叩かない。
 * 行番号は底本のものをそのまま表示する。連番ではないので、欠番はその旨を出す。
 * 英訳は 5 行おきの錨しか持たない(SPEC §3.1)ので、錨の行に区間の頭を出すに留める。
 */
(function () {
  "use strict";

  var params = new URLSearchParams(location.search);
  var book = parseInt(params.get("book"), 10);
  if (!Number.isInteger(book) || book < 1 || book > 24) book = 1;

  var titleEl = document.getElementById("title");
  var statusEl = document.getElementById("status");
  var textEl = document.getElementById("text");
  var toggles = {
    ja: document.getElementById("v-ja"),
    grc: document.getElementById("v-grc"),
    eng: document.getElementById("v-eng")
  };

  var data = null;

  function pad(n) { return n < 10 ? "0" + n : String(n); }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function engByAnchor(segments) {
    var map = new Map();
    (segments || []).forEach(function (s) {
      // 同じ錨に区間が 2 つ来ることがある(第 2 巻 720)。落とさず連ねる。
      var prev = map.get(s.from_line);
      map.set(s.from_line, prev ? prev + " " + s.text : s.text);
    });
    return map;
  }

  function render() {
    if (!data) return;
    var show = { ja: toggles.ja.checked, grc: toggles.grc.checked, eng: toggles.eng.checked };
    if (!show.ja && !show.grc && !show.eng) {
      textEl.innerHTML = '<p class="empty">表示する層が選ばれていません。上のいずれかを入れてください。</p>';
      return;
    }

    var eng = engByAnchor(data.english);
    var missing = new Set(data.missing || []);
    var html = [];
    var prevN = null;

    if (!data.translated && show.ja) {
      html.push(
        '<p class="empty">この巻の和訳は<b>準備中</b>です。' +
        "原文と英訳は表示できます。訳は巻ごとに順次追加します。</p>"
      );
    }

    // 欠番の注記は「前後の行が実際に描かれた」ときだけ出す。保留してから流す。
    // 行が 1 本も描かれない層の組み合わせ(例: 和訳のみ表示 × 未訳の巻)で
    // 注記だけが宙に浮くのを防ぐ。
    var pendingGap = null;
    var emitted = 0;

    data.lines.forEach(function (ln) {
      if (prevN !== null && ln.n !== prevN + 1) {
        var gone = [];
        for (var k = prevN + 1; k < ln.n; k++) if (missing.has(k)) gone.push(k);
        if (gone.length) pendingGap = gone;
      }
      prevN = ln.n;

      var body = [];
      if (show.ja && ln.ja) body.push('<p class="t-ja">' + esc(ln.ja) + "</p>");
      if (show.grc) body.push('<p class="t-grc">' + esc(ln.grc) + "</p>");
      if (show.eng && eng.has(ln.n)) body.push('<p class="t-eng">' + esc(eng.get(ln.n)) + "</p>");
      if (!body.length) return;

      if (pendingGap && emitted > 0) {
        html.push(
          '<p class="gapnote">' + pendingGap.join("・") +
          " 行は底本にない(校訂者が本文から除き、番号だけが残っている)</p>"
        );
      }
      pendingGap = null;

      var id = "l" + ln.n;
      html.push(
        '<div class="ln" id="' + id + '">' +
        '<div class="num"><a href="#' + id + '">' + ln.n + "</a></div>" +
        '<div class="body">' + body.join("") + "</div></div>"
      );
      emitted++;
    });

    textEl.innerHTML = html.join("");
    if (location.hash) {
      var t = document.getElementById(location.hash.slice(1));
      if (t) t.scrollIntoView();
    }
  }

  Object.keys(toggles).forEach(function (k) {
    toggles[k].addEventListener("change", render);
  });

  fetch("data/book-" + pad(book) + ".json")
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (d) {
      data = d;
      titleEl.textContent = "第 " + d.book + " 巻";
      var bits = [
        d.line_count.toLocaleString() + " 行",
        "行番号 1–" + d.line_max,
        d.translated ? "和訳あり" : "和訳は準備中"
      ];
      if (d.missing && d.missing.length) {
        bits.push("底本の欠番: " + d.missing.join("・"));
      }
      statusEl.textContent = bits.join(" ／ ");
      render();
    })
    .catch(function (e) {
      titleEl.textContent = "読み込めませんでした";
      statusEl.textContent = String(e);
    });
})();
