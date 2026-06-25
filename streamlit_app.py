import json
from datetime import datetime
from pathlib import Path

import anthropic
import feedparser
import requests
import streamlit as st
from bs4 import BeautifulSoup

# ── 파일 경로 ────────────────────────────────────────────────────────────────
CONFIG_FILE = Path("config.json")
POSTS_FILE = Path("posts.json")

RSS_FEEDS = [
    "https://news.yahoo.co.jp/rss/topics/life.xml",
    "https://news.yahoo.co.jp/rss/topics/entertainment.xml",
    "https://news.yahoo.co.jp/rss/topics/health.xml",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# ── 저장/불러오기 ─────────────────────────────────────────────────────────────
def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {"api_key": ""}

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))

def load_posts():
    if POSTS_FILE.exists():
        return json.loads(POSTS_FILE.read_text())
    return []

def save_posts(posts):
    POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2))

# ── 글 생성 ───────────────────────────────────────────────────────────────────
def fetch_articles():
    articles = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
            articles.append({"title": entry.title, "url": entry.link})
    return articles

def fetch_og_image(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        tag = soup.find("meta", property="og:image")
        return tag["content"] if tag and tag.get("content") else None
    except Exception:
        return None

def collect_image_urls(articles, count=2):
    images = []
    for article in articles:
        if len(images) >= count:
            break
        img = fetch_og_image(article["url"])
        if img:
            images.append(img)
    return images

def generate_post(api_key):
    articles = fetch_articles()
    if not articles:
        st.error("야후재팬에서 기사를 가져오지 못했어요.")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    topics_text = "\n".join(f"{i+1}. {a['title']}" for i, a in enumerate(articles))

    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"""以下はYahoo! Japanの最新ニュース見出しです:

{topics_text}

この中から20〜40代の日本人女性が最も共感・興味を持ちそうなトピックを1つ選び、
Threadsに投稿する文章を作成してください。

【条件】
- ガールズちゃんねるやSNSの日本女性の書き方に近い、親しみやすい口語体
- 等身大の本音・共感を引き出す内容（説教や押しつけはNG）
- 150〜200文字程度
- ハッシュタグを3〜5個（末尾にまとめる）
- 絵文字を自然に1〜3個使う

【出力形式】
選んだトピック：〇〇〇
---
（投稿本文）"""
        }]
    )

    raw = message.content[0].text
    parts = raw.split("---", 1)
    topic = parts[0].replace("選んだトピック：", "").strip()
    content = parts[1].strip() if len(parts) > 1 else raw.strip()
    images = collect_image_urls(articles)

    post = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topic": topic,
        "content": content,
        "images": images,
    }

    posts = load_posts()
    posts.insert(0, post)
    save_posts(posts)
    return post

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="야후재팬 스레드 생성기", page_icon="🧵", layout="wide")

st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #fafafa; }
  .post-card {
    background: #fff;
    border: 1px solid #e5e5e5;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 20px;
  }
  .post-date { font-size: 12px; color: #999; margin-bottom: 4px; }
  .post-topic { font-size: 14px; font-weight: 600; color: #555; margin-bottom: 14px; }
  .post-content {
    font-size: 15px;
    line-height: 1.75;
    white-space: pre-wrap;
    word-break: break-word;
    color: #1a1a1a;
  }
  .stButton > button { border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ── 사이드바 (API 키 설정) ────────────────────────────────────────────────────
config = load_config()

with st.sidebar:
    st.title("⚙️ 설정")
    st.markdown("---")

    api_key_input = st.text_input(
        "Claude API 키",
        value=config.get("api_key", ""),
        type="password",
        help="sk-ant-api... 형태의 키를 입력하세요"
    )

    if st.button("💾 저장", use_container_width=True, type="primary"):
        config["api_key"] = api_key_input
        save_config(config)
        st.success("저장됐어요!")
        st.rerun()

# ── 메인 영역 ─────────────────────────────────────────────────────────────────
col_title, col_btn = st.columns([4, 1])
with col_title:
    st.title("🧵 야후재팬 스레드 생성기")
with col_btn:
    st.markdown("<div style='padding-top:14px'>", unsafe_allow_html=True)
    generate_clicked = st.button("✍️ 지금 생성", type="primary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

if generate_clicked:
    if not config.get("api_key"):
        st.warning("왼쪽 사이드바에서 Claude API 키를 먼저 입력해주세요.")
    else:
        with st.spinner("야후재팬에서 주제 가져오는 중... 약 30초~1분 걸려요 ☕"):
            post = generate_post(config["api_key"])
        if post:
            st.success("글 생성 완료!")
            st.rerun()

st.markdown("---")

# ── 글 목록 ───────────────────────────────────────────────────────────────────
posts = load_posts()

if not posts:
    st.markdown("""
    <div style='text-align:center; padding: 60px 0; color: #999'>
      <div style='font-size:48px'>✍️</div>
      <p style='font-size:16px; margin-top:12px'>아직 생성된 글이 없어요.<br>위의 <b>지금 생성</b> 버튼을 눌러보세요!</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"**총 {len(posts)}개의 글**")
    st.markdown("")

    for post in posts:
        with st.container():
            st.markdown(f"""
            <div class='post-card'>
              <div class='post-date'>{post['created_at']}</div>
              <div class='post-topic'>📌 {post['topic']}</div>
            </div>
            """, unsafe_allow_html=True)

            if post.get("images"):
                img_cols = st.columns(len(post["images"]))
                for i, img_url in enumerate(post["images"]):
                    with img_cols[i]:
                        try:
                            st.image(img_url, use_container_width=True)
                        except Exception:
                            st.caption("이미지를 불러올 수 없어요")

            st.markdown(f"""
            <div class='post-content'>{post['content']}</div>
            """, unsafe_allow_html=True)

            col_space, col_del = st.columns([5, 1])
            with col_del:
                if st.button("🗑️ 삭제", key=f"del_{post['id']}"):
                    posts_new = [p for p in posts if p["id"] != post["id"]]
                    save_posts(posts_new)
                    st.rerun()

            st.markdown("---")
