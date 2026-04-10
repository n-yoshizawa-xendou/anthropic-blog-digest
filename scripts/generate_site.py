"""articles.json からHTMLサイトを生成するスクリプト"""

import json
import math
import re
import shutil
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"
OUTPUT_DIR = ROOT_DIR / "docs"

SITE_TITLE = "Anthropic ブログダイジェスト"
SITE_DESCRIPTION = "Anthropic社のブログ記事を非エンジニアにもわかりやすい日本語で紹介"
ARTICLES_PER_PAGE = 10
JST = timezone(timedelta(hours=9))

# 複合カテゴリを主要カテゴリに正規化するマッピング
PRIMARY_CATEGORY_MAP = {
    "AI技術": "AI技術",
    "パートナーシップ": "パートナーシップ",
    "企業ニュース": "企業ニュース",
    "安全性": "安全性",
    "セキュリティ": "安全性",
    "AI安全性": "安全性",
    "AI倫理": "安全性",
    "研究": "研究",
    "製品アップデート": "製品アップデート",
    "政策": "政策",
    "政策提言": "政策",
    "ポリシー": "政策",
    "規制": "政策",
    "規制対応": "政策",
    "AI政策": "政策",
    "プライバシー": "企業ニュース",
    "経済": "企業ニュース",
    "労働市場": "企業ニュース",
    "社会貢献": "企業ニュース",
    "社会責任": "企業ニュース",
    "グローバル展開": "企業ニュース",
    "事業拡大": "企業ニュース",
    "教育": "パートナーシップ",
    "オープンソース": "AI技術",
    "オープンソース化": "AI技術",
    "政府パートナーシップ": "パートナーシップ",
}


def normalize_category(raw_category: str) -> str:
    """複合カテゴリを主要カテゴリに正規化する"""
    parts = re.split(r"[、・,]", raw_category)
    first = parts[0].strip()
    return PRIMARY_CATEGORY_MAP.get(first, first)


def format_jst(date_str: str) -> str:
    """ISO 8601 日時文字列を JST yyyy-MM-dd HH:mm 形式に変換する"""
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.astimezone(JST).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        # 日付のみ (yyyy-MM-dd) の場合はそのまま返す
        return date_str


def load_articles() -> list[dict]:
    articles_file = DATA_DIR / "articles.json"
    if not articles_file.exists():
        return []
    data = json.loads(articles_file.read_text(encoding="utf-8"))
    articles = [v for v in data.values() if isinstance(v, dict) and v.get("summarized")]
    for article in articles:
        article["category_normalized"] = normalize_category(
            article.get("category", "その他")
        )
        article["display_date"] = format_jst(
            article.get("published") or article.get("lastmod", "")
        )
    # 新しい順にソート
    articles.sort(key=lambda x: x.get("lastmod", x.get("published", "")), reverse=True)
    return articles


def generate_site():
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )

    # 出力ディレクトリをクリーンアップ
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    (OUTPUT_DIR / "articles").mkdir()

    # 静的ファイルをコピー
    if STATIC_DIR.exists():
        for f in STATIC_DIR.iterdir():
            shutil.copy2(f, OUTPUT_DIR / f.name)

    articles = load_articles()
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    # 正規化済みカテゴリ一覧を件数付きで生成
    cat_counts = Counter(a["category_normalized"] for a in articles)
    categories = sorted(cat_counts.keys())
    category_data = [{"name": c, "count": cat_counts[c]} for c in categories]

    # ページネーション
    total_pages = max(1, math.ceil(len(articles) / ARTICLES_PER_PAGE))

    index_template = env.get_template("index.html")
    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * ARTICLES_PER_PAGE
        end = start + ARTICLES_PER_PAGE
        page_articles = articles[start:end]

        # ページ1は index.html、2以降は page/N/index.html
        if page_num == 1:
            base_path = ""
            out_file = OUTPUT_DIR / "index.html"
        else:
            base_path = f"../../"
            page_dir = OUTPUT_DIR / "page" / str(page_num)
            page_dir.mkdir(parents=True, exist_ok=True)
            out_file = page_dir / "index.html"

        page_html = index_template.render(
            site_title=SITE_TITLE,
            site_description=SITE_DESCRIPTION,
            articles=page_articles,
            categories=category_data,
            updated_at=now,
            total_count=len(articles),
            current_page=page_num,
            total_pages=total_pages,
            base_path=base_path,
        )
        out_file.write_text(page_html, encoding="utf-8")

    # 各記事ページ
    article_template = env.get_template("article.html")
    for article in articles:
        article_html = article_template.render(
            site_title=SITE_TITLE,
            article=article,
            updated_at=now,
        )
        article_dir = OUTPUT_DIR / "articles" / article["slug"]
        article_dir.mkdir(parents=True, exist_ok=True)
        (article_dir / "index.html").write_text(article_html, encoding="utf-8")

    print(f"Generated site with {len(articles)} articles, {total_pages} pages in {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_site()
