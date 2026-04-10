"""articles.json からHTMLサイトを生成するスクリプト"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"
OUTPUT_DIR = ROOT_DIR / "docs"

SITE_TITLE = "Anthropic ブログダイジェスト"
SITE_DESCRIPTION = "Anthropic社のブログ記事を非エンジニアにもわかりやすい日本語で紹介"
SITE_URL = ""  # GitHub Pages URL はデプロイ時に設定


def load_articles() -> list[dict]:
    articles_file = DATA_DIR / "articles.json"
    if not articles_file.exists():
        return []
    data = json.loads(articles_file.read_text(encoding="utf-8"))
    articles = [v for v in data.values() if isinstance(v, dict) and v.get("summarized")]
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
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # カテゴリ一覧を生成
    categories = sorted(set(a.get("category", "その他") for a in articles))

    # インデックスページ
    index_template = env.get_template("index.html")
    index_html = index_template.render(
        site_title=SITE_TITLE,
        site_description=SITE_DESCRIPTION,
        articles=articles,
        categories=categories,
        updated_at=now,
        total_count=len(articles),
    )
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")

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

    print(f"Generated site with {len(articles)} articles in {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_site()
