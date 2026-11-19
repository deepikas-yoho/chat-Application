# AI Chat Application — Week 5 Day 5

FastAPI backend for a persistent, streaming AI chat application with PostgreSQL history,
API-key authentication, per-key rate limiting, retries, and usage tracking.

## 1. Requirements

- Python 3.10+
- PostgreSQL
- An OpenAI API key (or compatible API key/base URL)

## 2. Setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

Edit `.env` and set `DATABASE_URL`, `API_KEY`, and `OPENAI_API_KEY`.

Create the database in PostgreSQL, for example:

```sql
CREATE DATABASE ai_chat_db;
```

Tables are created automatically when the application starts.

## 3. Run

```bash
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

Send this header with every API request:

```text
X-API-Key: change-this-secret-api-key
```

## 4. Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/sessions` | Create a chat session |
| GET | `/sessions/{session_id}/messages` | Read session history |
| DELETE | `/sessions/{session_id}` | Delete a session and its messages |
| POST | `/sessions/{session_id}/chat` | Save user message and stream assistant response |
| GET | `/usage` | Usage totals for the authenticated API key |

Chat request body:

```json
{"message": "Hello!","max_history_messages": 20}
```

The chat endpoint returns Server-Sent Events (`text/event-stream`). Each event is a
`data: {...}` line. The final event contains `done: true`, token usage, and estimated cost.

## 5. Test streaming with curl

```bash
curl -N -X POST "http://127.0.0.1:8000/sessions/SESSION_ID/chat" \
  -H "X-API-Key: change-this-secret-api-key" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Explain PostgreSQL in simple terms\"}"
```

Create a second session and chat in it to verify that histories are isolated.

The default limit is 20 user messages per API key per rolling hour. The 21st request
returns HTTP 429 and a `Retry-After` header.

## 6. Project structure

```text
ai_chat_application/
├── app/
│   ├── __init__.py
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── services.py
│   └── rate_limit.py
├── frontend/
│   └── index.html
├── tests/
│   ├── __init__.py
│   └── test_api.py
├── .env.example
├── .gitignore
└── requirements.txt
```

## Notes

- All SQL operations use SQLAlchemy's parameterized ORM queries.
- The full session history is loaded from PostgreSQL before each model call, then
  trimmed to the configured sliding window.
- Token usage is taken from the provider when available. If streaming usage is not
  returned, a conservative character-based estimate is stored.
- Cost is an estimate. Update the model pricing constants in `app/services.py` to
  match your provider's current pricing.
- This project is a backend-first implementation. The included frontend is a small
  demonstration client; it is not required for the API.
