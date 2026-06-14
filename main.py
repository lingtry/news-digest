#!/usr/bin/env python3
"""
IT & AI 资讯定时推送系统
每3小时自动抓取 RSS 新闻源，汇总后通过邮件发送。
运行在 GitHub Actions 上，完全免费，7×24 小时无人值守。
"""

import feedparser
import smtplib
import ssl
import html as html_module
import os
import re
import time
import hashlib
import json
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from collections import OrderedDict
import xml.etree.ElementTree as ET

# ============================================================
# 配置 — 通过 GitHub Secrets / 环境变量传入
# ============================================================

EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "")       # QQ邮箱地址
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")     # QQ邮箱 SMTP 授权码
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")   # 接收邮件的邮箱
MAX_ARTICLES_PER_SOURCE = int(os.environ.get("MAX_ARTICLES_PER_SOURCE", "8"))
CACHE_TTL_HOURS = int(os.environ.get("CACHE_TTL_HOURS", "24"))  # 去重窗口

# AI 相关关键词（用于高亮标记 🔥）
AI_KEYWORDS = [
    "GPT", "GPT-5", "GPT-4", "Claude", "Gemini", "LLaMA", "Llama",
    "DeepSeek", "deepseek", "Qwen", "通义千问", "文心一言", "Kimi",
    "LLM", "large language model", "大语言模型", "大模型",
    "Transformer", "diffusion", "diffusion model", "扩散模型",
    "AGI", "artificial general intelligence", "通用人工智能",
    "RLHF", "reinforcement learning", "fine-tuning", "微调",
    "RAG", "retrieval augmented", "检索增强",
    "agent", "AI agent", "智能体", "AI Agent",
    "open source", "开源模型", "open weight",
    "NVIDIA", "nvidia", "GPU", "H100", "B200", "GB200",
    "CUDA", "TensorRT",
    "OpenAI", "openai", "Anthropic", "anthropic",
    "Google DeepMind", "DeepMind", "deepmind",
    "Stable Diffusion", "Midjourney", "DALL-E", "Sora",
    "embeddings", "vector database", "向量数据库",
    "multi-modal", "多模态", "multimodal",
    "attention", "attention mechanism",
    "neural network", "神经网络",
    "inference", "推理", "training", "训练",
    "token", "tokenizer", "context window", "上下文窗口",
    "AI safety", "alignment", "对齐", "安全",
    "copilot", "Copilot", "cursor",
    "robot", "机器人", "humanoid",
    "quantum", "量子",
]

# ============================================================
# RSS 新闻源配置
# ============================================================

