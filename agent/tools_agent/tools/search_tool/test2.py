from serpapi import GoogleSearch
import os
import dotenv

dotenv.load_dotenv()

# Prefer SERPAPI_API_KEY, fall back to GOOGLE_API_KEY for backwards-compat
api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("Set SERPAPI_API_KEY (preferred) or GOOGLE_API_KEY in your environment/.env")

params = {
    "engine": "google_ai_mode",
    "q": "who is tayor swift's husband",
    "api_key": api_key,
}
search = GoogleSearch(params)
results = search.get_dict()
text_block = results.get("text_blocks")
print(text_block)
