#!/usr/bin/env python3
"""Gmail からニュースレターを取得するスクリプト。
GitHub Actions 上で実行される。環境変数で認証情報を受け取る。

Usage:
    python scripts/fetch_gmail.py <source>

    source: wsj | nyt-bn | short-squeez | skift | buysiders | nyt-op | business-insider

Output:
    取得したメール本文を stdout に出力。
    メタ情報（subject, date）は先頭に YAML-like ヘッダで出力。
"""
import sys
import os
import json
import base64
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta

# ── 設定 ──────────────────────────────────────────
SOURCES = {
    "wsj": {
        "query": 'from:wsj.com subject:"The 10-Point"',
        "label": "WSJ The 10-Point",
    },
    "nyt-bn": {
        "query": 'from:nytimes.com subject:"Breaking News"',
        "label": "NYT Breaking News",
    },
    "short-squeez": {
        "query": 'from:shortsqueez.co "Overheard on Wall Street"',
        "label": "Short Squeez OWS",
    },
    "skift": {
        "query": 'from:email.skift.com',
        "label": "Skift The Daily",
    },
    "buysiders": {
        "query": 'from:buysiders.co',
        "label": "Buysiders Deal Report",
    },
    "nyt-op": {
        "query": 'from:nytimes.com subject:"Opinion Today"',
        "label": "NYT Opinion Today",
    },
    "business-insider": {
        "query": 'from:businessinsider.com subject:"Today"',
        "label": "Business Insider",
    },
}


def get_access_token():
    """refresh_token から access_token を取得"""
    client_id = os.environ["GMAIL_CLIENT_ID"]
    client_secret = os.environ["GMAIL_CLIENT_SECRET"]
    refresh_token = os.environ["GMAIL_REFRESH_TOKEN"]

    # デバッグ: 認証情報の先頭・末尾を表示（秘密情報はマスク）
    print(f"[auth] client_id: {client_id[:20]}...{client_id[-5:]}", file=sys.stderr)
    print(f"[auth] client_secret: {client_secret[:8]}...{client_secret[-4:]}", file=sys.stderr)
    print(f"[auth] refresh_token: {refresh_token[:15]}...{refresh_token[-6:]} (len={len(refresh_token)})", file=sys.stderr)

    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")

    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["access_token"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"[auth] Token refresh failed: {e.code} {error_body}", file=sys.stderr)
        sys.exit(1)


def gmail_api(access_token, endpoint, params=None):
    """Gmail REST API を呼び出す"""
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"API Error: {e.code} {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def decode_body(payload):
    """メール本文をデコードする（再帰的にパーツを探索）"""
    # 直接 body がある場合
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    # multipart の場合、text/plain → text/html の順で探す
    parts = payload.get("parts", [])

    # まず text/plain を探す
    for part in parts:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

    # text/html を探す
    for part in parts:
        if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

    # ネストされた multipart を再帰的に探す
    for part in parts:
        if part.get("parts"):
            result = decode_body(part)
            if result:
                return result

    return ""


def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_gmail.py <source> [YYYY-MM-DD]", file=sys.stderr)
        sys.exit(1)

    source = sys.argv[1]
    date_override = sys.argv[2] if len(sys.argv) >= 3 else None

    if source not in SOURCES:
        print(f"Unknown source: {source}. Available: {', '.join(SOURCES.keys())}", file=sys.stderr)
        sys.exit(1)

    config = SOURCES[source]

    jst = timezone(timedelta(hours=9))

    if date_override:
        # 指定日の JST 00:00〜翌日 03:00 (深夜配信を含む) を検索
        target = datetime.strptime(date_override, "%Y-%m-%d").replace(tzinfo=jst)
        after_epoch = int(target.timestamp())
        before_epoch = int((target + timedelta(hours=27)).timestamp())
        query = f'{config["query"]} after:{after_epoch} before:{before_epoch}'
    else:
        # デフォルト: 過去36時間
        now = datetime.now(jst)
        after_epoch = int((now - timedelta(hours=36)).timestamp())
        query = f'{config["query"]} after:{after_epoch}'

    print(f"[fetch] Searching: {query}", file=sys.stderr)

    access_token = get_access_token()

    # メール検索
    results = gmail_api(access_token, "messages", {"q": query, "maxResults": "1"})
    messages = results.get("messages", [])

    if not messages:
        print(f"[fetch] No messages found for {source}", file=sys.stderr)
        print("NO_EMAIL_FOUND")
        sys.exit(0)

    msg_id = messages[0]["id"]
    print(f"[fetch] Found message: {msg_id}", file=sys.stderr)

    # メール本文を取得
    msg = gmail_api(access_token, f"messages/{msg_id}", {"format": "full"})

    # ヘッダからsubjectとdateを抽出
    headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
    subject = headers.get("subject", "No Subject")
    date_str = headers.get("date", "")

    # 本文をデコード
    body = decode_body(msg["payload"])

    if not body:
        print(f"[fetch] Warning: Empty body for {source}", file=sys.stderr)
        body = msg.get("snippet", "")

    # 出力
    print(f"EMAIL_SUBJECT: {subject}")
    print(f"EMAIL_DATE: {date_str}")
    print(f"EMAIL_SOURCE: {config['label']}")
    print("EMAIL_BODY_START")
    print(body)
    print("EMAIL_BODY_END")


if __name__ == "__main__":
    main()
