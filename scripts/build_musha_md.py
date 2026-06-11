#!/usr/bin/env python3
"""武者: 構造JSON(/tmp/musha_json/{go}.json) + 要約JSON(/tmp/musha_sum/{go}.json)
から content/musha/{date}.md を生成。hero=fig1、図表は各セクションに明示配置。

要約JSON 形式:
{
  "tags": ["..."],
  "summary": "60字以内1行",
  "exec": "エグゼクティブサマリー 3-4文",
  "sections": [
    {"heading": "(1) 見出し", "text": "要約文", "figs": ["fig1.jpg", "fig2.jpg"]},
    ...
  ]
}
figs は省略可。alt は構造JSON中の該当画像直前の「図表…」キャプションから自動補完。
"""
import sys, json, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def caption_map(blocks):
    """fileName -> 直前の図表キャプション。"""
    m, pending = {}, None
    for b in blocks:
        if b["type"] == "text" and b["text"].startswith("図表"):
            pending = b["text"]
        elif b["type"] == "img" and b.get("file"):
            m[b["file"]] = pending or "図表"
            pending = None
    return m


def date_jp(iso):
    y, mo, d = iso.split("-")
    return f"{y}年{int(mo)}月{int(d)}日"


def build(go):
    data = json.load(open(f"/tmp/musha_json/{go}.json"))
    summ = json.load(open(f"/tmp/musha_sum/{go}.json"))
    date = data["date"]
    fig_files = [f for f in (data.get("fig_files") or []) if f]
    hero = f"/images/musha/{go}/{fig_files[0]}" if fig_files else ""
    caps = caption_map(data["blocks"])

    fm = ["---",
          f'hero_image: "{hero}"',
          f'title: "武者リサーチ ストラテジーブレティン 第{go}号｜{date_jp(date)}"',
          f"date: {date}",
          'categories: ["武者リサーチ"]',
          "tags: [" + ", ".join(f'"{t}"' for t in summ["tags"]) + "]",
          f'original_url: "{data["url"]}"',
          f'summary: "{summ["summary"]}"',
          "---"]

    out = ["\n".join(fm), "", "## レポート概要", ""]
    out.append(f'**{data["title"]}**  ')
    if data.get("subtitle"):
        out.append(f'〜{data["subtitle"].strip("〜～")}〜')
    out += ["", "> **エグゼクティブサマリー**", f"> {summ['exec']}", "", "---", ""]

    for sec in summ["sections"]:
        out.append(f"### {sec['heading']}".rstrip())
        out += ["", sec["text"], ""]
        for fig in sec.get("figs", []):
            alt = caps.get(fig, "図表")
            out += [f"![{alt}](/images/musha/{go}/{fig})", ""]

    out += ["---", "", "*本稿は株式会社武者リサーチ発行のレポートを要約したものです。図表は原文より引用。*"]

    dest = os.path.join(REPO, "content", "musha", f"{date}.md")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    nf = sum(len(s.get("figs", [])) for s in summ["sections"])
    print(f"  ✅ {go} → content/musha/{date}.md (sections={len(summ['sections'])}, figs={nf})")


if __name__ == "__main__":
    for go in sys.argv[1:]:
        build(go)
