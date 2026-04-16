#!/usr/bin/env python3
"""Gmail OAuth2 Refresh Token 取得スクリプト
ブラウザで許可するだけで refresh_token を自動取得します。
"""
import http.server
import urllib.request
import urllib.parse
import json
import webbrowser
import sys
import os

CLIENT_ID = os.environ.get("GMAIL_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GMAIL_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080"
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

auth_code = None

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("✅ 認証成功！このタブを閉じてターミナルに戻ってください。".encode("utf-8"))
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("❌ エラーが発生しました。".encode("utf-8"))
    def log_message(self, format, *args):
        pass  # ログ抑制

def main():
    # 1. ローカルサーバー起動
    server = http.server.HTTPServer(("localhost", 8080), Handler)

    # 2. ブラウザで認証画面を開く
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope={SCOPE}"
        f"&access_type=offline&prompt=consent"
    )
    print("🌐 ブラウザで Google 認証画面を開きます...")
    webbrowser.open(auth_url)

    # 3. コールバックを待つ
    print("⏳ ブラウザで許可してください（待機中）...")
    server.handle_request()
    server.server_close()

    if not auth_code:
        print("❌ 認証コードを取得できませんでした")
        sys.exit(1)

    print("✅ 認証コード取得成功")

    # 4. refresh_token に交換
    print("🔄 Refresh Token を取得中...")
    data = urllib.parse.urlencode({
        "code": auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode("utf-8")

    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"❌ トークン交換エラー: {body}")
        sys.exit(1)

    refresh_token = result.get("refresh_token")
    if not refresh_token:
        print(f"❌ refresh_token が返ってきませんでした: {json.dumps(result, indent=2)}")
        sys.exit(1)

    # 5. 結果表示
    print("\n" + "=" * 60)
    print("🎉 成功！以下の値を GitHub Secrets に登録してください：")
    print("=" * 60)
    print(f"\nGMAIL_CLIENT_ID:\n  {CLIENT_ID}\n")
    print(f"GMAIL_CLIENT_SECRET:\n  {CLIENT_SECRET}\n")
    print(f"GMAIL_REFRESH_TOKEN:\n  {refresh_token}\n")
    print("=" * 60)

if __name__ == "__main__":
    main()
