#!/usr/bin/env python3
"""
translate_axios.py — Axios 統合ソース専用トランスレータ。

fetch_gmail.py が出力する「=== MEMBER: <label> | <subject> ===」マーカー付きの
連結テキストを受け取り、**メンバーごとに個別に翻訳**して、見出し
「## <label>：<件名の和訳>」をコード側で確実に付与しながら1記事に組み立てる。

これにより、単一LLM呼び出し＋チャンク分割で gpt-4o-mini がメンバー境界を無視して
再構成し「どの配信の内容か分からない」問題（エグゼクティブサマリー重複・見出し消失）を
構造的に解消する。

公開ファイル（秘密情報なし）。翻訳の実呼び出しは translate_gemini.py（runtimeで
GitHub Secret から scripts/ に復元される）の関数を import して再利用する。

Usage:
    python scripts/translate_axios.py <source> <date> < member_blob > out.md
Env: translate_gemini.py と同じ（GEMINI_API_KEY / GITHUB_TOKEN / TRANSLATION_MODEL /
     GITHUB_MODELS_ENDPOINT / CHUNK_CHAR_LIMIT / MAX_RETRIES / CHUNK_SLEEP_SEC ...）
"""
import sys
import os
import re
import time

import translate_gemini as tg  # runtime: scripts/translate_gemini.py (secretから復元)

# slug -> (表示名, カテゴリ)
SOURCE_MAP = {
    "axios-daily":    ("Axios Daily",          "Axios Daily"),
    "axios-ai":       ("Axios AI+PE/MA/VC",    "Axios AI+PE/MA/VC"),
    "axios-frontier": ("Axios Def/CAR/2028",   "Axios Def/CAR/2028"),
}

MEMBER_RE = re.compile(r'^=== MEMBER:\s*(?P<label>.+?)\s*\|\s*(?P<subject>.*?)\s*===\s*$')


def log(msg):
    print(f"[translate_axios] {msg}", file=sys.stderr)


def build_fallback():
    """translate_gemini.main() と同じ優先順でフォールバックチェーンを構築し、
    1プロンプトを翻訳する関数 translate(prompt)->str を返す。"""
    token = os.environ.get("GITHUB_TOKEN")
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    groq_api_key = os.environ.get("GROQ_API_KEY")
    model = os.environ.get("TRANSLATION_MODEL", tg.DEFAULT_MODEL)
    base_url = os.environ.get("GITHUB_MODELS_ENDPOINT", tg.DEFAULT_ENDPOINT)
    groq_model = os.environ.get("GROQ_MODEL", tg.GROQ_DEFAULT_MODEL)
    max_retries = int(os.environ.get("MAX_RETRIES", tg.DEFAULT_MAX_RETRIES))

    chain = []
    if gemini_api_key:
        chain.append("gemini")
    if groq_api_key:
        chain.append("groq")
    if token:
        chain.append("github_models")
    if not chain:
        log("No API key (GEMINI_API_KEY / GROQ_API_KEY / GITHUB_TOKEN)")
        sys.exit(1)
    log(f"fallback chain: {chain}")

    def translate(prompt: str) -> str:
        last = None
        for b in chain:
            try:
                if b == "gemini":
                    return tg.call_gemini_api(gemini_api_key, prompt, max_retries=max_retries)
                if b == "groq":
                    return tg.call_groq_api(groq_api_key, prompt, model=groq_model, max_retries=max_retries)
                return tg.call_github_models(base_url, token, model, prompt, max_retries=max_retries)
            except Exception as e:  # BackendError 等 → 次のバックエンドへ
                last = e
                log(f"backend {b} failed: {e}")
        raise RuntimeError(f"all backends failed: {last}")

    return translate


def clean_headline(subject: str) -> str:
    """件名から先頭の絵文字・記号と 'Axios XX:' プレフィックスを除いた見出しを返す。"""
    s = subject.strip()
    # 先頭の絵文字・記号類を除去
    s = re.sub(r'^[^\w぀-ヿ一-鿿(]+', '', s).strip()
    # 'Axios AM:' / 'Axios Pro Rata:' 等のプレフィックスを除去
    s = re.sub(r'^Axios\s+[^:：]{1,30}[:：]\s*', '', s).strip()
    return s or subject.strip()


def parse_members(blob: str):
    """EMAIL_BODY_START..END 内のメンバーブロックを (label, subject, body) で返す。"""
    m = re.search(r'EMAIL_BODY_START\s*(.*?)\s*EMAIL_BODY_END', blob, re.DOTALL)
    body_region = m.group(1) if m else blob
    members = []
    cur = None
    buf = []
    for line in body_region.splitlines():
        mk = MEMBER_RE.match(line)
        if mk:
            if cur is not None:
                members.append((cur[0], cur[1], "\n".join(buf).strip()))
            cur = (mk.group("label"), mk.group("subject"))
            buf = []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        members.append((cur[0], cur[1], "\n".join(buf).strip()))
    return [(l, s, b) for (l, s, b) in members if b]


