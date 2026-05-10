"""Anthropic / Claude のブログ記事を取得するスクリプト

複数のソースに対応:
- anthropic: https://www.anthropic.com/news/<slug>  (sitemap.xml ベース)
- claude:    https://claude.com/blog/<slug>        (一覧HTMLスクレイプ)

各記事は (source, slug) の複合キーで識別する。
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

ANTHROPIC_SITEMAP_URL = "https://www.anthropic.com/sitemap.xml"
ANTHROPIC_NEWS_PREFIX = "https://www.anthropic.com/news/"
CLAUDE_BLOG_INDEX_URL = "https://claude.com/blog"
CLAUDE_BLOG_PREFIX = "https://claude.com/blog/"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AnthropicBlogDigest/1.0)"
}

# /news, /blog ルート (一覧ページ) は除外
EXCLUDE_SLUGS = {""}


def article_key(source: str, slug: str) -> str:
    return f"{source}:{slug}"


def load_existing_articles() -> dict:
    if ARTICLES_FILE.exists():
        return json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    return {}


def save_articles(articles: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLES_FILE.write_text(
        json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def fetch_anthropic_entries() -> list[dict]:
    """anthropic.com の sitemap.xml から /news/ 配下のエントリを返す"""
    resp = requests.get(ANTHROPIC_SITEMAP_URL, timeout=30)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)

    entries = []
    for url_elem in root.findall("sm:url", NS):
        loc = url_elem.findtext("sm:loc", default="", namespaces=NS)
        lastmod = url_elem.findtext("sm:lastmod", default="", namespaces=NS)

        if not loc.startswith(ANTHROPIC_NEWS_PREFIX):
            continue

        slug = loc[len(ANTHROPIC_NEWS_PREFIX):].strip("/")
        if not slug or slug in EXCLUDE_SLUGS:
            continue

        entries.append({
            "source": "anthropic",
            "url": loc,
            "slug": slug,
            "lastmod": lastmod,
        })

    return entries


def fetch_claude_entries() -> list[dict]:
    """claude.com/blog のトップHTMLから /blog/<slug> リンクを抽出する

    sitemap が提供されていないため、初期描画HTMLに含まれている
    最新数十件のみを対象とする。それ以前は JS ページネーションが必要。
    """
    try:
        resp = requests.get(CLAUDE_BLOG_INDEX_URL, timeout=30, headers=REQUEST_HEADERS)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [WARN] Failed to fetch claude blog index: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    seen = set()
    entries = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/blog/"):
            slug = href[len("/blog/"):].strip("/")
        elif href.startswith(CLAUDE_BLOG_PREFIX):
            slug = href[len(CLAUDE_BLOG_PREFIX):].strip("/")
        else:
            continue

        if not slug or "/" in slug or slug in EXCLUDE_SLUGS:
            continue
        if slug in seen:
            continue
        seen.add(slug)

        entries.append({
            "source": "claude",
            "url": f"{CLAUDE_BLOG_PREFIX}{slug}",
            "slug": slug,
            "lastmod": "",  # 一覧HTMLには載らない。後段で published を流用
        })

    return entries


def _normalize_date(value: str) -> str:
    """様々な日付表記を ISO 8601 (YYYY-MM-DD) に寄せる。失敗時は元の値を返す。"""
    value = (value or "").strip()
    if not value:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.date().isoformat() if fmt != "%Y-%m-%dT%H:%M:%S%z" else dt.isoformat()
        except ValueError:
            continue
    return value


def _clean_title(title: str) -> str:
    """OGタイトル末尾の "| サイト名" を除去する"""
    title = (title or "").strip()
    # 末尾の " | <something>" を一段だけ落とす
    return re.sub(r"\s*\|\s*[^|]+$", "", title).strip() or title


def _extract_jsonld_dates(soup: BeautifulSoup) -> tuple[str, str]:
    """JSON-LD から datePublished / dateModified を取り出す"""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for d in candidates:
            if not isinstance(d, dict):
                continue
            published = d.get("datePublished") or ""
            modified = d.get("dateModified") or ""
            if published or modified:
                return _normalize_date(published), _normalize_date(modified)
    return "", ""


def extract_article_content(url: str) -> dict | None:
    """記事ページから本文・タイトル・公開日を抽出する"""
    try:
        resp = requests.get(url, timeout=30, headers=REQUEST_HEADERS)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [WARN] Failed to fetch {url}: {e}", file=sys.stderr)
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"]
    elif soup.title:
        title = soup.title.string or ""
    title = _clean_title(title)

    description = ""
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        description = og_desc["content"]

    published = ""
    modified = ""
    time_tag = soup.find("time")
    if time_tag:
        published = time_tag.get("datetime", time_tag.get_text(strip=True))
    if not published:
        meta_date = soup.find("meta", property="article:published_time")
        if meta_date and meta_date.get("content"):
            published = meta_date["content"]
    if not published:
        published, modified = _extract_jsonld_dates(soup)

    published = _normalize_date(published)

    body_text = ""
    for container_tag in ["article", "main", "body"]:
        container = soup.find(container_tag)
        if container:
            for tag in container.find_all(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            body_text = container.get_text(separator="\n", strip=True)
            break

    body_text = re.sub(r"\n{3,}", "\n\n", body_text)

    if len(body_text) < 100:
        print(f"  [WARN] Very short content for {url} ({len(body_text)} chars)", file=sys.stderr)
        return None

    return {
        "title": title.strip(),
        "description": description.strip(),
        "published": published.strip(),
        "modified": (modified or "").strip(),
        "body": body_text[:15000],
    }


def fetch_all_entries() -> list[dict]:
    """全ソースのエントリをまとめて返す"""
    entries: list[dict] = []
    entries.extend(fetch_anthropic_entries())
    entries.extend(fetch_claude_entries())
    return entries


def find_new_articles(limit: int = 5) -> list[dict]:
    """新しい記事を見つけて本文を取得する"""
    existing = load_existing_articles()
    all_entries = fetch_all_entries()

    candidates: list[dict] = []
    for entry in all_entries:
        key = article_key(entry["source"], entry["slug"])
        if key in existing and existing[key].get("summarized"):
            continue
        candidates.append(entry)

    # lastmod が無い (claude) ものは末尾に来るが、後段で published で並べ替える
    candidates.sort(key=lambda x: x.get("lastmod", ""), reverse=True)

    results: list[dict] = []
    for entry in candidates:
        if len(results) >= limit:
            break
        print(f"Fetching: {entry['url']}")
        content = extract_article_content(entry["url"])
        if not content:
            continue
        merged = {**entry, **content}
        # claude 側は lastmod が無いので modified -> published の順で流用
        if not merged.get("lastmod"):
            merged["lastmod"] = merged.get("modified") or merged.get("published", "")
        results.append(merged)

    return results


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    articles = find_new_articles(limit=limit)
    print(f"\nFound {len(articles)} new article(s)")
    for a in articles:
        print(f"  - [{a['source']}] {a['title']} ({a['slug']})")
