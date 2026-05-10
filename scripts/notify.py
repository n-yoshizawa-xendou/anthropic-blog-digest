"""Slack Incoming Webhook で新着記事を通知するモジュール

SLACK_WEBHOOK_URL が環境変数に無い場合は静かにスキップするため、
ローカル実行や Webhook 未設定の状態でもスクリプト全体は壊れない。
"""

import json
import os
import sys
from urllib import error, request

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

SOURCE_LABELS = {
    "anthropic": "anthropic.com",
    "claude": "claude.com",
}


def _escape_mrkdwn(text: str) -> str:
    """Slack mrkdwn のリンクラベルで誤動作する文字をエスケープする"""
    return (text or "").replace("<", "‹").replace(">", "›").replace("|", "/")


def build_message(articles: list[dict]) -> str:
    count = len(articles)
    lines = [f"*📰 新着 {count} 件のブログ記事*", ""]
    for a in articles:
        source = a.get("source", "anthropic")
        label = SOURCE_LABELS.get(source, source)
        title = _escape_mrkdwn(
            a.get("title_ja") or a.get("title_original") or a.get("slug", "")
        )
        url = a.get("url", "")
        lines.append(f"• <{url}|{title}>  _({label})_")
    return "\n".join(lines)


def notify_new_articles(articles: list[dict]) -> bool:
    """新着記事リストを Slack に投稿する。成功時 True。"""
    if not articles:
        return False
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set — skip Slack notification")
        return False

    payload = {"text": build_message(articles)}
    req = request.Request(
        SLACK_WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            if resp.status >= 300:
                print(f"  [WARN] Slack webhook returned {resp.status}", file=sys.stderr)
                return False
    except (error.URLError, error.HTTPError, TimeoutError) as e:
        print(f"  [WARN] Slack notification failed: {e}", file=sys.stderr)
        return False

    print(f"Slack: notified {len(articles)} new article(s)")
    return True


if __name__ == "__main__":
    # 動作確認用: ダミー記事で投稿
    sample = [
        {
            "source": "anthropic",
            "title_ja": "サンプル記事",
            "url": "https://www.anthropic.com/news/example",
        },
        {
            "source": "claude",
            "title_ja": "Claude側のサンプル",
            "url": "https://claude.com/blog/example",
        },
    ]
    notify_new_articles(sample)
