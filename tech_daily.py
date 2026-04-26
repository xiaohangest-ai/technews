#!/usr/bin/env python3
"""
Tech Daily - 每天 8:00 (北京时间) 抓取国内外科技新闻 Top 5，推送到 Lark

云端版（GitHub Actions）：
- 凭据从环境变量读取（APP_ID / APP_SECRET / OPEN_ID），不再硬编码。
- 可选 LARK_BASE 覆盖（默认 https://open.larksuite.com/open-apis）。

用法:
    python3 tech_daily.py            # 抓取 + 筛选 + 推送
    python3 tech_daily.py --dry-run  # 只抓取和筛选，打印 Top 5，不发送
    python3 tech_daily.py --debug    # 同上 + 打印所有抓取到的原始条目

只用 Python 3 标准库，无第三方依赖。
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape

# ======================================================================
# 配置（凭据 + 新闻源）
# ======================================================================

# 凭据从环境变量读取；缺失时立即报错退出（避免静默失败）。
def _require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        print(
            f"❌ Missing required env var: {name}\n"
            f"   Set it in GitHub repository settings → Secrets and variables → Actions.",
            file=sys.stderr,
        )
        sys.exit(2)
    return v


APP_ID = _require_env("APP_ID")
APP_SECRET = _require_env("APP_SECRET")
OPEN_ID = _require_env("OPEN_ID")

LARK_BASE = (os.environ.get("LARK_BASE") or "https://open.larksuite.com/open-apis").rstrip("/")

CST = timezone(timedelta(hours=8))  # 北京时间

# 新闻源（全中文，聚焦 AI / 美股 / 互联网 / 科技）
SOURCES = [
    {"name": "36氪",   "type": "rss", "region": "cn", "weight": 0.90, "limit": 25,
     "url": "https://36kr.com/feed"},
    {"name": "钛媒体", "type": "rss", "region": "cn", "weight": 0.85, "limit": 20,
     "url": "https://www.tmtpost.com/feed"},
    {"name": "爱范儿", "type": "rss", "region": "cn", "weight": 0.85, "limit": 20,
     "url": "https://www.ifanr.com/feed"},
    {"name": "雷锋网", "type": "rss", "region": "cn", "weight": 0.80, "limit": 20,
     "url": "https://www.leiphone.com/feed"},
    {"name": "IT之家", "type": "rss", "region": "cn", "weight": 0.65, "limit": 20,
     "url": "https://www.ithome.com/rss/"},  # 权重低 + 噪声过滤
    # 已停用：
    #   虎嗅: https://www.huxiu.com/rss/0.xml （连续超时）
    #   少数派: https://sspai.com/feed （主要是评测/教程，不是新闻）
    #   机器之心: https://www.jiqizhixin.com/rss （XML 格式不规范）
    #   HN/TC/Verge/Ars: 英文，已弃用
]

# Top 5 配比：全部国内（用户偏好中文）
INTL_COUNT = 0
CN_COUNT = 5
MAX_AGE_HOURS = 30

# 来源多样性
MAX_PER_SOURCE_CN = 1     # 每源最多 1 条（强制分散）
MAX_PER_SOURCE_INTL = 2   # （当前未使用）

# 主题关键词加权 —— 用户偏好：AI / 美股 / 互联网 / 科技
TOPIC_KEYWORDS = {
    "AI": [
        "AI", "人工智能", "大模型", "LLM", "GPT", "Claude", "Gemini",
        "OpenAI", "Anthropic", "DeepSeek", "Qwen", "Llama", "千问",
        "智能体", "Agent", "AGI", "Sora", "Midjourney", "Stable Diffusion",
        "机器学习", "深度学习", "扩散模型", "RAG",
    ],
    "美股": [
        "美股", "纳斯达克", "标普", "道指", "道琼斯", "财报", "美联储",
        "Apple", "苹果", "Microsoft", "微软", "Google", "谷歌",
        "Amazon", "亚马逊", "Tesla", "特斯拉", "Meta", "Nvidia", "英伟达",
        "Netflix", "AMD", "Intel", "英特尔", "上市", "IPO",
    ],
    "互联网": [
        "阿里", "腾讯", "字节", "字节跳动", "百度", "美团", "拼多多",
        "抖音", "TikTok", "微信", "京东", "小米", "华为", "网易",
        "电商", "短视频", "社交", "直播", "外卖", "本地生活",
    ],
    "科技": [
        "半导体", "芯片", "晶圆", "光刻", "5G", "6G", "卫星",
        "量子", "机器人", "自动驾驶", "新能源车", "电池", "固态电池",
        "GPU", "CPU", "数据中心", "云计算", "AR", "VR", "头显",
    ],
}

# 每命中一个主题加多少分；摘要也参与匹配
TOPIC_BOOST_PER_TOPIC = 0.18
TOPIC_BOOST_CAP = 0.5

# 主题对应 emoji（卡片里显示）
TOPIC_EMOJI = {
    "AI": "🤖",
    "美股": "📈",
    "互联网": "🌐",
    "科技": "💻",
}
DEFAULT_TOPIC_EMOJI = "📰"

# 36氪 PR 软文标记 —— 标题或摘要命中任一关键词即跳过
# 这里挑确定性高的 brand 内容标记；融资类"36氪首发"保留（融资新闻是好的）
KR_PR_MARKERS = [
    # 明确的商业合作 / Brand 栏目
    "BRANDSTORM", "科氪|", "科氪丨",

    # 发布会站台稿（各种变体）
    "战略合作签约", "战略发布会", "产品发布会",
    "战略与产品发布会", "战略与新品发布", "新品发布会",

    # 站台发言/重磅营销感叹
    "重磅发布！", "重磅亮相", "战略升级！",
]

# IT之家 产品发布噪声标记 —— 标题同时含【产品类型】+【发布动作】或【明显价格】则跳过
ITHOME_PRODUCT_KEYWORDS = [
    "显示器", "键盘", "鼠标", "路由器", "电视", "耳机",
    "手机", "平板", "笔记本电脑", "主板", "显卡", "充电器",
    "电源", "硬盘", "音箱", "智能锁", "净化器", "扫地机",
    "洗衣机", "空调", "冰箱", "投影仪", "智能手表", "耳塞",
    "机箱", "摄像头", "无人机", "麦克风",
]
ITHOME_ACTION_KEYWORDS = ["推出", "上市", "开售", "众筹", "发售"]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) TechDaily/1.0"
)


# ======================================================================
# HTTP 工具
# ======================================================================

def http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_post(url: str, body: dict, headers: dict = None, timeout: int = 15) -> dict:
    h = {"Content-Type": "application/json; charset=utf-8", "User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body_text)
        except Exception:
            return {"http_error": e.code, "body": body_text}


# ======================================================================
# 解析工具
# ======================================================================

def strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s: str):
    """Try RSS 2.0 (RFC 2822) then Atom (ISO 8601)."""
    if not s:
        return None
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


# ======================================================================
# 抓取
# ======================================================================

def fetch_hn(source: dict) -> list:
    """Hacker News best stories."""
    items = []
    try:
        ids = json.loads(http_get("https://hacker-news.firebaseio.com/v0/beststories.json"))
        for sid in ids[: source["limit"]]:
            try:
                story = json.loads(
                    http_get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
                )
                if not story or story.get("type") != "story":
                    continue
                items.append({
                    "title": story.get("title", "").strip(),
                    "url": story.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                    "source": source["name"],
                    "region": source["region"],
                    "weight": source["weight"],
                    "published": datetime.fromtimestamp(story.get("time", 0), tz=timezone.utc),
                    "popularity": story.get("score", 0),
                    "summary": "",
                })
            except Exception as e:
                print(f"  ! HN item {sid} skipped: {e}", file=sys.stderr)
    except Exception as e:
        print(f"  ! HN fetch failed: {e}", file=sys.stderr)
    return items


def fetch_rss(source: dict) -> list:
    """通用 RSS 2.0 / Atom 解析。"""
    items = []
    try:
        xml_bytes = http_get(source["url"])
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            print(f"  ! {source['name']} XML parse error: {e}", file=sys.stderr)
            return items

        # RSS 2.0
        entries = root.findall(".//item")
        is_atom = False
        if not entries:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            entries = root.findall(".//a:entry", ns)
            is_atom = True

        for e in entries[: source["limit"]]:
            if is_atom:
                ns = {"a": "http://www.w3.org/2005/Atom"}
                title = (e.findtext("a:title", "", ns) or "").strip()
                link_el = e.find("a:link", ns)
                url = link_el.get("href") if link_el is not None else ""
                pub = e.findtext("a:published", "", ns) or e.findtext("a:updated", "", ns)
                summary = strip_html(e.findtext("a:summary", "", ns) or "")
            else:
                title = (e.findtext("title", "") or "").strip()
                url = (e.findtext("link", "") or "").strip()
                pub = e.findtext("pubDate", "")
                summary = strip_html(e.findtext("description", "") or "")

            if not title or not url:
                continue

            items.append({
                "title": title,
                "url": url,
                "source": source["name"],
                "region": source["region"],
                "weight": source["weight"],
                "published": parse_date(pub) or datetime.now(timezone.utc),
                "popularity": 0,
                "summary": summary[:200],
            })
    except Exception as ex:
        print(f"  ! {source['name']} fetch failed: {ex}", file=sys.stderr)
    return items


def fetch_all() -> list:
    items = []
    for source in SOURCES:
        print(f"  -> {source['name']}...", file=sys.stderr)
        if source["type"] == "hn":
            items += fetch_hn(source)
        elif source["type"] == "rss":
            items += fetch_rss(source)
    return items


# ======================================================================
# 筛选
# ======================================================================

def normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower()).strip()


def is_similar(a: str, b: str) -> bool:
    a, b = normalize_title(a), normalize_title(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) > 20 and len(b) > 20 and (a in b or b in a):
        return True
    return False


def matched_topics(it: dict) -> list:
    """返回标题/摘要里命中的主题列表（按 TOPIC_KEYWORDS 顺序）"""
    text = (it.get("title", "") + " " + it.get("summary", "")).lower()
    matches = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                matches.append(topic)
                break
    return matches


def score_item(it: dict, now: datetime) -> float:
    pub = it["published"]
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    age_h = max(0.0, (now - pub).total_seconds() / 3600)
    if age_h <= 6:
        recency = 1.0
    elif age_h <= 12:
        recency = 0.9
    elif age_h <= 24:
        recency = 0.8
    else:
        recency = 0.5

    pop = it.get("popularity", 0)
    pop_factor = 1.0 + math.log(pop + 1) / 10 if pop > 0 else 1.0
    base = it["weight"] * recency * pop_factor

    # 主题加权
    topics = matched_topics(it)
    it["_topics"] = topics  # 缓存，formatter 会用
    boost = min(len(topics) * TOPIC_BOOST_PER_TOPIC, TOPIC_BOOST_CAP)
    return base + boost


def is_36kr_pr(item: dict) -> bool:
    """36氪 PR/软文识别 —— 同时扫描标题和摘要"""
    if item["source"] != "36氪":
        return False
    text = item.get("title", "") + " " + (item.get("summary") or "")
    return any(marker in text for marker in KR_PR_MARKERS)


def is_ithome_product_noise(item: dict) -> bool:
    """IT之家 单纯产品发布稿过滤"""
    if item["source"] != "IT之家":
        return False
    title = item.get("title", "")
    has_product = any(p in title for p in ITHOME_PRODUCT_KEYWORDS)
    has_action = any(a in title for a in ITHOME_ACTION_KEYWORDS)
    has_price = bool(re.search(r"\d{3,5}\s*元", title))
    # 命中（产品 + 发布动作）或（产品 + 明显价格）→ 是产品发布稿
    return has_product and (has_action or has_price)


def is_noise(item: dict) -> bool:
    """统一噪声过滤入口"""
    return is_36kr_pr(item) or is_ithome_product_noise(item)


def select_top_5(items: list) -> list:
    now = datetime.now(timezone.utc)

    fresh = []
    for it in items:
        pub = it["published"]
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        age_h = (now - pub).total_seconds() / 3600
        if age_h > MAX_AGE_HOURS or age_h < -1:
            continue
        if not it.get("title"):
            continue
        if is_noise(it):
            continue  # 跳过噪声（36氪 PR、IT之家 产品发布稿等）
        it["_score"] = score_item(it, now)
        fresh.append(it)

    intl = sorted([x for x in fresh if x["region"] == "intl"], key=lambda x: -x["_score"])
    cn = sorted([x for x in fresh if x["region"] == "cn"], key=lambda x: -x["_score"])

    def pick_diverse(sorted_pool, target_count, max_per_source):
        """按分数依次取，但每个来源最多 max_per_source 条；同时跳过和已选相似标题"""
        out = []
        source_counts = {}
        for it in sorted_pool:
            if len(out) >= target_count:
                break
            src = it["source"]
            if source_counts.get(src, 0) >= max_per_source:
                continue
            if any(is_similar(it["title"], o["title"]) for o in out):
                continue
            out.append(it)
            source_counts[src] = source_counts.get(src, 0) + 1
        return out

    picked_intl = pick_diverse(intl, INTL_COUNT, MAX_PER_SOURCE_INTL)
    picked_cn = pick_diverse(cn, CN_COUNT, MAX_PER_SOURCE_CN)
    picked = picked_intl + picked_cn

    target = INTL_COUNT + CN_COUNT

    # 兜底 1：如果某一边不足，放宽该边的单源约束再试
    if len(picked_cn) < CN_COUNT:
        relaxed_cn = pick_diverse(cn, CN_COUNT, MAX_PER_SOURCE_CN + 1)
        picked = picked_intl + relaxed_cn
    if len(picked_intl) < INTL_COUNT:
        relaxed_intl = pick_diverse(intl, INTL_COUNT, MAX_PER_SOURCE_INTL + 1)
        picked = relaxed_intl + (picked_cn if len(picked_cn) >= CN_COUNT else
                                 pick_diverse(cn, CN_COUNT, MAX_PER_SOURCE_CN + 1))

    # 兜底 2：还是不够 5 条，从另一区域补
    if len(picked) < target:
        existing_urls = {it["url"] for it in picked}
        leftover = sorted(
            [x for x in (intl + cn) if x["url"] not in existing_urls],
            key=lambda x: -x["_score"],
        )
        picked += leftover[: target - len(picked)]

    picked.sort(key=lambda x: -x["_score"])
    return picked[:5]


# ======================================================================
# Lark 卡片
# ======================================================================

def build_card(items: list) -> dict:
    now_cst = datetime.now(CST)
    weekday_zh = "一二三四五六日"[now_cst.weekday()]

    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"📅 **{now_cst.strftime('%Y-%m-%d')} 星期{weekday_zh}**\n"
                    f"为你精选今日 {len(items)} 条最重要的科技新闻"
                ),
            },
        },
        {"tag": "hr"},
    ]

    for i, item in enumerate(items, 1):
        # 主题 emoji（按命中的第一个主题）
        topics = item.get("_topics") or matched_topics(item)
        emoji = TOPIC_EMOJI.get(topics[0], DEFAULT_TOPIC_EMOJI) if topics else DEFAULT_TOPIC_EMOJI
        topic_label = " · ".join(topics) if topics else ""

        # 标题里如果有 Markdown 特殊字符要转义
        title = item["title"].replace("[", "(").replace("]", ")")
        url = item["url"]
        body = f"**{i}. {emoji} [{title}]({url})**"

        summary = (item.get("summary") or "").strip()
        if summary:
            if len(summary) > 90:
                summary = summary[:90] + "…"
            body += f"\n{summary}"

        meta = item["source"]
        if topic_label:
            meta += f" · {topic_label}"
        if item.get("popularity"):
            meta += f" · 🔥 {item['popularity']}"
        body += f"\n{meta}"

        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": body}})
        if i < len(items):
            elements.append({"tag": "hr"})

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": f"Tech Daily · 推送于 {now_cst.strftime('%H:%M')}"
        }],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": "📰 今日科技 Top 5"},
        },
        "elements": elements,
    }


# ======================================================================
# Lark 发送
# ======================================================================

def get_token() -> str:
    r = http_post(
        f"{LARK_BASE}/auth/v3/tenant_access_token/internal",
        {"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    if r.get("code") != 0:
        raise RuntimeError(f"Failed to get token: {r}")
    return r["tenant_access_token"]


def send_card(open_id: str, card: dict) -> dict:
    token = get_token()
    return http_post(
        f"{LARK_BASE}/im/v1/messages?receive_id_type=open_id",
        {
            "receive_id": open_id,
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False),
        },
        {"Authorization": f"Bearer {token}"},
    )


# ======================================================================
# Main
# ======================================================================

def main() -> int:
    debug = "--debug" in sys.argv
    dry_run = "--dry-run" in sys.argv or debug

    print(f"[{datetime.now(CST).isoformat()}] Tech Daily start", file=sys.stderr)
    print("Fetching sources...", file=sys.stderr)
    raw = fetch_all()
    print(f"Total fetched: {len(raw)} items\n", file=sys.stderr)

    if debug:
        print("=== All raw items ===")
        for it in raw:
            print(f"  [{it['region']}] [{it['source']}] {it['title'][:80]}")
        print()

    top5 = select_top_5(raw)
    print(f"Selected {len(top5)} items:", file=sys.stderr)
    for i, it in enumerate(top5, 1):
        print(f"  {i}. [{it['region']}] {it['source']}: {it['title'][:70]}",
              file=sys.stderr)

    if not top5:
        print("\n! No items selected, abort.", file=sys.stderr)
        return 1

    card = build_card(top5)

    if dry_run:
        print("\n=== Dry run, not sending. Card payload: ===")
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return 0

    print("\nSending to Lark...", file=sys.stderr)
    r = send_card(OPEN_ID, card)
    if r.get("code") == 0:
        print(f"✅ Sent. message_id={r['data']['message_id']}")
        return 0
    else:
        print(f"❌ Send failed: {r}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
