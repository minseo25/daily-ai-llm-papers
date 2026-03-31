"""Deep paper analysis using Claude (API or CLI) per-paper, 5-section Korean format."""

import re
import subprocess
import shutil
import time
import urllib.error
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

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DailyLLMBriefing/2.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                tree = ET.parse(resp)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 10 * (attempt + 1)
                print(f"  [WARN] arXiv rate limited, retrying in {wait}s...")
                time.sleep(wait)
                continue
            print(f"  [WARN] Could not fetch metadata for {arxiv_id}: {e}")
            return {}
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
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                html = resp.read().decode("utf-8")
                final_url = resp.url  # May redirect (e.g., to versioned URL)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 10 * (attempt + 1)
                print(f"  [WARN] arXiv rate limited, retrying in {wait}s...")
                time.sleep(wait)
                continue
            print(f"  [WARN] Could not fetch HTML for {arxiv_id}: {e}")
            return {"text": "", "figure1_url": ""}
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
    text_section = f"\n\n논문 본문:\n{full_text}" if full_text else ""

    return f"""아래 논문을 한국어로 깊이 있게 분석해주세요.

Title: {paper.get('title', 'N/A')}
Authors: {authors_str}
URL: {paper.get('url', 'N/A')}
Track: {paper.get('track', 'N/A')}
Abstract: {paper.get('abstract', 'N/A')}{text_section}

아래 5개 항목으로 분석해주세요:

📋 Problem Definition: 어떤 문제를 해결하려고 했는지 (2-3문장)

📚 Background / Related Works: 관련된 작업이나 선행작업에는 뭐가 있는지 (2-3문장, 구체적 논문명 포함)

🔬 Main Methodology: 핵심 방법론 및 기여 (3-5문장, 기술적으로 정확하게)

🧪 Evaluation: 어떤 setting에서 어떻게 evaluation을 했고 결과가 어땠는지 (2-3문장, 구체적 수치 포함)

💡 Key Intuition & Lesson: 이 논문에서 얻을 수 있는 핵심 인사이트 및 교훈 (2-3문장)

주의사항:
- 반드시 한국어로 작성
- 피상적이지 않게, 구체적인 방법론과 수치를 포함해서 작성
- 논문의 핵심 아이디어를 정확히 전달
- **bold** 마크다운 강조 표시를 사용하지 말 것. 강조 없이 일반 텍스트로 작성
- "접근이 제한되어", "원문을 확인하시는 것을 권장", "발췌본에는", "권한이 차단", "도구 접근" 등의 면책 표현을 사용하지 말 것
- 분석에 필요한 모든 정보(논문 본문, abstract, 메타데이터)는 이미 위에 제공되어 있음. 외부 도구(WebFetch, Semantic Scholar 등)를 사용할 필요 없이 제공된 텍스트만으로 분석할 것
- --- 구분선이나 ### 마크다운 헤더를 사용하지 말 것"""


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
