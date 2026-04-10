"""Anthropic のブログ記事を sitemap.xml から取得するスクリプト"""

import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

SITEMAP_URL = "https://www.anthropic.com/sitemap.xml"
NEWS_PREFIX = "https://www.anthropic.com/news/"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"

# sitemap.xml の名前空間
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# /news ルート (一覧ページ) は除外
EXCLUDE_SLUGS = {""}


def load_existing_articles() -> dict:
    if ARTICLES_FILE.exists():
        return json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    return {}


def save_articles(articles: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLES_FILE.write_text(
        json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def fetch_sitemap_news_urls() -> list[dict]:
    """sitemap.xml から /news/ 配下の URL と lastmod を取得"""
    resp = requests.get(SITEMAP_URL, timeout=30)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)

    entries = []
    for url_elem in root.findall("sm:url", NS):
        loc = url_elem.findtext("sm:loc", default="", namespaces=NS)
        lastmod = url_elem.findtext("sm:lastmod", default="", namespaces=NS)

        if not loc.startswith(NEWS_PREFIX):
            continue

        slug = loc[len(NEWS_PREFIX):].strip("/")
        if not slug or slug in EXCLUDE_SLUGS:
            continue

        entries.append({"url": loc, "slug": slug, "lastmod": lastmod})

    return entries


def extract_article_content(url: str) -> dict | None:
    """記事ページから本文とタイトルを抽出"""
    try:
        resp = requests.get(url, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AnthropicBlogDigest/1.0)"
        })
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [WARN] Failed to fetch {url}: {e}", file=sys.stderr)
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # タイトル取得
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"]
    elif soup.title:
        title = soup.title.string or ""

    # 説明文取得
    description = ""
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        description = og_desc["content"]

    # 公開日取得
    published = ""
    time_tag = soup.find("time")
    if time_tag:
        published = time_tag.get("datetime", time_tag.get_text(strip=True))

    # 本文抽出: article タグ or main タグ内のテキスト
    body_text = ""
    for container_tag in ["article", "main", "body"]:
        container = soup.find(container_tag)
        if container:
            # スクリプトやスタイルを除去
            for tag in container.find_all(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            body_text = container.get_text(separator="\n", strip=True)
            break

    # テキストの前処理: 連続空行を削減
    body_text = re.sub(r"\n{3,}", "\n\n", body_text)

    # 最低限のコンテンツがあるか確認
    if len(body_text) < 100:
        print(f"  [WARN] Very short content for {url} ({len(body_text)} chars)", file=sys.stderr)
        return None

    return {
        "title": title.strip(),
        "description": description.strip(),
        "published": published.strip(),
        "body": body_text[:15000],  # Claude API のトークン制限を考慮
    }


def find_new_articles(limit: int = 5) -> list[dict]:
    """新しい記事を見つけて本文を取得"""
    existing = load_existing_articles()
    sitemap_entries = fetch_sitemap_news_urls()

    new_articles = []
    for entry in sitemap_entries:
        slug = entry["slug"]
        if slug in existing and existing[slug].get("summarized"):
            continue
        new_articles.append(entry)

    # 最新のもの(lastmod降順)から limit 件取得
    new_articles.sort(key=lambda x: x.get("lastmod", ""), reverse=True)
    new_articles = new_articles[:limit]

    results = []
    for entry in new_articles:
        print(f"Fetching: {entry['url']}")
        content = extract_article_content(entry["url"])
        if content:
            results.append({**entry, **content})

    return results


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    articles = find_new_articles(limit=limit)
    print(f"\nFound {len(articles)} new article(s)")
    for a in articles:
        print(f"  - {a['title']} ({a['slug']})")
