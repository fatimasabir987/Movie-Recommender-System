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
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
TMDB_API_KEY = st.secrets.get("TMDB_API_KEY", "")

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
    /* Fullscreen movie player overlay */
    .movie-player-overlay {
        position: fixed;
        top: 0; left: 0;
        width: 100vw; height: 100vh;
        background: rgba(0,0,0,0.97);
        z-index: 9999;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    /* Sidebar width */
    section[data-testid="stSidebar"] {
        min-width: 240px !important;
        max-width: 280px !important;
    }
    /* Style the collapsed sidebar toggle — red pill button */
    section[data-testid="stSidebarCollapsedControl"] {
        background-color: #e63946 !important;
        border-radius: 0 12px 12px 0 !important;
        padding: 8px 4px !important;
    }
    section[data-testid="stSidebarCollapsedControl"] button {
        color: white !important;
        background: transparent !important;
    }
    section[data-testid="stSidebarCollapsedControl"] svg {
        fill: white !important;
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
# TRENDING + MOOD + SURPRISE HELPERS
# ─────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_trending():
    """Fetch trending movies from TMDB this week."""
    try:
        data = requests.get(
            f"https://api.themoviedb.org/3/trending/movie/week?api_key={TMDB_API_KEY}",
            timeout=5).json()
        results = []
        for m in data.get("results", [])[:10]:
            results.append({
                "title":    m.get("title", ""),
                "movie_id": m.get("id"),
                "score":    round(m.get("vote_average", 0) * 10, 1),
                "poster":   f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get("poster_path") else "",
            })
        return results
    except:
        return []

def detect_mood_genre(text):
    """Simple mood to genre mapping."""
    text = text.lower()
    mood_map = {
        "sad":        ("Drama"),
        "cry":        ("Drama"),
        "happy":      ("Comedy"),
        "fun":        ("Comedy"),
        "funny":      ("Comedy"),
        "scared":     ("Horror"),
        "horror":     ("Horror"),
        "thrill":     ("Thriller"),
        "action":     ("Action"),
        "fight":      ("Action"),
        "love":       ("Romance"),
        "romance":    ("Romance"),
        "date":       ("Romance"),
        "adventure":  ("Adventure"),
        "family":     ("Family"),
        "kids":       ("Family"),
        "sci-fi":     ("Science Fiction"),
        "space":      ("Science Fiction"),
        "mystery":    ("Mystery"),
        "crime":      ("Crime"),
    }
    for keyword, (genre, emoji) in mood_map.items():
        if keyword in text:
            return genre, emoji
    return None, None

@st.cache_data(show_spinner=False, ttl=3600)
def fetch_by_genre(genre_name):
    """Fetch popular movies by genre from TMDB."""
    genre_ids = {
        "Action": 28, "Comedy": 35, "Drama": 18, "Horror": 27,
        "Romance": 10749, "Thriller": 53, "Science Fiction": 878,
        "Adventure": 12, "Family": 10751, "Mystery": 9648, "Crime": 80,
    }
    gid = genre_ids.get(genre_name)
    if not gid:
        return []
    try:
        data = requests.get(
            f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}"
            f"&with_genres={gid}&sort_by=popularity.desc&vote_count.gte=500",
            timeout=5).json()
        results = []
        for m in data.get("results", [])[:10]:
            results.append({
                "title":    m.get("title", ""),
                "movie_id": m.get("id"),
                "score":    round(m.get("vote_average", 0) * 10, 1),
                "poster":   f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get("poster_path") else "",
            })
        return results
    except:
        return []

def get_surprise_movie(movies_df):
    """Return a random highly-rated movie."""
    import random
    pool = movies_df.sample(frac=1).head(50)
    return pool.iloc[random.randint(0, len(pool)-1)]

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
# SHARED MOVIE GRID RENDERER
# ─────────────────────────────────────────────
def render_movie_grid(results, user_id, key_prefix=""):
    """Render a grid of movie cards with Watch + Rate buttons."""
    playing = st.session_state.get("playing_movie_id")
    playing_title = st.session_state.get("playing_movie_title", "")

    if playing:
        # Fetch trailer for the playing movie
        details = fetch_movie_details(playing)
        trailer_url = details.get("trailer", "")
        st.markdown(
            f"<div style='background:#111;border-radius:12px;padding:1rem 1rem 0.5rem;margin-bottom:0.5rem;'>"
            f"<span style='color:white;font-size:1.1rem;font-weight:600;'>▶ {playing_title}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
        if trailer_url:
            # YouTube embed — always works
            yt_id = trailer_url.split("v=")[-1]
            yt_embed = f"https://www.youtube.com/embed/{yt_id}?autoplay=1&rel=0"
            st.markdown(
                f"<iframe width='100%' height='480' src='{yt_embed}' "
                f"frameborder='0' allowfullscreen allow='autoplay; encrypted-media' "
                f"style='border-radius:8px;display:block;'></iframe>",
                unsafe_allow_html=True
            )
            st.caption("🎬 Official trailer")
        else:
            st.info("No trailer available for this movie.")
        if st.button("✕  Close", key=f"close_{key_prefix}"):
            st.session_state.playing_movie_id    = None
            st.session_state.playing_movie_title = None
            st.rerun()
        st.markdown("---")

    chunk_size = 5
    for row_start in range(0, len(results), chunk_size):
        chunk = results[row_start:row_start + chunk_size]
        cols  = st.columns(len(chunk))
        for j, movie in enumerate(chunk):
            with cols[j]:
                poster = movie.get("poster") or fetch_poster(movie["movie_id"])
                if poster:
                    st.image(poster, use_container_width=True)
                st.markdown(f"**{movie['title']}**")
                st.caption(f"Match: {movie['score']}%")
                if st.button("▶ Watch", key=f"play_{key_prefix}_{movie['movie_id']}", type="primary"):
                    st.session_state.playing_movie_id    = movie["movie_id"]
                    st.session_state.playing_movie_title = movie["title"]
                    st.rerun()
                if user_id:
                    rating = st.select_slider(
                        "Rate", key=f"rate_{key_prefix}_{movie['movie_id']}",
                        options=[0.0,0.5,1.0,1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0],
                        value=0.0
                    )
                    if st.button("✓ Watched", key=f"w_{key_prefix}_{movie['movie_id']}"):
                        save_watch(user_id, movie["movie_id"], movie["title"],
                                   rating if rating > 0 else None)
                        st.success("Saved!")
        st.markdown("")

# ─────────────────────────────────────────────
# PAGE — DISCOVER
# ─────────────────────────────────────────────
def page_discover():
    movies, _ = load_model()
    user_id   = st.session_state.get("user_id")
    watched   = get_watched_titles(user_id) if user_id else []

    # ── GENRE FILTERS ──────────────────────
    st.markdown("##### Browse by Genre")
    genres = ["All", "Action", "Comedy", "Drama", "Horror", "Romance",
              "Thriller", "Science Fiction", "Adventure", "Family", "Mystery", "Crime"]
    selected_genre = st.selectbox("Genre", genres, label_visibility="collapsed")

    if selected_genre != "All":
        genre_results = fetch_by_genre(selected_genre)
        if genre_results:
            st.markdown(f"#### Popular {selected_genre} Movies")
            render_movie_grid(genre_results, user_id, key_prefix=f"genre_{selected_genre}")
            st.markdown("---")

    # ── CONTENT-BASED RECOMMENDATIONS ──────
    st.markdown("##### Or pick a movie you liked:")
    selected = st.selectbox(
        "Pick a movie:",
        options=movies["title"].values,
        index=None,
        placeholder="Type or scroll to find a movie...",
        label_visibility="collapsed"
    )

    if not selected:
        return

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
        if st.button("▶ Watch Movie", type="primary", key="watch_selected"):
            st.session_state.playing_movie_id    = row.movie_id
            st.session_state.playing_movie_title = selected
            st.rerun()

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
        render_movie_grid(results, user_id, key_prefix="rec")

# ─────────────────────────────────────────────
# MOVIE EXTRACTOR FROM AI REPLY
# ─────────────────────────────────────────────
def extract_movies_from_reply(reply, movies_df):
    """Find movie titles from AI reply that exist in our database."""
    import re
    found = []
    all_titles = movies_df["title"].tolist()
    # Look for bold titles (**Title**) or numbered lists
    bold_titles = re.findall(r'\*\*([^*]+)\*\*', reply)
    candidates = bold_titles if bold_titles else []
    # Also check numbered list items
    numbered = re.findall(r'\d+[.)]\s+([A-Za-z][^\n(]+?)(?:\s*[-(\[]|\n|$)', reply)
    candidates += [t.strip() for t in numbered]

    seen = set()
    for candidate in candidates:
        candidate = candidate.strip().rstrip(':.,')
        if len(candidate) < 3:
            continue
        # Exact match first
        if candidate in all_titles and candidate not in seen:
            row = movies_df[movies_df["title"] == candidate].iloc[0]
            found.append({"title": candidate, "movie_id": row.movie_id, "score": 0})
            seen.add(candidate)
        else:
            # Fuzzy match — check if candidate is in title
            for title in all_titles:
                if candidate.lower() in title.lower() and title not in seen:
                    row = movies_df[movies_df["title"] == title].iloc[0]
                    found.append({"title": title, "movie_id": row.movie_id, "score": 0})
                    seen.add(title)
                    break
        if len(found) >= 5:
            break
    return found

# ─────────────────────────────────────────────
# PAGE — ASK AI
# ─────────────────────────────────────────────
def page_ask_ai():
    user_id   = st.session_state.get("user_id")
    movies, _ = load_model()

    if "chat_msgs" not in st.session_state or not st.session_state.chat_msgs:
        if user_id:
            db_hist = load_chat_from_db(user_id)
            st.session_state.chat_msgs = [{"role": r, "content": m} for r, m in db_hist]
        else:
            st.session_state.chat_msgs = []

    # Quick-start chips
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

    # Display conversation history
    for msg in st.session_state.chat_msgs:
        role = "assistant" if msg["role"] in ("assistant", "model") else "user"
        with st.chat_message(role, avatar="🎬" if role == "assistant" else None):
            st.write(msg["content"])
            # Show movie cards under assistant messages
            if role == "assistant" and msg.get("movie_cards"):
                ai_movies = msg["movie_cards"]
                cols = st.columns(min(len(ai_movies), 5))
                for j, movie in enumerate(ai_movies[:5]):
                    with cols[j]:
                        poster = fetch_poster(movie["movie_id"])
                        if poster:
                            st.image(poster, use_container_width=True)
                        st.caption(f"**{movie['title']}**")
                        if st.button("▶ Watch", key=f"ai_play_{msg.get('ts',j)}_{movie['movie_id']}_{j}", type="primary"):
                            st.session_state.playing_movie_id    = movie["movie_id"]
                            st.session_state.playing_movie_title = movie["title"]
                            st.rerun()

    # Show player if active
    playing       = st.session_state.get("playing_movie_id")
    playing_title = st.session_state.get("playing_movie_title", "")
    if playing:
        details_p   = fetch_movie_details(playing)
        trailer_url = details_p.get("trailer", "")
        st.markdown(
            f"<div style='background:#111;border-radius:12px;padding:1rem 1rem 0.5rem;margin:0.5rem 0;'>"
            f"<span style='color:white;font-size:1rem;font-weight:600;'>▶ {playing_title}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
        if trailer_url:
            yt_id    = trailer_url.split("v=")[-1]
            yt_embed = f"https://www.youtube.com/embed/{yt_id}?autoplay=1&rel=0"
            st.markdown(
                f"<iframe width='100%' height='460' src='{yt_embed}' "
                f"frameborder='0' allowfullscreen allow='autoplay; encrypted-media' "
                f"style='border-radius:8px;display:block;'></iframe>",
                unsafe_allow_html=True
            )
            st.caption("🎬 Playing official trailer.")
        else:
            st.info("No trailer available for this movie.")
        if st.button("✕ Close", key="ai_close_player"):
            st.session_state.playing_movie_id    = None
            st.session_state.playing_movie_title = None
            st.rerun()
        st.markdown("---")

    # Handle pending chip
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

            # Extract movies and show cards
            ai_movies = extract_movies_from_reply(reply, movies)
            if ai_movies:
                st.markdown("**Watch these now:**")
                cols = st.columns(min(len(ai_movies), 5))
                ts   = int(datetime.now().timestamp())
                for j, movie in enumerate(ai_movies[:5]):
                    with cols[j]:
                        poster = fetch_poster(movie["movie_id"])
                        if poster:
                            st.image(poster, use_container_width=True)
                        st.caption(f"**{movie['title']}**")
                        if st.button("▶ Watch", key=f"new_play_{ts}_{movie['movie_id']}_{j}", type="primary"):
                            st.session_state.playing_movie_id    = movie["movie_id"]
                            st.session_state.playing_movie_title = movie["title"]
                            st.rerun()

        msg_obj = {"role": "assistant", "content": reply, "ts": int(datetime.now().timestamp())}
        if ai_movies:
            msg_obj["movie_cards"] = ai_movies
        st.session_state.chat_msgs.append(msg_obj)
        if user_id:
            save_chat(user_id, "assistant", reply)

# ─────────────────────────────────────────────
# PAGE — MY WATCHLIST
# ─────────────────────────────────────────────
def page_watchlist():
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
        lambda x: ("★" * int(x) + "☆" * (5 - int(x))) if (x is not None and x == x) else "—"
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
# PAGE — TRENDING
# ─────────────────────────────────────────────
def page_trending():
    user_id = st.session_state.get("user_id")
    st.markdown("### This Week's Trending Movies")
    st.caption("Updated weekly from TMDB")

    with st.spinner("Fetching trending movies..."):
        trending = fetch_trending()

    if not trending:
        st.info("Could not load trending movies. Please refresh.")
        return

    render_movie_grid(trending, user_id, key_prefix="trend")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    if "user_id" not in st.session_state:
        page_login()
        return

    username = st.session_state.get("username", "")

    # Top header
    h1, h2, h3 = st.columns([3, 5, 2])
    with h1:
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;padding:0.4rem 0;'>"
            f"{logo(30)}<span style='font-size:1.1rem;font-weight:700;'>{APP_NAME}</span></div>",
            unsafe_allow_html=True
        )
    with h2:
        st.markdown(
            f"<div style='text-align:center;padding:0.5rem 0;'>"
            f"<span style='font-size:0.75rem;opacity:0.5;'>Welcome, </span>"
            f"<span style='font-family:Playfair Display,serif;font-size:0.95rem;font-weight:600;'>{username}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    with h3:
        if st.button("Sign Out", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.markdown("<hr style='margin:0 0 1rem 0;opacity:0.15;'>", unsafe_allow_html=True)

    # Tab navigation works on ALL devices
    tab1, tab2, tab3 = st.tabs(["Discover", "Ask AI", "My Watchlist"])
    with tab1:
        page_discover()
    with tab2:
        page_ask_ai()
    with tab3:
        page_watchlist()

if __name__ == "__main__":
    main()