def member_body_prompt(label: str, body: str) -> str:
    pro_rata = ""
    if "Pro Rata" in label:
        pro_rata = (
            "- ディール一覧（The BFD / Venture Capital Deals / Private Equity Deals / "
            "Public Offerings / Liquidity Events / More M&A / Fundraising / It's Personnel / "
            "Final Numbers 等）は散文化せず「- 」始まりの箇条書きのまま和訳する。\n"
            "  企業名・投資家名・ティッカー・金額（$50m / $8.4b / €6m 等）・axios.link URL は原文表記のまま転記する。\n"
        )
    return (
        f"あなたはAxiosニュースレターの専門翻訳者です。以下の英語ニュースレター「{label}」の本文を"
        "日本語に翻訳してください。対象読者はC-levelエグゼクティブ・機関投資家。\n\n"
        "【出力ルール（厳守）】\n"
        "- 本文の翻訳のみを出力する。front matter・記事タイトル・エグゼクティブサマリー・英語原文・絵文字は一切出力しない。\n"
        "- 小見出しが必要なら ### を使う（## は使わない）。箇条書きは「- 」で保持する。\n"
        "- Smart Brevity ラベルは和訳して残す：Why it matters→なぜ重要か / The big picture→全体像 / "
        "Driving the news→ニュースの要点 / Between the lines→行間 / By the numbers→数字で見る / "
        "The bottom line→結論 / What they're saying→関係者の声 / Zoom in→詳細。\n"
        "- スポンサー枠・配信フッター・購読導線が混じっていても訳さず除外する。\n"
        f"{pro_rata}"
        "\n【本文】\n"
        f"{body}\n"
    )


def translate_member_body(translate, label: str, body: str, chunk_limit: int, sleep_sec: float) -> str:
    chunks = tg.split_into_chunks(body, chunk_limit) if len(body) > chunk_limit else [body]
    out_parts = []
    for i, ch in enumerate(chunks):
        if i > 0:
            time.sleep(sleep_sec)
        res = translate(member_body_prompt(label, ch))
        res = tg.strip_code_fences(res).strip()
        # 念のため front matter が混入したら除去
        _, res = tg.extract_front_matter(res)
        out_parts.append(res.strip())
    return "\n\n".join(p for p in out_parts if p)


def translate_headline(translate, headline: str) -> str:
    if not headline:
        return ""
    prompt = (
        "次のニュースレターの見出しを自然な日本語に訳してください。"
        "訳文のみを1行で出力（絵文字・引用符・原文・説明は不要）。\n"
        f"見出し: {headline}\n"
    )
    try:
        out = tg.strip_code_fences(translate(prompt)).strip()
        out = out.splitlines()[0].strip() if out else headline
        return out.strip('"“”「」').strip()
    except Exception as e:
        log(f"headline translate failed ({headline}): {e}")
        return headline


def main():
    if len(sys.argv) < 3:
        print("Usage: translate_axios.py <source> <date>", file=sys.stderr)
        sys.exit(1)
    source, date = sys.argv[1], sys.argv[2]
    if source not in SOURCE_MAP:
        print(f"Unknown axios source: {source}", file=sys.stderr)
        sys.exit(1)
    display, category = SOURCE_MAP[source]

    blob = sys.stdin.read()
    members = parse_members(blob)
    if not members:
        print("No members parsed from input", file=sys.stderr)
        sys.exit(1)
    log(f"{source}: {len(members)} member(s)")

    chunk_limit = int(os.environ.get("CHUNK_CHAR_LIMIT", tg.DEFAULT_CHUNK_CHAR_LIMIT))
    sleep_sec = float(os.environ.get("CHUNK_SLEEP_SEC", tg.DEFAULT_CHUNK_SLEEP_SEC))
    translate = build_fallback()

    y, mo, d = date.split("-")
    date_ja = f"{y}年{mo}月{d}日"

    sections = []      # (label, ja_headline, ja_body)
    for idx, (label, subject, body) in enumerate(members):
        if idx > 0:
            time.sleep(sleep_sec)
        headline = clean_headline(subject)
        ja_head = translate_headline(translate, headline)
        ja_body = translate_member_body(translate, label, body, chunk_limit, sleep_sec)
        sections.append((label, ja_head, ja_body))
        log(f"  done: {label} -> {ja_head[:30]}")

    # summary（hero画像キーワード生成用）: 各メンバー見出しを連結し60字以内
    summary = "／".join(h for _, h, _ in sections if h)[:60]

    # 出力組み立て
    out = []
    out.append("---")
    out.append(f'title: "{display}｜{date_ja}"')
    out.append(f"date: {date}")
    out.append(f'categories: ["{category}"]')
    out.append('tags: ["Axios"]')
    out.append('original_url: "https://www.axios.com/newsletters"')
    out.append(f'summary: "{summary}"')
    out.append("---")
    out.append("")
    out.append("## エグゼクティブサマリー")
    out.append("")
    out.append("| # | 配信 | 見出し |")
    out.append("|---|------|--------|")
    for i, (label, ja_head, _) in enumerate(sections, 1):
        out.append(f"| {i} | {label} | {ja_head} |")
    out.append("")
    for label, ja_head, ja_body in sections:
        out.append(f"## {label}：{ja_head}")
        out.append("")
        out.append(ja_body)
        out.append("")

    sys.stdout.write("\n".join(out).rstrip() + "\n")


if __name__ == "__main__":
    main()
