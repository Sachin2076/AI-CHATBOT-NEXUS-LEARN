# Nexus Learn — AI Study Assistant
Full-stack web app: Flask · MongoDB · Ollama LLM · Vanilla JS

---

## ⚡ Quick Start (3 steps)

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up environment
```bash
cp .env.example .env
# Edit .env if needed — defaults work for local setup
```

### 3. Start all services & run
```bash
# Terminal 1 — MongoDB (if running locally)
mongod

# Terminal 2 — Ollama
ollama serve

# Terminal 3 — Pull a model (first time only)
ollama pull llama3

# Terminal 4 — Flask app
python app.py
```

Open **http://localhost:5000**

---

## 🧱 Prerequisites

| Tool | Install | Notes |
|------|---------|-------|
| Python 3.11+ | python.org | Required |
| MongoDB | mongodb.com/try/download | Or use MongoDB Atlas (free) |
| Ollama | ollama.ai | Runs the LLM locally |

---

## 🌐 MongoDB Atlas (Cloud — no local install needed)

1. Go to [cloud.mongodb.com](https://cloud.mongodb.com) → free M0 cluster
2. Create a user + password
3. Get your connection string:
   `mongodb+srv://youruser:yourpass@cluster.mongodb.net/`
4. Set in `.env`:
   ```
   MONGODB_URI=mongodb+srv://youruser:yourpass@cluster.mongodb.net/
   ```

---

## 🤖 Ollama Models

```bash
# Recommended models (choose one):
ollama pull llama3        # Best quality, ~4.7GB
ollama pull mistral       # Fast + good, ~4.1GB
ollama pull gemma2        # Lightweight, ~3.8GB
ollama pull phi3          # Very fast, ~2.3GB
```

Then set in `.env`:
```
OLLAMA_MODEL=llama3   # or mistral, gemma2, phi3
```

---

## 🗂 Project Structure

```
nexus/
├── app.py              # Flask routes + API endpoints
├── db.py               # MongoDB connection + indexes
├── auth.py             # Register/login with bcrypt
├── llm.py              # Ollama integration + prompt builder
├── requirements.txt
├── .env.example
├── templates/
│   ├── index.html      # Landing page
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── chat.html       # Chat interface
│   ├── planner.html    # Weekly planner
│   └── placeholder.html
└── static/
    ├── css/style.css
    └── js/
        ├── chat.js
        ├── planner.js
        └── main.js
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/register` | Create account |
| POST | `/api/login` | Sign in |
| POST | `/api/logout` | Sign out |
| GET  | `/api/me` | Current user + stats |
| POST | `/api/chat` | Send message → LLM reply |
| GET  | `/api/chat/history` | Last 50 messages |
| DELETE | `/api/chat/history` | Clear chat |
| GET  | `/api/planner` | Get all tasks |
| POST | `/api/planner` | Add task `{day, task_text}` |
| DELETE | `/api/planner` | Remove task `{task_id}` |
| GET  | `/api/status` | Ollama + MongoDB health check |

---

## 🗄 MongoDB Collections

**users** — `{name, email, password_hash, created_at}`

**messages** — `{user_id, role, content, timestamp}`

**planner_tasks** — `{user_id, day, task_text, created_at}`

**usage_logs** — `{user_id, date, login_time, message_count, active_day}`

---

## 🔧 Running on Replit

1. Upload all files
2. In Replit Secrets, add:
   - `MONGODB_URI` → your Atlas URI
   - `SECRET_KEY` → any random string
   - `OLLAMA_URL` → if using external Ollama (or leave default)
3. In Shell: `pip install -r requirements.txt`
4. Run: `python app.py`

> **Note**: Ollama can't run inside Replit (no GPU). Point `OLLAMA_URL` to an external machine running Ollama, or use [ollama.ngrok.io](https://ngrok.com) to tunnel your local Ollama.

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection |
| `SECRET_KEY` | `dev-secret-change-me` | Flask session key |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama base URL |
| `OLLAMA_MODEL` | `llama3` | Model name |
| `PORT` | `5000` | Flask port |
