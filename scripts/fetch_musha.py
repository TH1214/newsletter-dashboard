#!/usr/bin/env python3
"""武者リサーチ ストラテジーブレティン: 詳細ページから図表DL＋本文構造抽出。
要約は行わない（決定的処理のみ）。Claude/別工程が要約に使う構造化JSONを出力する。

usage: python3 fetch_musha.py <号番号> [--out-dir DIR]
  - 図表画像を DIR/static/images/musha/{号}/figN.{ext} に保存（DOM出現順）
  - 構造化データを stdout に JSON で出力
"""
import sys, re, json, html, os, urllib.request
from html.parser import HTMLParser

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.musha.co.jp"


def fetch(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()


def clean(s: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


class BodyParser(HTMLParser):
    """PostDescription 内を線形に走査し、テキストと img を出現順で blocks 化。"""
    def __init__(self):
        super().__init__()
        self.blocks = []   # {"type":"text","text":..} | {"type":"img","src":..}
        self._buf = []

    def _flush(self):
        t = clean("".join(self._buf))
        if t:
            self.blocks.append({"type": "text", "text": t})
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            d = dict(attrs)
            src = d.get("src", "")
            if "img/cache/" in src:
                self._flush()
                m = re.search(r"img/cache/[a-f0-9-]+\.(?:jpg|png)", src)
                if m:
                    self.blocks.append({"type": "img", "src": m.group(0)})
        elif tag in ("p", "br", "div", "table", "tr"):
            self._flush()

    def handle_data(self, data):
        self._buf.append(data)

    def close(self):
        self._flush()
        super().close()


def extract(go: str):
    url = f"{BASE}/short_comment/detail/{go}"
    raw = fetch(url).decode("utf-8", "replace")

    def grab(pat):
        m = re.search(pat, raw, re.S)
        return m.group(1).strip() if m else None

    date_jp = clean(grab(r'<h3 id="PostDate"[^>]*>(.*?)</h3>') or "")
    dm = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", date_jp)
    date_iso = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}" if dm else None

    title_raw = grab(r'<h1 id="PostTitle"[^>]*>(.*?)</h1>') or ""
    sub_small = re.search(r"<small>(.*?)</small>", title_raw, re.S)
    subtitle = clean(sub_small.group(1)) if sub_small else clean(grab(r'<h2 id="PostSubTitle"[^>]*>(.*?)</h2>') or "")
    main_title = clean(re.sub(r"<small>.*?</small>", "", title_raw, flags=re.S))

    body_html = grab(r'<div id="PostDescription"[^>]*>(.*?)</div>\s*(?:<div|<footer|<aside|$)')
    if not body_html:
        # フォールバック: PostDescription 開始から末尾まで
        m = re.search(r'<div id="PostDescription"[^>]*>(.*)$', raw, re.S)
        body_html = m.group(1) if m else raw

    p = BodyParser()
    p.feed(body_html)
    p.close()

    # PDF URL
    pdf = grab(r'href="(/attachment/[^"]+\.pdf)"')
    pdf_url = BASE + pdf if pdf else None

    # 図表DL（DOM順, 重複srcは順序維持で1回）
    seen, figs = set(), []
    for b in p.blocks:
        if b["type"] == "img" and b["src"] not in seen:
            seen.add(b["src"])
            figs.append(b["src"])

    return {
        "go": go, "url": url, "date": date_iso, "date_jp": date_jp,
        "title": main_title, "subtitle": subtitle, "pdf_url": pdf_url,
        "blocks": p.blocks, "figures": figs,
    }


def download_figs(data, out_dir):
    go = data["go"]
    dest_dir = os.path.join(out_dir, "static", "images", "musha", go)
    os.makedirs(dest_dir, exist_ok=True)
    mapping = {}   # src -> figN.ext
    for i, rel in enumerate(data["figures"], 1):
        ext = rel.rsplit(".", 1)[1]
        name = f"fig{i}.{ext}"
        try:
            blob = fetch(f"{BASE}/{rel}")
            with open(os.path.join(dest_dir, name), "wb") as f:
                f.write(blob)
            mapping[rel] = name
        except Exception as e:
            sys.stderr.write(f"  WARN fig{i} dl失敗: {e}\n")
    # blocks の img を figN に解決
    for b in data["blocks"]:
        if b["type"] == "img":
            b["file"] = mapping.get(b["src"])
    data["fig_files"] = [mapping.get(s) for s in data["figures"]]
    return data


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 fetch_musha.py <号番号> [--out-dir DIR]")
    go = sys.argv[1]
    out_dir = "."
    if "--out-dir" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--out-dir") + 1]
    data = extract(go)
    data = download_figs(data, out_dir)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
