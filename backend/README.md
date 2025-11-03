# AgentM Backend

- Dev server: `python -m uvicorn backend.main:app --reload --port 8000`
- Health check: `GET /health`
- Chat endpoint: `POST /api/chat` (multipart/form-data)
  - fields: `query` (text, optional), `image` (file, optional), `user_id` (text, optional)
  - returns: `{ output, facts, messages }`

Dependencies (install once):

```
pip install -r backend/requirements.txt
```

Environment:
- Requires agent dependencies (LangChain, LangGraph, Google Generative AI) and `GOOGLE_API_KEY` in `.env`.

Notes:
- If an image is uploaded, it is sent as a base64 data URL to Gemini via LangChain multimodal `HumanMessage`.
- Text-only queries work with `query`.
