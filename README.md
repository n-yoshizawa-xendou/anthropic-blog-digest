# 📰 Anthropic ブログダイジェスト

Anthropic / Claude のブログ記事を、非エンジニアでもわかりやすい日本語で自動要約する[サイト](https://n-yoshizawa-xendou.github.io/anthropic-blog-digest/)です。

## 🔧 仕組み

1. **毎日自動実行** — GitHub Actionsが毎日9時(JST)に起動
2. **記事を収集** — 以下の2ソースから新着記事を検出
   - `https://www.anthropic.com/news` (sitemap.xml ベース)
   - `https://claude.com/blog` (一覧HTMLスクレイプ。直近〜22件)
3. **AIで要約** — Claude APIを使い、専門用語を避けたわかりやすい日本語に翻訳・要約
4. **サイト公開** — GitHub Pagesに静的HTMLとしてデプロイ

記事は `(source, slug)` の複合キーで識別し、URL も `/articles/anthropic/<slug>/` と
`/articles/claude/<slug>/` に分かれて出力されます。

## 🚀 セットアップ

### 1. リポジトリのSecrets設定

GitHub リポジトリの **Settings → Secrets and variables → Actions** で以下を設定:

| Secret名 | 説明 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic APIキー（[取得はこちら](https://console.anthropic.com/)） |
| `SLACK_WEBHOOK_URL` | （任意）新着通知用 Slack Incoming Webhook URL。未設定なら通知をスキップ。 |

### 2. GitHub Pages の有効化

**Settings → Pages** で:
- **Source**: `GitHub Actions` を選択

### 3. 手動実行（初回）

**Actions → Daily Blog Digest → Run workflow** から手動実行できます。

## 📁 ファイル構成

```
├── .github/workflows/daily-digest.yml  # GitHub Actions ワークフロー
├── scripts/
│   ├── fetch_articles.py               # 記事取得 (anthropic + claude)
│   ├── summarize.py                    # Claude API 要約
│   ├── notify.py                       # Slack Incoming Webhook 通知
│   └── generate_site.py                # HTML生成
├── templates/                          # Jinja2 テンプレート
├── static/                             # CSS
├── data/articles.json                  # 処理済み記事データ ({source}:{slug} キー)
└── requirements.txt
```

## 🔔 Slack 通知

新着記事を要約したタイミングで Incoming Webhook に投稿します。

- 新着 0 件のときは投稿しません
- `SLACK_WEBHOOK_URL` が未設定の環境ではスキップされる（ローカル実行で安全）
- リンク先は本ダイジェストサイトの記事ページ (`/articles/<source>/<slug>/`) になります
- 必要なら環境変数 `DIGEST_BASE_URL` で公開先ドメインを上書きできます（デフォルトは GitHub Pages の URL）
- メッセージ例:
  ```
  *📰 新着 2 件のブログ記事*

  • <https://n-yoshizawa-xendou.github.io/anthropic-blog-digest/articles/anthropic/.../|タイトル>  _(anthropic.com)_
  • <https://n-yoshizawa-xendou.github.io/anthropic-blog-digest/articles/claude/.../|タイトル>     _(claude.com)_
  ```

## 🔑 必要な外部サービス

- **Anthropic API** — 記事の要約生成に使用（[料金](https://www.anthropic.com/pricing)）
  - 1記事あたり約$0.01〜0.03（Claude Sonnet使用時）
- **Slack Incoming Webhook**（任意） — 新着通知の投稿先

## ローカル実行

```bash
# 依存インストール
pip install -r requirements.txt

# 環境変数を設定
export ANTHROPIC_API_KEY="your-api-key"
# 任意: Slack 通知を有効化したいときだけ
# export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."

# 記事取得＆要約（最大5件）
cd scripts && python summarize.py 5

# サイト生成
python generate_site.py

# 確認
open ../docs/index.html
```

## ライセンス

MIT
