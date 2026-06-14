# 📡 IT & AI 资讯定时推送

每 **3小时** 自动聚合全球 IT 和 AI 资讯，精美 HTML 邮件推送到你的邮箱。

> 🆓 **完全免费** — 运行在 GitHub Actions，无需服务器，电脑关机也能收。

---

## ✨ 功能

| 功能 | 说明 |
|------|------|
| 🤖 AI/ML 前沿 | ArXiv AI/ML 论文、OpenAI/Google/HuggingFace 官方博客 |
| 💻 IT/科技 | Hacker News、TechCrunch、Ars Technica、The Verge 等 |
| 🇨🇳 中文科技 | 36氪、机器之心、量子位、InfoQ、IT之家 |
| 🔥 AI 重点标记 | 自动识别 AI 关键词（LLM/Agent/GPT/多模态…），红色高亮 |
| 📊 概览统计 | 邮件顶部展示本次资讯数量 + AI 相关条目数 |
| 🗂️ 智能去重 | 24小时内已发送的文章不会重复推送 |
| 📱 移动适配 | HTML 邮件在手机和电脑上都有良好阅读体验 |

---

## 🚀 快速部署（3步搞定）

### 第1步：获取 QQ邮箱授权码

1. 登录 [QQ邮箱](https://mail.qq.com)
2. 点击 **设置 → 账户**
3. 找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务**
4. 开启 **SMTP 服务**
5. 按提示发送短信验证，获取 **16位授权码**（不是QQ密码！）

### 第2步：创建 GitHub 仓库并设置 Secrets

1. 将这个项目文件夹推到你自己的 GitHub 仓库：

```bash
cd news-digest
git init
git add .
git commit -m "🎉 初始化 IT & AI 资讯推送系统"
git branch -M main
git remote add origin https://github.com/<你的用户名>/news-digest.git
git push -u origin main
```

2. 在仓库页面：**Settings → Secrets and variables → Actions → New repository secret**

添加以下3个 secrets：

| Secret 名称 | 值 |
|-------------|-----|
| `EMAIL_ADDRESS` | 你的 QQ 邮箱，如 `123456@qq.com` |
| `EMAIL_PASSWORD` | QQ邮箱的 **SMTP 授权码**（16位） |
| `RECIPIENT_EMAIL` | 接收邮件的邮箱（可以和发件人相同） |

### 第3步：手动触发测试

1. 进入仓库 **Actions** 标签页
2. 点击左侧 **"News Digest — IT & AI 资讯定时推送"**
3. 点击 **Run workflow** 按钮
4. 选择 `main` 分支，点击绿色的 **Run workflow**

✅ 几分钟后检查你的邮箱！

---

## ⏰ 推送时间表

北京时间（UTC+8），每天 **8次**：

| 推送时间 |
|----------|
| 08:00 · 11:00 · 14:00 · 17:00 |
| 20:00 · 23:00 · 02:00 · 05:00 |

> 💡 半夜的推送（02:00/05:00）可能为空（新闻源更新少），属于正常现象。

**修改推送频率**：编辑 `.github/workflows/news-digest.yml` 中的 `cron` 表达式。

---

## 📧 邮件效果预览

```
╔══════════════════════════════════════╗
║     📡 IT & AI 资讯推送               ║
║     2026年06月15日 14:00             ║
╚══════════════════════════════════════╝

📰 本次资讯: 32条  |  🔥 AI相关: 12条

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 AI 重点资讯（红色高亮区域）
━━━━━━━━━━━━━━━━━━━━━━━━━━
• [ArXiv] GPT-5 Survey Paper 🔥GPT-5 LLM
• [HuggingFace] New Open-Source Agent Framework 🔥agent 开源模型
...

━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 AI/ML 前沿 (7条)
━━━━━━━━━━━━━━━━━━━━━━━━━━
...

━━━━━━━━━━━━━━━━━━━━━━━━━━
💻 IT / 科技 (12条)
━━━━━━━━━━━━━━━━━━━━━━━━━━
...

━━━━━━━━━━━━━━━━━━━━━━━━━━
🇨🇳 中文科技 (13条)
━━━━━━━━━━━━━━━━━━━━━━━━━━
...
```

---

## 🔧 自定义

### 添加/修改新闻源

编辑 `main.py` 中的 `RSS_SOURCES` 字典：

```python
RSS_SOURCES = {
    "🤖 AI/ML 前沿": [
        {"name": "显示名称", "url": "RSS地址"},
        # 在这里添加更多...
    ],
}
```

### 修改 AI 关键词

编辑 `main.py` 中的 `AI_KEYWORDS` 列表，添加你关注的关键词。

### 调整去重时间

在 GitHub Secrets 中设置 `CACHE_TTL_HOURS`（默认24小时）。

---

## 📦 依赖

- Python 3.10+
- [feedparser](https://pypi.org/project/feedparser/) — RSS/Atom 解析

无其他重型依赖，GitHub Actions 冷启动 < 30秒。

---

## ⚠️ 注意事项

- QQ邮箱 SMTP 有每日发送上限（通常500封），本系统每天8封，完全没问题
- 部分国外 RSS 源（如 MIT Tech Review）在国内可能较慢，GitHub Actions 的服务器在海外，不受影响
- 如果某次推送为空，说明所有信源在去重窗口内都没有新文章

---

## 📄 License

MIT
