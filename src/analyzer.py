"""Deep paper analysis using Claude (API or CLI) per-paper, 5-section English format."""

import re
import subprocess
import shutil
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from src import config

ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

MAX_HTML_TEXT_CHARS = 40000


def fetch_paper_metadata(arxiv_id: str) -> dict:
    """Fetch title, authors, abstract from arXiv API for a single paper."""
    clean_id = re.sub(r"v\d+$", "", arxiv_id)
    url = f"http://export.arxiv.org/api/query?id_list={clean_id}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DailyLLMBriefing/2.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            tree = ET.parse(resp)
    except Exception as e:
        print(f"  [WARN] Could not fetch metadata for {arxiv_id}: {e}")
        return {}

    root = tree.getroot()
    entry = root.find("atom:entry", ARXIV_NS)
    if entry is None:
        return {}

    title_el = entry.find("atom:title", ARXIV_NS)
    summary_el = entry.find("atom:summary", ARXIV_NS)
    authors = [a.find("atom:name", ARXIV_NS).text for a in entry.findall("atom:author", ARXIV_NS)]

    return {
        "title": title_el.text.strip().replace("\n", " ") if title_el is not None else "",
        "authors": authors,
        "abstract": summary_el.text.strip().replace("\n", " ") if summary_el is not None else "",
    }


