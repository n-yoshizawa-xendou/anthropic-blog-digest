# 📰 Anthropic ブログダイジェスト

Anthropic社のブログ記事を、非エンジニアでもわかりやすい日本語で自動要約する[サイト](https://n-yoshizawa-xendou.github.io/anthropic-blog-digest/)です。

## 🔧 仕組み

1. **毎日自動実行** — GitHub Actionsが毎日0時(JST)に起動
2. **記事を収集** — Anthropicのsitemap.xmlから新しいブログ記事を検出
3. **AIで要約** — Claude APIを使い、専門用語を避けたわかりやすい日本語に翻訳・要約
4. **サイト公開** — GitHub Pagesに静的HTMLとしてデプロイ

## 🚀 セットアップ

### 1. リポジトリのSecrets設定

GitHub リポジトリの **Settings → Secrets and variables → Actions** で以下を設定:

| Secret名 | 説明 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic APIキー（[取得はこちら](https://console.anthropic.com/)） |

### 2. GitHub Pages の有効化

**Settings → Pages** で:
- **Source**: `GitHub Actions` を選択

### 3. 手動実行（初回）

**Actions → Daily Blog Digest → Run workflow** から手動実行できます。

## 📁 ファイル構成

```
├── .github/workflows/daily-digest.yml  # GitHub Actions ワークフロー
├── scripts/
│   ├── fetch_articles.py               # 記事取得
│   ├── summarize.py                    # Claude API 要約
│   └── generate_site.py               # HTML生成
├── templates/                          # Jinja2 テンプレート
├── static/                             # CSS
├── data/articles.json                  # 処理済み記事データ
└── requirements.txt
```

## 🔑 必要な外部サービス

- **Anthropic API** — 記事の要約生成に使用（[料金](https://www.anthropic.com/pricing)）
  - 1記事あたり約$0.01〜0.03（Claude Sonnet使用時）

## ローカル実行

```bash
# 依存インストール
pip install -r requirements.txt

# 環境変数を設定
export ANTHROPIC_API_KEY="your-api-key"

# 記事取得＆要約（最大5件）
cd scripts && python summarize.py 5

# サイト生成
python generate_site.py

# 確認
open ../docs/index.html
```

## ライセンス

MIT
