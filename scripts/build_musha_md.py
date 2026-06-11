#!/usr/bin/env python3
"""武者: 構造JSON(/tmp/musha_json/{go}.json) + 要約JSON(/tmp/musha_sum/{go}.json)
から content/musha/{date}.md を生成。図表は各セクションのDOM位置に自動配置、hero=fig1。

要約JSON 形式:
{
  "tags": ["..."],            # 3-5個
  "summary": "60字以内1行",
  "exec": "エグゼクティブサマリー 3-4文",
  "sections": { "1": "要約文", "2": "...", ... }   # (N) ごとの圧縮要約
}
"""
import sys, json, re, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def segment(blocks):
    """blocks を intro + sections に分割。各 section に図表(alt付)を紐付け。"""
    sections, intro, cur, pending_cap = [], [], None, None
    for b in blocks:
        if b["type"] == "text":
            t = b["text"]
            m = re.match(r"^\s*[\(（](\d+)[\)）]\s*(.*)$", t)
            if m and len(m.group(2)) > 2:   # (N) 見出し
                cur = {"n": m.group(1), "heading": m.group(2).strip(), "figs": []}
                sections.append(cur)
                pending_cap = None
            elif t.startswith("図表"):
                pending_cap = t
            elif cur is None:
                intro.append(t)
        elif b["type"] == "img" and b.get("file"):
            alt = pending_cap or (cur["heading"] if cur else "図表")
            (cur["figs"] if cur else sections[-1]["figs"] if sections else []).append(
                {"file": b["file"], "alt": alt}
            )
            pending_cap = None
    return intro, sections


def build(go):
    data = json.load(open(f"/tmp/musha_json/{go}.json"))
    summ = json.load(open(f"/tmp/musha_sum/{go}.json"))
    date = data["date"]
    fig_files = [f for f in (data.get("fig_files") or []) if f]
    hero = f'/images/musha/{go}/{fig_files[0]}' if fig_files else ""

    _, sections = segment(data["blocks"])

    fm = ["---"]
    fm.append(f'hero_image: "{hero}"')
    fm.append(f'title: "武者リサーチ ストラテジーブレティン 第{go}号｜{date_jp(date)}"')
    fm.append(f"date: {date}")
    fm.append('categories: ["武者リサーチ"]')
    fm.append("tags: [" + ", ".join(f'"{t}"' for t in summ["tags"]) + "]")
    fm.append(f'original_url: "{data["url"]}"')
    fm.append(f'summary: "{summ["summary"]}"')
    fm.append("---")

    out = ["\n".join(fm), ""]
    out.append("## レポート概要\n")
    out.append(f'**{data["title"]}**  ')
    if data.get("subtitle"):
        out.append(f'〜{data["subtitle"].strip("〜～")}〜')
    out.append("")
    out.append("> **エグゼクティブサマリー**")
    out.append(f"> {summ['exec']}")
    out.append("\n---\n")

    # 要約にあるセクションを順に。図表は構造JSONの該当セクションから補完。
    by_n = {s["n"]: s for s in sections}
    for n, text in summ["sections"].items():
        sec = by_n.get(n, {})
        head = sec.get("heading", "")
        out.append(f"### ({n}) {head}".rstrip())
        out.append("")
        out.append(text)
        out.append("")
        for fig in sec.get("figs", []):
            out.append(f'![{fig["alt"]}](/images/musha/{go}/{fig["file"]})')
            out.append("")

    out.append("---\n")
    out.append("*本稿は株式会社武者リサーチ発行のレポートを要約したものです。図表は原文より引用。*")

    dest = os.path.join(REPO, "content", "musha", f"{date}.md")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    nf = sum(len(s.get("figs", [])) for s in sections)
    print(f"  ✅ {go} → content/musha/{date}.md (sections={len(summ['sections'])}, figs={nf})")


def date_jp(iso):
    y, m, d = iso.split("-")
    return f"{y}年{int(m)}月{int(d)}日"


if __name__ == "__main__":
    for go in sys.argv[1:]:
        build(go)
