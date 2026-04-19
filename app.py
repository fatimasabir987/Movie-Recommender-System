import streamlit as st
import pickle
import requests
import pandas as pd
import sqlite3
import os
from datetime import datetime
try:
    from groq import Groq as _Groq
except ImportError:
    _Groq = None

# similarity.pkl is downloaded inside load_model() on first use

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
TMDB_API_KEY = st.secrets["TMDB_API_KEY"]
APP_NAME    = "SceneSeeker"
APP_TAGLINE = "Discover what your mood deserves"

LOGO_SVG = """<svg width="{size}" height="{size}" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <rect x="6" y="20" width="52" height="36" rx="5" fill="#1a1a1a" stroke="#e63946" stroke-width="1.5"/>
  <rect x="6" y="10" width="52" height="14" rx="5" fill="#e63946"/>
  <line x1="6" y1="17" x2="58" y2="17" stroke="#1a1a1a" stroke-width="1"/>
  <rect x="14" y="10" width="7" height="14" fill="#1a1a1a" transform="skewX(-15)"/>
  <rect x="28" y="10" width="7" height="14" fill="#1a1a1a" transform="skewX(-15)"/>
  <rect x="42" y="10" width="7" height="14" fill="#1a1a1a" transform="skewX(-15)"/>
  <circle cx="32" cy="38" r="8" fill="none" stroke="#e63946" stroke-width="2"/>
  <polygon points="29,34 29,42 38,38" fill="#e63946"/>
</svg>"""

def logo(size=40):
    return LOGO_SVG.format(size=size)

# Generate favicon from our clapboard logo
import base64, os
_FAVICON_SVG = b"""<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <rect x="6" y="20" width="52" height="36" rx="5" fill="#1a1a1a" stroke="#e63946" stroke-width="1.5"/>
  <rect x="6" y="10" width="52" height="14" rx="5" fill="#e63946"/>
  <line x1="6" y1="17" x2="58" y2="17" stroke="#1a1a1a" stroke-width="1"/>
  <rect x="14" y="10" width="7" height="14" fill="#1a1a1a" transform="skewX(-15)"/>
  <rect x="28" y="10" width="7" height="14" fill="#1a1a1a" transform="skewX(-15)"/>
  <rect x="42" y="10" width="7" height="14" fill="#1a1a1a" transform="skewX(-15)"/>
  <circle cx="32" cy="38" r="8" fill="none" stroke="#e63946" stroke-width="2"/>
  <polygon points="29,34 29,42 38,38" fill="#e63946"/>
</svg>"""

def _make_favicon():
    try:
        import cairosvg
        png = cairosvg.svg2png(bytestring=_FAVICON_SVG, output_width=64, output_height=64)
        with open("favicon.png", "wb") as f:
            f.write(png)
        return "favicon.png"
    except:
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            # clapboard body (dark rect)
            d.rounded_rectangle([6,20,58,56], radius=5, fill="#1a1a1a", outline="#e63946", width=2)
            # clapboard top bar (red)
            d.rounded_rectangle([6,10,58,24], radius=5, fill="#e63946")
            # play circle
            d.ellipse([24,30,40,46], outline="#e63946", width=2)
            # play triangle
            d.polygon([(29,34),(29,42),(38,38)], fill="#e63946")
            img.save("favicon.png")
            return "favicon.png"
        except:
            return "🎬"

_favicon = _make_favicon()