def fetch_paper_html(arxiv_id: str) -> dict:
    """Fetch full text + Figure 1 URL from arxiv.org/html/{id}.

    Returns dict with 'text' (truncated body text) and 'figure1_url'.
    Falls back gracefully if HTML version is not available.
    """
    clean_id = re.sub(r"v\d+$", "", arxiv_id)
    url = f"https://arxiv.org/html/{clean_id}"

    headers = {"User-Agent": "DailyLLMBriefing/2.0"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            html = resp.read().decode("utf-8")
            final_url = resp.url  # May redirect (e.g., to versioned URL)
    except Exception as e:
        print(f"  [WARN] Could not fetch HTML for {arxiv_id}: {e}")
        return {"text": "", "figure1_url": ""}

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # Extract body text — prefer <section> elements (skips header metadata)
    # Remove references/bibliography section to save space
    for bib in soup.find_all("section", class_="ltx_bibliography"):
        bib.decompose()
    for bib in soup.find_all("section", id=lambda x: x and "bib" in x.lower()):
        bib.decompose()

    sections = soup.find_all("section")
    if sections:
        parts = []
        for sec in sections:
            for tag in sec.find_all(["script", "style", "nav"]):
                tag.decompose()
            parts.append(sec.get_text(separator="\n", strip=True))
        text = "\n\n".join(parts)
    else:
        article = soup.find("article") or soup.find("div", class_="ltx_page_content") or soup.body
        text = ""
        if article:
            for tag in article.find_all(["script", "style", "nav"]):
                tag.decompose()
            text = article.get_text(separator="\n", strip=True)

    # Extract Figure 1 URL (first <figure> with an <img>)
    # Use <base href> if present, otherwise resolve relative to page URL
    base_tag = soup.find("base")
    if base_tag and base_tag.get("href"):
        base_url = urllib.parse.urljoin(final_url, base_tag["href"])
    else:
        base_url = final_url
    figure1_url = ""
    for fig in soup.find_all("figure"):
        img = fig.find("img")
        if img and img.get("src"):
            figure1_url = urllib.parse.urljoin(base_url, img["src"])
            break

    return {"text": text[:MAX_HTML_TEXT_CHARS], "figure1_url": figure1_url}


def _build_prompt(paper: dict) -> str:
    """Build the 5-section analysis prompt."""
    authors_str = ", ".join(paper.get("authors", [])[:5])
    if len(paper.get("authors", [])) > 5:
        authors_str += " et al."

    full_text = paper.get("full_text", "")
    text_section = f"\n\nFull paper text:\n{full_text}" if full_text else ""

    return f"""Please provide an in-depth analysis of the following paper in English.

Title: {paper.get('title', 'N/A')}
Authors: {authors_str}
URL: {paper.get('url', 'N/A')}
Track: {paper.get('track', 'N/A')}
Abstract: {paper.get('abstract', 'N/A')}{text_section}

Analyze the paper using the following 5 sections:

📋 Problem Definition: What problem is the paper trying to solve? (2-3 sentences)

📚 Background / Related Works: What related or prior work exists in this area? (2-3 sentences, include specific paper names)

🔬 Main Methodology: Core methodology and contributions (3-5 sentences, technically precise)

🧪 Evaluation: What setting was used for evaluation, how was it conducted, and what were the results? (2-3 sentences, include specific numbers)

💡 Key Intuition & Lesson: What are the key insights and takeaways from this paper? (2-3 sentences)

Important notes:
- Write entirely in English
- Be specific — include concrete methodology details and numbers, not superficial summaries
- Accurately convey the core ideas of the paper
- Do not use **bold** markdown formatting. Write in plain text without emphasis
- Do not use disclaimer phrases like "access is limited", "I recommend checking the original", "in the excerpt", "access is blocked", "tool access", etc.
- All information needed for analysis (full paper text, abstract, metadata) is already provided above. Analyze using only the provided text without using external tools (WebFetch, Semantic Scholar, etc.)
- Do not use --- dividers or ### markdown headers"""


def _analyze_via_api(prompt: str) -> str:
    """Analyze using Anthropic API (requires ANTHROPIC_API_KEY)."""
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=config.ANALYSIS_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _analyze_via_cli(prompt: str) -> str:
    """Analyze using Claude Code CLI (uses Pro/Pro Max subscription).

    Passes prompt via stdin to avoid OS argument length limits with long texts.
    """
    claude_path = shutil.which("claude")
    if not claude_path:
        raise RuntimeError(
            "claude CLI not found. Install Claude Code or set ANTHROPIC_API_KEY."
        )

    result = subprocess.run(
        [claude_path, "-p", "-", "--output-format", "text", "--allowedTools", ""],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr[:200]}")
    return result.stdout.strip()


def analyze_paper(paper: dict) -> str:
    """Generate deep 5-section Korean analysis for a single paper.

    Also sets paper['figure1_url'] if Figure 1 is found in the HTML version.

    Routing:
      - ANTHROPIC_API_KEY set → Anthropic API (pay-per-token)
      - ANTHROPIC_API_KEY empty → Claude Code CLI (Pro/Pro Max subscription)
    """
    # Fetch metadata if missing (track pool papers only have arxiv_id)
    if not paper.get("abstract") or paper.get("source") == "track_pool":
        print(f"  Fetching metadata for {paper['id']}...")
        meta = fetch_paper_metadata(paper["id"])
        if meta:
            paper["title"] = meta.get("title", paper.get("title", ""))
            paper["authors"] = meta.get("authors", paper.get("authors", []))
            paper["abstract"] = meta.get("abstract", paper.get("abstract", ""))

    # Fetch HTML full text + Figure 1
    print(f"  Fetching HTML for {paper['id']}...")
    html_data = fetch_paper_html(paper["id"])
    if html_data["text"]:
        paper["full_text"] = html_data["text"]
        print(f"  HTML text: {len(html_data['text'])} chars")
    if html_data["figure1_url"]:
        paper["figure1_url"] = html_data["figure1_url"]
        print(f"  Figure 1: {html_data['figure1_url'][:80]}...")

    prompt = _build_prompt(paper)
    use_api = bool(config.ANTHROPIC_API_KEY)

    def _run_analysis(p: str) -> str:
        if use_api:
            print(f"  Using Anthropic API ({config.CLAUDE_MODEL})")
            return _analyze_via_api(p)
        else:
            print(f"  Using Claude Code CLI (subscription)")
            return _analyze_via_cli(p)

    try:
        result = _run_analysis(prompt)
        if len(result) < 100:
            raise RuntimeError(f"Analysis too short ({len(result)} chars), likely failed")
        return result
    except Exception as e:
        print(f"  [WARN] Analysis failed with full text: {e}")
        # Fallback: retry with abstract only (no full_text)
        if paper.get("full_text"):
            print(f"  Retrying with abstract only...")
            paper.pop("full_text", None)
            fallback_prompt = _build_prompt(paper)
            try:
                return _run_analysis(fallback_prompt)
            except Exception as e2:
                print(f"  [ERROR] Fallback analysis also failed: {e2}")
                return ""
        print(f"  [ERROR] Analysis failed: {e}")
        return ""
