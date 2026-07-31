# SceneSeeker — Movie Recommender System

**SceneSeeker** is a content-based movie recommendation web app built with Streamlit. Pick a movie you like and get similar recommendations, chat with an AI movie assistant that understands your mood, and keep track of what you've watched — all in a sleek, personalized interface.

🔗 **Live Demo:** [https://movie-recommender-system-fs.streamlit.app/](https://movie-recommender-system-fs.streamlit.app/)

---

## Features

- **Content-based recommendations** — pick any movie, get the 10 most similar titles instantly
- **Ask AI (SceneSeeker AI)** — chat naturally about mood, genre, actor, or era and get punchy, personalized movie picks (powered by Groq's LLaMA 3.3 70B)
- **Multi-language chat** — auto-detects and replies in the user's language: English, Roman Urdu, Urdu script, or Punjabi
- **My Watchlist** — track watched movies, rate them, and get fresh recommendations based on your history
- **Live posters, ratings, runtime & trailers** via The Movie Database (TMDB) API
- **Surprise Me** — random highly-rated pick when you can't decide
- **Simple username-based login** with persistent history (SQLite)
- **Trending this week** — popular movies pulled live from TMDB

---

## How It Works

### Recommendation Engine (Content-Based Filtering)

1. A pre-processed dataset of movies (`movies.pkl`) holds metadata (title, movie ID, tags built from genres/cast/crew/overview keywords).
2. A **precomputed cosine-similarity matrix** (`similarity.pkl`) captures how similar every movie is to every other movie based on those tags. This file is large, so it's hosted on Google Drive and **auto-downloaded on first run** via `gdown`.
3. When a user selects a movie, the app looks up its index, sorts all other movies by similarity score, filters out anything the user has already watched, and returns the top-N matches.

```
User selects a movie
        │
        ▼
Look up movie index in movies.pkl
        │
        ▼
Sort similarity.pkl row by score (descending)
        │
        ▼
Filter out already-watched titles
        │
        ▼
Return top 10 similar movies + poster/details from TMDB
```

### Conversational Recommendations (Ask AI)

The "Ask AI" tab sends the conversation to **Groq's `llama-3.3-70b-versatile`** model with a system prompt that instructs it to act as a movie recommendation assistant — suggesting 3–5 movies with short, enthusiastic reasons based on mood, genre, actor, era, or theme. A strict language-matching rule makes the assistant reply in whatever language the user typed in (English, Roman Urdu, Urdu script, or Punjabi), without mixing languages.

### Data Persistence

A local **SQLite** database (`sceneseeker.db`) stores:
- `users` — username-based accounts
- `watch_history` — watched movies + optional ratings, used to personalize future recommendations and avoid repeats
- `chat_history` — full Ask-AI conversation log per user

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend / App Framework | Streamlit |
| Recommendation Logic | Content-based filtering — precomputed Cosine Similarity matrix (scikit-learn) |
| Conversational AI | Groq API — LLaMA 3.3 70B Versatile |
| Movie Data / Posters / Trailers | TMDB (The Movie Database) API |
| Database | SQLite |
| Large File Hosting | Google Drive + `gdown` (for `similarity.pkl`) |
| Text Processing | NLTK |
| Deployment | Streamlit Community Cloud |

---

## Project Structure

```
Movie-Recommender-System/
├── app.py            # Full Streamlit app — UI, recommendation engine, AI chat, DB, TMDB integration
├── movies.pkl         # Preprocessed movie metadata (titles, IDs, tags)
├── favicon.png         # App icon
├── requirements.txt
├── procfile            # Deployment start command
└── setup.sh            # Streamlit server config for deployment
```

> Note: `similarity.pkl` (the cosine-similarity matrix) is **not stored in the repo** due to its size — it's downloaded automatically from Google Drive the first time the app runs.

---

## Setup & Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/fatimasabir987/Movie-Recommender-System.git
   cd Movie-Recommender-System
   ```

2. **Create a virtual environment & install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate      # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Add your API keys**

   Create a `.streamlit/secrets.toml` file:
   ```toml
   GROQ_API_KEY = "your_groq_api_key_here"
   TMDB_API_KEY = "your_tmdb_api_key_here"
   ```

4. **Run the app**
   ```bash
   streamlit run app.py
   ```

   On first run, `similarity.pkl` will be downloaded automatically from Google Drive.

---

## Usage

1. Open the app (locally or via the [live demo](https://movie-recommender-system-fs.streamlit.app/)) and log in with any username.
2. **Discover** tab — pick a movie from the dropdown to get similar recommendations.
3. **Ask AI** tab — describe your mood or preferences in any supported language and get tailored picks.
4. **My Watchlist** tab — mark movies as watched, rate them, and get recommendations built from your viewing history.

---

## Known Limitations

- Recommendations are purely **content-based** (tag/metadata similarity) — no collaborative filtering across users.
- `similarity.pkl` is a large static matrix computed offline; it won't reflect new movies without regenerating the model.
- SQLite is file-based — not ideal for concurrent multi-user production scale.
- Login is username-only, with no password/auth security.
- TMDB and Groq API calls depend on external service availability and rate limits.

---

## Roadmap / Possible Improvements

- [ ] Add collaborative filtering / hybrid recommendation approach
- [ ] Move from SQLite to a managed database (PostgreSQL) for production scale
- [ ] Add proper authentication (passwords / OAuth)
- [ ] Periodically refresh the similarity matrix with new releases
- [ ] Surface the "Trending this week" view in the main navigation

---

## License

This project is open-source. Feel free to fork and build on it.

---

## 👩‍💻 Author

**Fatima Sabir** — [GitHub](https://github.com/fatimasabir987)