st.set_page_config(
    page_title=APP_NAME,
    page_icon=_favicon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&display=swap');

    #MainMenu, footer, header {visibility: hidden;}

    .ss-header {
        padding: 1.2rem 0 0.5rem 0;
        border-bottom: 1px solid rgba(128,128,128,0.15);
        margin-bottom: 1.5rem;
    }
    .ss-logo {
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .ss-tagline {
        font-size: 0.9rem;
        opacity: 0.5;
        margin-top: 2px;
    }
    div[data-testid="column"] img {
        border-radius: 10px;
    }
    div[data-testid="metric-container"] {
        background: rgba(128,128,128,0.06);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        border: 0.5px solid rgba(128,128,128,0.12);
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# DATABASE  (SQLite)
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("sceneseeker.db", check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        created_at TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS watch_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        movie_id TEXT,
        movie_title TEXT,
        rating REAL,
        watched_at TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        message TEXT,
        timestamp TEXT)""")
    conn.commit()
    return conn

def get_or_create_user(username):
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if row:
        return row[0]
    conn.execute("INSERT INTO users(username,created_at) VALUES(?,?)",
                 (username, datetime.now().isoformat()))
    conn.commit()
    return conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()[0]

def save_watch(user_id, movie_id, movie_title, rating=None):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM watch_history WHERE user_id=? AND movie_id=?",
        (user_id, str(movie_id))).fetchone()
    if existing:
        if rating:
            conn.execute("UPDATE watch_history SET rating=? WHERE id=?", (rating, existing[0]))
    else:
        conn.execute(
            "INSERT INTO watch_history(user_id,movie_id,movie_title,rating,watched_at) VALUES(?,?,?,?,?)",
            (user_id, str(movie_id), movie_title, rating, datetime.now().isoformat()))
    conn.commit()

def get_watch_history(user_id):
    conn = get_db()
    return conn.execute(
        "SELECT movie_title,rating,watched_at FROM watch_history WHERE user_id=? ORDER BY watched_at DESC",
        (user_id,)).fetchall()

def get_watched_titles(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT movie_title FROM watch_history WHERE user_id=?", (user_id,)).fetchall()
    return [r[0] for r in rows]

def save_chat(user_id, role, message):
    conn = get_db()
    conn.execute(
        "INSERT INTO chat_history(user_id,role,message,timestamp) VALUES(?,?,?,?)",
        (user_id, role, message, datetime.now().isoformat()))
    conn.commit()

def load_chat_from_db(user_id, limit=40):
    conn = get_db()
    rows = conn.execute(
        "SELECT role,message FROM chat_history WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit)).fetchall()
    return list(reversed(rows))

# ─────────────────────────────────────────────
# TMDB
# ─────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=86400)
def fetch_poster(movie_id):
    try:
        data = requests.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}",
            timeout=5).json()
        p = data.get("poster_path")
        return f"https://image.tmdb.org/t/p/w500{p}" if p else \
               "https://via.placeholder.com/500x750?text=No+Poster"
    except:
        return "https://via.placeholder.com/500x750?text=No+Poster"

@st.cache_data(show_spinner=False, ttl=86400)
def fetch_movie_details(movie_id):
    try:
        data = requests.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}",
            timeout=5).json()
        trailer = None
        vids = requests.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={TMDB_API_KEY}",
            timeout=5).json()
        for v in vids.get("results", []):
            if v.get("type") == "Trailer" and v.get("site") == "YouTube":
                trailer = f"https://www.youtube.com/watch?v={v['key']}"
                break
        return {
            "overview": data.get("overview", ""),
            "vote":     round(data.get("vote_average", 0), 1),
            "year":     data.get("release_date", "")[:4],
            "runtime":  data.get("runtime", 0),
            "trailer":  trailer,
        }
    except:
        return {}

# ─────────────────────────────────────────────
# RECOMMENDATION ENGINE
# ─────────────────────────────────────────────
@st.cache_resource
def load_model():
    # Download similarity.pkl from Google Drive if not present
    if not os.path.exists("similarity.pkl"):
        try:
            import gdown
            gdown.download(
                "https://drive.google.com/uc?id=1UBueaytEtkE4sRPdOt00neSctWQaAoWa",
                "similarity.pkl",
                quiet=False
            )
        except Exception as e:
            st.error(f"Could not download model: {e}. Please refresh.")
            st.stop()
    movies     = pickle.load(open("movies.pkl",     "rb"))
    similarity = pickle.load(open("similarity.pkl", "rb"))
    return movies, similarity

def recommend(movie, user_id=None, top_n=10):
    movies, similarity = load_model()
    idx      = movies[movies["title"] == movie].index[0]
    raw      = sorted(list(enumerate(similarity[idx])), reverse=True,
                      key=lambda x: x[1])[1:top_n + 30]
    watched  = get_watched_titles(user_id) if user_id else []
    results  = []
    for i, score in raw:
        title    = movies.iloc[i].title
        movie_id = movies.iloc[i].movie_id
        if title not in watched:
            results.append({"title": title, "movie_id": movie_id,
                            "score": round(score * 100, 1)})
        if len(results) == top_n:
            break
    return results

# ─────────────────────────────────────────────
# GROQ CHATBOT  —  auto language detection
# ─────────────────────────────────────────────
def ask_groq(api_history, user_message):
    try:
        if _Groq is None:
            return "Groq library not installed. Run: pip install groq"
        client = _Groq(api_key=GROQ_API_KEY)

        system = {
            "role": "system",
            "content": (
                "You are SceneSeeker AI, a passionate movie recommendation assistant. "
                "When the user describes a mood, genre, actor, era, or theme — recommend 3-5 movies "
                "with a short punchy reason for each. Be warm and enthusiastic.\n\n"
                "LANGUAGE RULE (HIGHEST PRIORITY — NEVER BREAK THIS):\n"
                "- Detect the language of the user's message carefully.\n"
                "- Reply in EXACTLY the same language the user used.\n"
                "- English message → English reply only.\n"
                "- Roman Urdu message (Urdu written in English letters like 'koi sad movie batao') → Roman Urdu reply only.\n"
                "- Urdu script message (like یہ کوئی) → Urdu script reply only.\n"
                "- Punjabi message → Punjabi reply only.\n"
                "- Any other language → reply in that same language.\n"
                "- NEVER mix languages in a single reply.\n"
                "- NEVER default to Roman Urdu or Urdu when user wrote in English.\n"
                "Examples:\n"
                "  User: 'suggest me romantic movies' → Reply in English\n"
                "  User: 'koi sad movie batao' → Reply in Roman Urdu\n"
                "  User: 'کوئی اچھی فلم بتاؤ' → Reply in Urdu script\n"
                "  User: 'koi changi film dasoo' → Reply in Punjabi"
            )
        }

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[system] + api_history + [{"role": "user", "content": user_message}],
            max_tokens=1024,
            temperature=0.7
        )
        return response.choices[0].message.content

    except Exception as e:
        err = str(e).lower()
        if any(k in err for k in ["api", "key", "auth", "invalid", "401"]):
            return (
                "SceneSeeker AI needs a Groq API key.\n\n"
                "Get yours free at **https://console.groq.com** → API Keys → Create, "
                "then paste it into `app.py` at `GROQ_API_KEY = ...`"
            )
        return f"Oops, something went wrong: {str(e)}"

# ─────────────────────────────────────────────
# SHARED HEADER
# ─────────────────────────────────────────────
def app_header(subtitle=None):
    st.markdown(
        f'<div class="ss-header">'
        f'<div class="ss-logo" style="display:flex;align-items:center;gap:10px;">'
        f'{logo(38)}<span>{APP_NAME}</span>'
        f'</div>'
        f'<div class="ss-tagline">{subtitle or APP_TAGLINE}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

# ─────────────────────────────────────────────
# PAGE — LOGIN
# ─────────────────────────────────────────────
def page_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(
            f"<div style='text-align:center; padding-bottom:1.5rem;'>"
            f"<div style='display:flex;justify-content:center;margin-bottom:10px;'>{logo(80)}</div>"
            f"<div style='font-size:2.2rem; font-weight:700; letter-spacing:-0.5px;'>{APP_NAME}</div>"
            f"<div style='opacity:0.45; font-size:0.95rem; margin-top:6px;'>{APP_TAGLINE}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        name = st.text_input(
            "Your name",
            placeholder="Type your name to get started...",
            label_visibility="collapsed"
        )
        if st.button("Start Exploring  →", use_container_width=True, type="primary"):
            if name.strip():
                uid = get_or_create_user(name.strip())
                st.session_state.user_id   = uid
                st.session_state.username  = name.strip()
                st.session_state.chat_msgs = []
                st.rerun()
            else:
                st.warning("Enter your name first!")
        st.markdown(
            "<div style='text-align:center;opacity:0.35;font-size:0.78rem;margin-top:0.8rem;'>"
            "No password needed · your history is saved automatically"
            "</div>",
            unsafe_allow_html=True
        )

# ─────────────────────────────────────────────
# PAGE — DISCOVER
# ─────────────────────────────────────────────
def page_discover():
    app_header("Find your next favourite film")

    movies, _ = load_model()
    user_id   = st.session_state.get("user_id")
    watched   = get_watched_titles(user_id) if user_id else []

    selected = st.selectbox(
        "Pick a movie you enjoyed:",
        options=movies["title"].values,
        index=None,
        placeholder="Type or scroll to find a movie..."
    )

    if not selected:
        st.markdown(
            "<div style='opacity:0.35;text-align:center;padding:3rem 0;'>"
            "← Select any movie you liked to get personalised picks"
            "</div>",
            unsafe_allow_html=True
        )
        return

    # Selected movie card
    row     = movies[movies["title"] == selected].iloc[0]
    details = fetch_movie_details(row.movie_id)
    poster  = fetch_poster(row.movie_id)

    left, right = st.columns([1, 3])
    with left:
        st.image(poster, width=155)
    with right:
        st.subheader(selected)
        meta = []
        if details.get("year"):    meta.append(f"📅 {details['year']}")
        if details.get("runtime"): meta.append(f"⏱ {details['runtime']} min")
        if details.get("vote"):    meta.append(f"⭐ {details['vote']} / 10")
        if meta:
            st.caption("  ·  ".join(meta))
        if details.get("overview"):
            st.write(details["overview"])
        if details.get("trailer"):
            st.link_button("▶ Watch Trailer", details["trailer"])

    st.markdown("---")

    if watched:
        st.caption(f"Hiding {len(watched)} already-watched movies from results")

    if st.button("✦  Get Recommendations", type="primary"):
        with st.spinner("Curating your watchlist..."):
            results = recommend(selected, user_id=user_id, top_n=10)
        st.session_state.last_results = results
        st.session_state.last_seed    = selected

    if ("last_results" in st.session_state and
            st.session_state.get("last_seed") == selected):

        results = st.session_state.last_results
        st.markdown(f"#### Because you liked *{selected}*")

        for row_start in [0, 5]:
            cols = st.columns(5)
            for j, movie in enumerate(results[row_start:row_start + 5]):
                with cols[j]:
                    st.image(fetch_poster(movie["movie_id"]), use_container_width=True)
                    st.markdown(f"**{movie['title']}**")
                    st.caption(f"Match: {movie['score']}%")
                    if user_id:
                        rating = st.select_slider(
                            "Rate", key=f"rate_{movie['movie_id']}",
                            options=[0.0,0.5,1.0,1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0],
                            value=0.0
                        )
                        if st.button("✓ Watched", key=f"w_{movie['movie_id']}"):
                            save_watch(user_id, movie["movie_id"], movie["title"],
                                       rating if rating > 0 else None)
                            st.success("Saved!")
                        d = fetch_movie_details(movie["movie_id"])
                        if d.get("trailer"):
                            st.link_button("▶", d["trailer"], key=f"t_{movie['movie_id']}")
            st.markdown("")

# ─────────────────────────────────────────────
# PAGE — ASK AI
# ─────────────────────────────────────────────
def page_ask_ai():
    app_header("Ask SceneSeeker AI anything")

    user_id = st.session_state.get("user_id")

    if "chat_msgs" not in st.session_state or not st.session_state.chat_msgs:
        if user_id:
            db_hist = load_chat_from_db(user_id)
            st.session_state.chat_msgs = [{"role": r, "content": m} for r, m in db_hist]
        else:
            st.session_state.chat_msgs = []

    # Quick-start chips — only show when chat is empty
    if not st.session_state.chat_msgs:
        st.markdown("<div style='opacity:0.6; font-size:0.9rem; margin-bottom:8px;'>Try asking:</div>",
                    unsafe_allow_html=True)
        chips = [
            "Sad movies that make you cry",
            "Best 90s action films",
            "Something like Inception",
            "Funny movie for tonight",
        ]
        cols = st.columns(4)
        for i, chip in enumerate(chips):
            with cols[i]:
                if st.button(chip, key=f"chip_{i}", use_container_width=True):
                    st.session_state.pending_prompt = chip
                    st.rerun()
        st.markdown("---")

    # Display conversation
    for msg in st.session_state.chat_msgs:
        role = "assistant" if msg["role"] in ("assistant", "model") else "user"
        with st.chat_message(role, avatar="🎬" if role == "assistant" else None):
            st.write(msg["content"])

    # Handle pending chip click
    pending = st.session_state.pop("pending_prompt", None)
    prompt  = st.chat_input("Describe your mood, a genre, actor, era...") or pending

    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        st.session_state.chat_msgs.append({"role": "user", "content": prompt})
        if user_id:
            save_chat(user_id, "user", prompt)

        api_history = []
        for m in st.session_state.chat_msgs[:-1]:
            r = "assistant" if m["role"] in ("assistant", "model") else "user"
            api_history.append({"role": r, "content": m["content"]})

        with st.chat_message("assistant", avatar="🎬"):
            with st.spinner("Finding the perfect scene..."):
                reply = ask_groq(api_history, prompt)
            st.write(reply)

        st.session_state.chat_msgs.append({"role": "assistant", "content": reply})
        if user_id:
            save_chat(user_id, "assistant", reply)

# ─────────────────────────────────────────────
# PAGE — MY WATCHLIST
# ─────────────────────────────────────────────
def page_watchlist():
    app_header("Your cinematic journey")

    user_id = st.session_state.get("user_id")
    history = get_watch_history(user_id)

    if not history:
        st.markdown(
            "<div style='text-align:center;padding:3rem 0;opacity:0.4;'>"
            "No films saved yet — head to Discover and start watching!"
            "</div>",
            unsafe_allow_html=True
        )
        return

    ratings    = [r[1] for r in history if r[1] is not None]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

    c1, c2, c3 = st.columns(3)
    c1.metric("Films Watched", len(history))
    c2.metric("Avg Rating", f"{avg_rating} / 5" if avg_rating else "—")
    c3.metric("Rated", f"{len(ratings)} of {len(history)}")

    st.markdown("---")
    st.subheader("Watch history")

    df = pd.DataFrame(history, columns=["Title", "Rating", "Watched On"])
    df["Watched On"] = pd.to_datetime(df["Watched On"]).dt.strftime("%d %b %Y")
    df["Rating"]     = df["Rating"].apply(
        lambda x: ("★" * int(x) + "☆" * (5 - int(x))) if x else "—"
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Auto recommendations from top rated
    st.markdown("---")
    st.subheader("Recommended for you")
    top_rated = [r[0] for r in history if r[1] and r[1] >= 4.0]
    seed      = top_rated[0] if top_rated else history[0][0]
    movies, _ = load_model()

    if seed in movies["title"].values:
        st.caption(f"Based on your love for: *{seed}*")
        results = recommend(seed, user_id=user_id, top_n=5)
        cols    = st.columns(5)
        for j, movie in enumerate(results):
            with cols[j]:
                st.image(fetch_poster(movie["movie_id"]), use_container_width=True)
                st.markdown(f"**{movie['title']}**")
                st.caption(f"{movie['score']}% match")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    if "user_id" not in st.session_state:
        page_login()
        return

    username = st.session_state.get("username", "")

    with st.sidebar:
        st.markdown(
            f"<div style='padding:0.5rem 0 1rem;'>"
            f"<div style='display:flex;align-items:center;gap:8px;font-size:1.25rem;font-weight:700;'>"
            f"{logo(32)}<span>{APP_NAME}</span></div>"
            f"<div style='font-size:0.75rem;opacity:0.5;margin-top:2px;letter-spacing:0.02em;'>Welcome,</div>"
            f"<div style='font-family:Playfair Display, serif;font-size:1.05rem;font-weight:600;margin-top:1px;'>{username}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        st.markdown("---")

        page = st.radio(
            "nav",
            options=["Discover", "Ask AI", "My Watchlist"],
            label_visibility="collapsed"
        )

        st.markdown("---")
        if st.button("← Sign Out", use_container_width=True):
            st.session_state.clear()
            st.rerun()

        st.markdown(
            "<div style='position:absolute;bottom:1rem;font-size:0.72rem;opacity:0.3;'>"
            "SceneSeeker · FYP 2025"
            "</div>",
            unsafe_allow_html=True
        )

    if page == "Discover":
        page_discover()
    elif page == "Ask AI":
        page_ask_ai()
    elif page == "My Watchlist":
        page_watchlist()

if __name__ == "__main__":
    main()
