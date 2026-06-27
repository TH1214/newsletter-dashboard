# Axios メンバークエリ — Gmail MCP 検証済み（2026-06-27）

全12メンバーを Gmail MCP で実検証。SOURCES に転記する確定値。

| グループ | label | 確定クエリ | 検証メモ |
|---|---|---|---|
| axios-daily | Axios AM | `from:mike@axios.com subject:"Axios AM"` | AM版のみ。PM/FLと相互排他 ✓ |
| axios-daily | Axios PM | `from:mike@axios.com subject:"Axios PM"` | PM版のみ ✓ |
| axios-daily | Axios Finish Line | `from:mike@axios.com subject:"Finish Line"` | FL版のみ ✓ |
| axios-daily | Axios Closer | `from:closer@axios.com` | 単一送信者 |
| axios-daily | Axios Markets | `from:markets@axios.com` | 単一送信者 |
| axios-daily | Axios Macro | `from:macro@axios.com` | 単一送信者 |
| axios-ai | Axios Pro Rata | `from:axios.com subject:"Pro Rata"` | dan@ と lucinda.shen@(火) 両方ヒット。`from:dan@` だと火曜取りこぼし → sender-agnostic 採用 ✓ |
| axios-ai | Axios AI+ | `from:ai.plus@axios.com` | ai.plus.gov を巻き込まない ✓ |
| axios-ai | Axios AI+ Government | `from:ai.plus.gov@axios.com` | gov のみ ✓ |
| axios-frontier | Axios Mobility | `from:mobility@axios.com` | 週次(水) |
| axios-frontier | Axios Defense | `from:defense@axios.com` | 週次(水) |
| axios-frontier | Axios 2028 | `from:2028@axios.com` | 週次(日) |

## 本物 fetch_gmail.py 回収結果（リスク解消）

- session `b8685e2f`(2026-06-13) の最後の `gh secret set SECRET_FETCH_GMAIL_PY` 引数＝現行本番版を復元。
- 276行・14ソース・py_compile OK。262行base(a44ced5~1)との差分は3ソース追加(pere修正/maverick/hospitality-net)のみ＝本体無改変を確認。
- 出力形式: `EMAIL_SUBJECT:/EMAIL_DATE:/EMAIL_SOURCE:` + `EMAIL_BODY_START..END`。単一ソースの本文は**生HTML**（HTMLストリップは multi/cnbc のみ）。
- ヘルパ: `get_access_token()` / `gmail_api()` / `decode_body()` / `strip_and_truncate(text,max)`。
- date window: `date_override` 指定時は JST 00:00 を中心に -12h〜+27h。`config["query"]` に after:/before: を付加。

復元ファイル: `scratchpad/fetch_gmail_recovered.py`（このセッションの作業コピー）。