RSS_SOURCES: Dict[str, List[Dict[str, str]]] = OrderedDict({
    "🤖 AI/ML 前沿": [
        {"name": "ArXiv CS.AI", "url": "http://export.arxiv.org/rss/cs.AI"},
        {"name": "ArXiv CS.LG (ML)", "url": "http://export.arxiv.org/rss/cs.LG"},
        {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml"},
        {"name": "OpenAI Blog", "url": "https://openai.com/blog/rss.xml"},
        {"name": "Google Research", "url": "https://blog.research.google/feeds/posts/default"},
        {"name": "MIT Tech Review - AI", "url": "https://www.technologyreview.com/feed/ai/"},
        {"name": "MarkTechPost (AI)", "url": "https://www.marktechpost.com/feed/"},
    ],
    "💻 IT / 科技": [
        {"name": "Hacker News", "url": "https://hnrss.org/frontpage?count=15"},
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
        {"name": "GitHub Trending", "url": "https://github.com/trending.atom"},
        {"name": "The Register", "url": "https://www.theregister.com/headlines.atom"},
    ],
    "🇨🇳 中文科技": [
        {"name": "36氪", "url": "https://36kr.com/feed"},
        {"name": "机器之心", "url": "https://www.jiqizhixin.com/rss"},
        {"name": "量子位", "url": "https://www.qbitai.com/feed"},
        {"name": "InfoQ 中文", "url": "https://www.infoq.cn/feed"},
        {"name": "IT之家", "url": "https://it之家.com/feed"},
    ],
})


# ============================================================
# 工具函数
# ============================================================

def strip_html(text: str) -> str:
    """去除 HTML 标签，保留纯文本"""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html_module.unescape(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def strip_markdown_links(text: str) -> str:
    """去除 Markdown 链接格式"""
    return re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", text)


def truncate(text: str, max_len: int = 200) -> str:
    """截断文本，在完整句子边界处截断"""
    text = strip_html(text)
    text = strip_markdown_links(text)
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # 尝试在最后一个句号处截断
    last_period = max(
        truncated.rfind("。"),
        truncated.rfind(". "),
        truncated.rfind("！"),
        truncated.rfind("? "),
        truncated.rfind("\n"),
    )
    if last_period > max_len // 2:
        return truncated[: last_period + 1]
    return truncated.rsplit(" ", 1)[0] + "…"


def extract_summary(entry, max_len: int = 180) -> str:
    """从 RSS entry 中提取摘要"""
    # 优先使用 summary
    if hasattr(entry, "summary") and entry.summary:
        return truncate(entry.summary, max_len)
    # 其次 description
    if hasattr(entry, "description") and entry.description:
        return truncate(entry.description, max_len)
    # 最后 content
    if hasattr(entry, "content") and entry.content:
        text = entry.content[0].get("value", "") if isinstance(entry.content, list) else str(entry.content)
        return truncate(text, max_len)
    return ""


def find_ai_keywords(text: str) -> List[str]:
    """检查文本是否包含 AI 相关关键词"""
    matched = []
    text_lower = text.lower()
    for kw in AI_KEYWORDS:
        if kw.lower() in text_lower:
            matched.append(kw)
    return matched


def article_id(title: str, link: str) -> str:
    """生成文章唯一标识（用于去重）"""
    return hashlib.md5(f"{title}{link}".encode()).hexdigest()


# ============================================================
# 缓存管理（去重）
# ============================================================

def load_sent_cache() -> Dict[str, float]:
    """加载已发送文章缓存"""
    cache_file = os.path.join(os.path.dirname(__file__), ".sent_cache.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_sent_cache(cache: Dict[str, float]):
    """保存缓存，清理过期条目"""
    cache_file = os.path.join(os.path.dirname(__file__), ".sent_cache.json")
    now = datetime.now().timestamp()
    ttl = CACHE_TTL_HOURS * 3600
    # 清理过期
    cache = {k: v for k, v in cache.items() if now - v < ttl}
    # 限制缓存大小
    if len(cache) > 5000:
        sorted_items = sorted(cache.items(), key=lambda x: x[1], reverse=True)
        cache = dict(sorted_items[:5000])
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    return cache


# ============================================================
# 新闻抓取
# ============================================================

def fetch_source(name: str, url: str, sent_cache: Dict[str, float]) -> List[Dict]:
    """抓取单个 RSS 源"""
    articles = []
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; NewsDigest/1.0; +https://github.com)",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            content = response.read()

        feed = feedparser.parse(content)

        if feed.bozo and not feed.entries:
            # XML 解析错误且没有条目，跳过
            return articles

        for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
            title = strip_html(entry.get("title", ""))
            link = entry.get("link", "")
            if not title or not link:
                continue

            aid = article_id(title, link)
            if aid in sent_cache:
                continue  # 已发送过，跳过

            summary = extract_summary(entry)

            # 发布时间
            published = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    dt = datetime(*entry.published_parsed[:6])
                    published = dt.strftime("%m-%d %H:%M")
                except Exception:
                    pass

            ai_tags = find_ai_keywords(f"{title} {summary}")

            articles.append({
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
                "source": name,
                "ai_tags": ai_tags,
                "id": aid,
            })

    except urllib.error.URLError as e:
        pass  # 网络错误，静默跳过该源
    except Exception as e:
        pass  # 其他错误也静默跳过

    return articles


def fetch_all_news(sent_cache: Dict[str, float]) -> Dict[str, List[Dict]]:
    """抓取所有新闻源"""
    results = OrderedDict()
    for category, sources in RSS_SOURCES.items():
        cat_articles = []
        for src in sources:
            articles = fetch_source(src["name"], src["url"], sent_cache)
            cat_articles.extend(articles)
            # 小延迟避免请求过快
            time.sleep(0.3)
        # 按时间排序（有时间的在前）
        cat_articles.sort(key=lambda a: a["published"], reverse=True)
        results[category] = cat_articles
    return results


# ============================================================
# 邮件构建
# ============================================================

def build_email_html(results: Dict[str, List[Dict]]) -> str:
    """构建 HTML 邮件内容"""
    now = datetime.now(timezone(timedelta(hours=8)))  # UTC+8
    total = sum(len(v) for v in results.values())
    ai_articles = []
    for cat_articles in results.values():
        for a in cat_articles:
            if a["ai_tags"]:
                ai_articles.append(a)

    # ---- CSS 样式 ----
    html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { margin:0; padding:0; background:#f0f2f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; }
  .container { max-width: 700px; margin: 0 auto; padding: 20px; }
  .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); color:#fff; padding: 32px 24px; border-radius: 12px 12px 0 0; text-align: center; }
  .header h1 { margin:0 0 6px 0; font-size: 26px; letter-spacing: 2px; }
  .header .subtitle { opacity: 0.8; font-size: 14px; margin: 0; }
  .header .time { opacity: 0.6; font-size: 12px; margin-top: 8px; }
  .stats { background: #fff; padding: 16px 24px; border-bottom: 1px solid #e8e8e8; display: flex; justify-content: space-around; text-align: center; flex-wrap: wrap; }
  .stats .stat-num { font-size: 28px; font-weight: bold; color: #0f3460; }
  .stats .stat-label { font-size: 12px; color: #888; margin-top: 2px; }
  .content { background: #fff; padding: 20px 24px; border-radius: 0 0 12px 12px; }
  .category { margin-bottom: 28px; }
  .cat-title { font-size: 18px; font-weight: bold; color: #1a1a2e; border-bottom: 2px solid #0f3460; padding-bottom: 6px; margin-bottom: 14px; }
  .article { padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
  .article:last-child { border-bottom: none; }
  .article .title { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
  .article .title a { color: #0f3460; text-decoration: none; }
  .article .title a:hover { text-decoration: underline; color: #e94560; }
  .article .meta { font-size: 11px; color: #999; margin-bottom: 4px; }
  .article .summary { font-size: 13px; color: #555; line-height: 1.6; }
  .tag { display: inline-block; background: #e94560; color: #fff; padding: 1px 7px; border-radius: 10px; font-size: 10px; margin-left: 4px; }
  .tag-ai { background: #ff6b35; }
  .hot-section { background: linear-gradient(135deg, #fff5f5, #fff0e6); border: 1px solid #ffcccc; border-radius: 10px; padding: 16px 20px; margin-bottom: 24px; }
  .hot-section .hot-title { font-size: 17px; font-weight: bold; color: #e94560; margin-bottom: 10px; }
  .footer { text-align: center; color: #aaa; font-size: 11px; margin-top: 20px; line-height: 1.8; }
  .footer a { color: #888; }
  .no-articles { color: #999; font-style: italic; text-align: center; padding: 20px; }
  @media (max-width: 480px) {
    .container { padding: 10px; }
    .header { padding: 20px 16px; }
    .content { padding: 14px 12px; }
  }
</style>
</head>
<body>
<div class="container">
"""
    # ---- Header ----
    html += f"""
<div class="header">
  <h1>📡 IT & AI 资讯推送</h1>
  <p class="subtitle">自动化聚合 · 每3小时更新</p>
  <p class="time">{now.strftime('%Y年%m月%d日 %H:%M')} (UTC+8)</p>
</div>
"""

    # ---- Stats ----
    html += f"""
<div class="stats">
  <div><div class="stat-num">{total}</div><div class="stat-label">📰 本次资讯</div></div>
  <div><div class="stat-num">{len(ai_articles)}</div><div class="stat-label">🔥 AI 相关</div></div>
  <div><div class="stat-num">{len(RSS_SOURCES)}</div><div class="stat-label">📂 分类</div></div>
  <div><div class="stat-num">{sum(len(s) for s in RSS_SOURCES.values())}</div><div class="stat-label">📡 信源</div></div>
</div>
"""

    html += '<div class="content">\n'

    # ---- 重点：AI 相关文章汇总 ----
    if ai_articles:
        html += '<div class="hot-section">\n'
        html += '<div class="hot-title">🔥 AI 重点资讯</div>\n'
        for a in ai_articles[:15]:
            tags_html = " ".join(
                f'<span class="tag tag-ai">{html_module.escape(t)}</span>' for t in a["ai_tags"][:4]
            )
            html += f"""
<div class="article">
  <div class="title">
    <a href="{html_module.escape(a['link'])}" target="_blank">{html_module.escape(a['title'])}</a>
    {tags_html}
  </div>
  <div class="meta">📌 {html_module.escape(a['source'])} {('· ' + a['published']) if a['published'] else ''}</div>
  <div class="summary">{html_module.escape(a['summary']) if a['summary'] else ''}</div>
</div>
"""
        html += '</div>\n'

    # ---- 分类展示 ----
    for category, articles in results.items():
        html += f'<div class="category">\n<div class="cat-title">{category}</div>\n'
        if not articles:
            html += '<div class="no-articles">本时段暂无更新</div>\n'
        else:
            for a in articles:
                tags_html = ""
                if a["ai_tags"]:
                    tags_html = " ".join(
                        f'<span class="tag tag-ai">{html_module.escape(t)}</span>'
                        for t in a["ai_tags"][:3]
                    )
                html += f"""
<div class="article">
  <div class="title">
    <a href="{html_module.escape(a['link'])}" target="_blank">{html_module.escape(a['title'])}</a>
    {tags_html}
  </div>
  <div class="meta">📌 {html_module.escape(a['source'])} {('· ' + a['published']) if a['published'] else ''}</div>
  <div class="summary">{html_module.escape(a['summary']) if a['summary'] else ''}</div>
</div>
"""
        html += '</div>\n'

    # ---- Footer ----
    html += f"""
</div><!-- .content -->
<div class="footer">
  <p>📬 由 <strong>News Digest Bot</strong> 自动生成 · 每3小时推送</p>
  <p>运行在 GitHub Actions · 完全免费 · <a href="https://github.com">项目地址</a></p>
  <p style="margin-top:6px;">退订或调整频率？修改 GitHub Actions 配置即可</p>
</div>
</div><!-- .container -->
</body>
</html>
"""
    return html


def send_email(html_content: str, total_count: int) -> bool:
    """通过 QQ邮箱 SMTP 发送邮件"""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD or not RECIPIENT_EMAIL:
        print("⚠️  邮件配置不完整，跳过发送。请设置 EMAIL_ADDRESS / EMAIL_PASSWORD / RECIPIENT_EMAIL")
        return False

    msg = MIMEMultipart("alternative")
    now = datetime.now(timezone(timedelta(hours=8)))
    subject = f"📡 IT & AI 资讯 · {now.strftime('%m/%d %H:%M')} · {total_count}条"
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = Header(f"News Digest <{EMAIL_ADDRESS}>", "utf-8")
    msg["To"] = RECIPIENT_EMAIL

    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.qq.com", 465, context=context, timeout=30) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, [RECIPIENT_EMAIL], msg.as_string())
        print(f"✅ 邮件发送成功 → {RECIPIENT_EMAIL}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ SMTP 认证失败：请检查 QQ邮箱授权码是否正确（不是QQ密码！）")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP 错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return False


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 50)
    print(f"🚀 News Digest Bot 启动 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 加载去重缓存
    sent_cache = load_sent_cache()
    print(f"📋 已缓存 {len(sent_cache)} 条已发送文章（{CACHE_TTL_HOURS}h 去重窗口）")

    # 抓取新闻
    print("📡 开始抓取新闻...")
    results = fetch_all_news(sent_cache)

    # 统计
    total = sum(len(v) for v in results.values())
    for cat, articles in results.items():
        print(f"  {cat}: {len(articles)} 条")

    if total == 0:
        print("📭 没有新文章，跳过发送。")
        return

    # 构建邮件
    print(f"📧 构建邮件（共 {total} 条）...")
    html = build_email_html(results)

    # 发送
    success = send_email(html, total)

    # 更新缓存（只有发送成功才标记为已发送）
    if success:
        now_ts = datetime.now().timestamp()
        for articles in results.values():
            for a in articles:
                sent_cache[a["id"]] = now_ts
        save_sent_cache(sent_cache)
        print(f"💾 缓存已更新 ({len(sent_cache)} 条)")

    print("✅ 任务完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
