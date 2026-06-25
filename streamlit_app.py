import json
from datetime import datetime
from pathlib import Path

import anthropic
import feedparser
import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup

# ── 파일 경로 ────────────────────────────────────────────────────────────────
CONFIG_FILE = Path("config.json")
POSTS_FILE = Path("posts.json")

RSS_FEEDS = [
    "https://news.yahoo.co.jp/rss/topics/life.xml",
    "https://news.yahoo.co.jp/rss/topics/entertainment.xml",
    "https://news.yahoo.co.jp/rss/topics/health.xml",
    "https://news.yahoo.co.jp/rss/topics/beauty.xml",
    "https://news.yahoo.co.jp/rss/topics/family.xml",
    "https://news.yahoo.co.jp/rss/topics/fashion.xml",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# ── 복사 버튼 ────────────────────────────────────────────────────────────────
def text_copy_button(text: str, key: str):
    safe = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    components.html(f"""
    <button id="btn_{key}" onclick="
      navigator.clipboard.writeText(`{safe}`)
        .then(()=>{{document.getElementById('btn_{key}').innerHTML='✅ 복사됨!';setTimeout(()=>document.getElementById('btn_{key}').innerHTML='📋 글 복사',2000)}})
        .catch(()=>alert('복사 실패. 직접 선택해서 복사해주세요.'))
    " style="width:100%;background:#ff4b4b;color:white;border:none;padding:9px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer">
      📋 글 복사
    </button>""", height=46)


def image_copy_button(img_url: str, idx: int, key: str):
    components.html(f"""
    <button id="imgbtn_{key}_{idx}" onclick="
      fetch('{img_url}')
        .then(r=>r.blob())
        .then(blob=>navigator.clipboard.write([new ClipboardItem({{[blob.type]:blob}})]))
        .then(()=>{{document.getElementById('imgbtn_{key}_{idx}').innerHTML='✅ 복사됨!';setTimeout(()=>document.getElementById('imgbtn_{key}_{idx}').innerHTML='🖼️ 사진 복사',2000)}})
        .catch(()=>{{document.getElementById('imgbtn_{key}_{idx}').innerHTML='📥 저장만 가능';document.getElementById('imgbtn_{key}_{idx}').onclick=()=>window.open('{img_url}','_blank')}})
    " style="width:100%;background:#444;color:white;border:none;padding:7px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer">
      🖼️ 사진 복사
    </button>""", height=42)


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
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""以下はYahoo! Japanの最新ニュース見出しです:

{topics_text}

この中から20〜40代の日本人女性（アラサー・アラフォー）が最も共感・興味を持ちそうなトピックを1つ選んで、
日本人女性がThreadsに投稿するような文章を書いてください。

【絶対条件】
ニュースの解説や要約は絶対NG。
「このニュースを見て自分はこう感じた・こういう経験がある」という
一人の日本人女性の本音・リアルな日常として書くこと。
読んだ人が「わかりすぎる」「私も！」「どういうこと？教えて」と
コメントしたくなる内容にする。

【コメントが増えるポイント（内容に合ったものを自然に使う。毎回同じパターンはNG）】
以下のどれかを内容に合わせて自然に使う。無理に全部入れない。
- 強い共感ポイントを作る（読んだ人が「わかりすぎる」と思う瞬間）
- 「賛否が分かれそうな本音」をさらっと混ぜる
- 「言いにくいけど実は…」という告白スタイル
- 答えを出さずに終わらせる（モヤモヤ感を残す）
- 内容的に自然な流れのときだけ、最後に問いかける（「同じ人いる？笑」など）
→ 毎回質問で締めるのは不自然。むしろ強い本音や共感で終わるほうが自然なことも多い

【文体・現地感】
- 100％日本人女性のThreads投稿に見えること（翻訳っぽさゼロ）
- ガールズちゃんねる・Threads・X女性ユーザーの自然な口語体
- 「えぐい」「やばみ」「まじで」「つよい」「〜すぎて無理」など今の若者言葉
- 「ww」「笑」「〜じゃない？」「〜だよね」「〜かも」を自然に使う
- 文末に「。」使わない
- 絵文字1〜2個（😭🥹✨🤣💦など、使いすぎない）
- 1行15〜20文字以内、2行ごとに空行
- ハッシュタグなし
- 全体150〜200文字

【出力形式】
選んだトピック：〇〇〇
---
（Threads投稿本文）
===
（위 일본어 글의 한국어 번역. 뉘앙스와 댓글 유도 포인트도 설명해줘）"""
        }]
    )

    raw = message.content[0].text
    parts = raw.split("---", 1)
    topic = parts[0].replace("選んだトピック：", "").strip()
    rest = parts[1].strip() if len(parts) > 1 else raw.strip()

    jp_ko = rest.split("===", 1)
    content = jp_ko[0].strip()
    content_ko = jp_ko[1].strip() if len(jp_ko) > 1 else ""

    images = collect_image_urls(articles)

    post = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topic": topic,
        "content": content,
        "content_ko": content_ko,
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
  .post-card {
    border: 1px solid rgba(128,128,128,0.3);
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 20px;
  }
  .post-date { font-size: 12px; opacity: 0.55; margin-bottom: 4px; }
  .post-topic { font-size: 14px; font-weight: 600; opacity: 0.75; margin-bottom: 14px; }
  .post-content {
    font-size: 15px;
    line-height: 1.85;
    white-space: pre-wrap;
    word-break: break-word;
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
                        image_copy_button(img_url, i, post["id"])

            st.markdown(f"""
            <div class='post-content'>{post['content']}</div>
            """, unsafe_allow_html=True)

            text_copy_button(post["content"], post["id"])

            if post.get("content_ko"):
                with st.expander("🇰🇷 한국어 번역 보기"):
                    st.markdown(post["content_ko"])

            col_space, col_del = st.columns([5, 1])
            with col_del:
                if st.button("🗑️ 삭제", key=f"del_{post['id']}"):
                    posts_new = [p for p in posts if p["id"] != post["id"]]
                    save_posts(posts_new)
                    st.rerun()

            st.markdown("---")
