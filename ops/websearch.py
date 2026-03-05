#!/usr/bin/env python3
"""
Web search via DuckDuckGo — works globally (no API key, no geo-restriction).

Used by the CC agent via Bash tool since Claude Code's built-in WebSearch
only works in the US and this bot runs in Australia.

Usage:
  python ops/websearch.py "your query here"
  python ops/websearch.py "AI news for coaches" --max 5
  python ops/websearch.py "n8n automation tutorial" --news
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def search_web(query: str, max_results: int = 5) -> list[dict]:
    from ddgs import DDGS
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def search_news(query: str, max_results: int = 5) -> list[dict]:
    from ddgs import DDGS
    with DDGS() as ddgs:
        return list(ddgs.news(query, max_results=max_results))


def format_results(results: list[dict], mode: str = "web") -> str:
    if not results:
        return "No results found."
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "No title")
        url = r.get("url", r.get("href", ""))
        snippet = r.get("body", r.get("description", ""))[:300]
        if mode == "news":
            date = r.get("date", "")
            source = r.get("source", "")
            lines.append(f"{i}. {title}")
            if source or date:
                lines.append(f"   {source} {date}".strip())
        else:
            lines.append(f"{i}. {title}")
        lines.append(f"   {url}")
        if snippet:
            lines.append(f"   {snippet}")
        lines.append("")
    return "\n".join(lines).strip()


def main():
    parser = argparse.ArgumentParser(description="Web search via DuckDuckGo")
    parser.add_argument("query", nargs="+", help="Search query")
    parser.add_argument("--max", type=int, default=5, help="Max results (default: 5)")
    parser.add_argument("--news", action="store_true", help="Search news instead of web")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    query = " ".join(args.query)
    try:
        if args.news:
            results = search_news(query, args.max)
        else:
            results = search_web(query, args.max)

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            mode = "news" if args.news else "web"
            print(f"Search: {query}\n")
            print(format_results(results, mode))
    except Exception as e:
        print(f"Search failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
