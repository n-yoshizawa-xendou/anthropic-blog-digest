"""Claude API を使って記事を非エンジニア向けの日本語に要約するスクリプト"""

import json
import os
import sys
from pathlib import Path

import anthropic

from fetch_articles import find_new_articles, load_existing_articles, save_articles

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
あなたはテクノロジーニュースの翻訳・要約の専門家です。
Anthropic社のブログ記事を、ITに詳しくない一般の日本人読者向けにわかりやすく要約してください。

ルール:
- 日本語で書いてください
- 専門用語は避けるか、使う場合は簡単な説明を括弧内に添えてください
- 要約は300〜600文字程度にしてください
- 記事の要点を3〜5個の箇条書きでまとめた「ポイント」セクションも作成してください
- 身近な例え話を1つ入れて、技術的な内容をわかりやすくしてください
- 出力はJSON形式で返してください

出力フォーマット (JSON):
{
  "title_ja": "日本語タイトル",
  "summary": "要約テキスト（300〜600文字）",
  "points": ["ポイント1", "ポイント2", "ポイント3"],
  "analogy": "身近な例え話",
  "category": "カテゴリ（例: AI技術, 企業ニュース, 安全性, 製品アップデート, 研究, パートナーシップ）"
}\
"""


def summarize_article(client: anthropic.Anthropic, article: dict) -> dict | None:
    """1記事をClaude APIで要約"""
    user_message = f"""以下のAnthropicブログ記事を要約してください。

タイトル: {article['title']}
説明: {article.get('description', '')}
URL: {article['url']}
公開日: {article.get('published', '')}

本文:
{article['body']}
"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text

        # JSON部分を抽出
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(text[json_start:json_end])
        else:
            print(f"  [WARN] Could not extract JSON from response", file=sys.stderr)
            return None

    except Exception as e:
        print(f"  [ERROR] API call failed: {e}", file=sys.stderr)
        return None


def process_new_articles(limit: int = 5) -> int:
    """新しい記事を取得・要約してdata/articles.jsonに保存"""
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    articles = find_new_articles(limit=limit)

    if not articles:
        print("No new articles found.")
        return 0

    existing = load_existing_articles()
    processed = 0

    for article in articles:
        slug = article["slug"]
        print(f"\nSummarizing: {article['title']}")

        summary = summarize_article(client, article)
        if summary:
            existing[slug] = {
                "slug": slug,
                "url": article["url"],
                "title_original": article["title"],
                "title_ja": summary["title_ja"],
                "description": article.get("description", ""),
                "published": article.get("published", ""),
                "lastmod": article.get("lastmod", ""),
                "summary": summary["summary"],
                "points": summary["points"],
                "analogy": summary.get("analogy", ""),
                "category": summary.get("category", "その他"),
                "summarized": True,
            }
            processed += 1
            print(f"  ✓ {summary['title_ja']}")
        else:
            print(f"  ✗ Failed to summarize")

    save_articles(existing)
    print(f"\nProcessed {processed}/{len(articles)} articles")
    return processed


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    count = process_new_articles(limit=limit)
    print(f"Done. {count} article(s) summarized.")
