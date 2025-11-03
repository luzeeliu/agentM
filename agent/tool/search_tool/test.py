import pprint

from search_engine_parser.core.engines.bing import Search as BingSearch
from search_engine_parser.core.engines.yahoo import Search as YahooSearch
try:
    # Optional: Only import Google if you want to test it
    from search_engine_parser.core.engines.baidu import Search as GoogleSearch
except Exception:
    GoogleSearch = None


# Minimal test for search_engine_parser (no agent tool).
QUERY = "who is taylor swift"
PAGE = 1  # page argument used by the library
TOP_N = 5


def extract_results(obj):
    """Extract list of {title,url,content} from SearchResult or dict-like."""
    # Try dict-like access first
    for accessor in (
        lambda k: obj.get(k),  # mapping style
        lambda k: obj[k],      # item access
        lambda k: getattr(obj, k, None),  # attribute access
    ):
        try:
            titles = accessor("titles") or []
            links = accessor("links") or []
            descs = accessor("descriptions") or []
            if isinstance(titles, list) and isinstance(links, list) and isinstance(descs, list):
                size = min(len(titles), len(links), len(descs))
                return [
                    {"title": titles[i], "url": links[i], "content": descs[i]}
                    for i in range(size)
                ]
        except Exception:
            pass
    # Fallback: try to convert to dict
    try:
        d = dict(obj)
        titles = d.get("titles", [])
        links = d.get("links", [])
        descs = d.get("descriptions", [])
        size = min(len(titles), len(links), len(descs))
        return [
            {"title": titles[i], "url": links[i], "content": descs[i]}
            for i in range(size)
        ]
    except Exception:
        return []


def try_engine(name, engine):
    try:
        res = engine.search(QUERY, PAGE)
        items = extract_results(res)
        if not items:
            print(f"{name}: No parsed items; raw object below")
            pprint.pprint(res)
        else:
            print(f"-------------{name} (top {min(TOP_N, len(items))})------------")
            for item in items[:TOP_N]:
                print(f"- {item['title']}\n  {item['url']}\n  {item['content']}")
    except Exception as e:
        print(f"ENGINE FAILURE: {name}\n{e}")


if __name__ == "__main__":
    # Google tends to flag automated traffic; run it last or skip.
    try_engine("Yahoo", YahooSearch())
    try_engine("Bing", BingSearch())
    if GoogleSearch is not None:
        try_engine("Google", GoogleSearch())
