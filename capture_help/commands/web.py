import html
import re
import urllib.parse

import httpx
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, stream_response

console = Console()

WEB_PROMPT = """You are a technical web documentation specialist.
Answer the user's query using the live search results below. Cite sources by title.

Search results for: '{query}'

{results}

Instructions:
1. Answer directly with crisp, production-grade guidance and code examples.
2. If results are insufficient, say so plainly instead of guessing.
3. List the most relevant sources at the end under "## Sources"."""

DUCKDUCKGO_SEARCH_URL = "https://lite.duckduckgo.com/lite/"
_BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
_MAX_RESULTS = 6
_TIMEOUT = 10.0


def _fetch_search_results(query: str) -> list:
    """Search DuckDuckGo lite (no API key required) and return parsed results."""
    try:
        resp = httpx.get(
            DUCKDUCKGO_SEARCH_URL,
            params={"q": query},
            headers={"User-Agent": _BROWSER_UA},
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as e:
        console.print(f"[bold yellow]! Live web search unavailable ({e}). Falling back to model knowledge only.[/bold yellow]")
        return []

    link_pattern = re.compile(
        r"<a[^>]*href=\"[^\"]*uddg=([^&\"]+)[^\"]*\"[^>]*class='result-link'>(.*?)</a>",
        re.DOTALL,
    )
    results = []
    for m in link_pattern.finditer(resp.text):
        if len(results) >= _MAX_RESULTS:
            break
        url = urllib.parse.unquote(m.group(1))
        # Skip sponsored/advertised results (Bing-served ads via DuckDuckGo).
        if any(token in url for token in ("ad_domain", "ad_provider", "aclick")):
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        after = resp.text[m.end():]
        snippet_match = re.search(r"class='result-snippet'>(.*?)</td>", after, re.DOTALL)
        snippet = html.unescape(re.sub(r"<[^>]+>", "", snippet_match.group(1))).strip() if snippet_match else ""
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def _format_results(results: list) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}\n    URL: {r['url']}\n    {r['snippet'][:300]}")
    return "\n\n".join(lines) if lines else "No live results found."


def web_command(query: str):
    """Search live web documentation and answer technical questions."""
    print_header("Web Search & Documentation", query)
    console.print(f"[bold cyan]🌐 Searching web & docs for:[/bold cyan] [bold white]'{query}'[/bold white]...\n")

    results = _fetch_search_results(query)
    provider = get_provider()
    prompt = WEB_PROMPT.format(query=query, results=_format_results(results))
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
