"""arXiv API search + institution-based search via Claude CLI for fresh paper discovery."""

import datetime
import json
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from src import config

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def search_arxiv(query: str, max_results: int = 30, days_back: int = None) -> list:
    """Search arXiv API and return papers within the time window."""
    if days_back is None:
        days_back = config.FRESH_DAYS_BACK

    cat_filter = " OR ".join(f"cat:{c}" for c in config.ARXIV_CATEGORIES)
    full_query = f"({query}) AND ({cat_filter})"

    params = urllib.parse.urlencode({
        "search_query": full_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })

    url = f"{ARXIV_API}?{params}"
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_back)
    papers = []

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DailyLLMBriefing/2.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            tree = ET.parse(resp)
    except Exception as e:
        print(f"  [WARN] arXiv query failed: {e}")
        return []

    root = tree.getroot()
    for entry in root.findall("atom:entry", ARXIV_NS):
        published_str = entry.find("atom:published", ARXIV_NS).text
        published = datetime.datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        if published < cutoff:
            continue

        arxiv_id = re.sub(r"v\d+$", "", entry.find("atom:id", ARXIV_NS).text.split("/abs/")[-1])
        title = entry.find("atom:title", ARXIV_NS).text.strip().replace("\n", " ")
        abstract = entry.find("atom:summary", ARXIV_NS).text.strip().replace("\n", " ")
        authors = [a.find("atom:name", ARXIV_NS).text for a in entry.findall("atom:author", ARXIV_NS)]
        categories = [c.get("term") for c in entry.findall("atom:category", ARXIV_NS)]
        affiliation_text = " ".join(authors).lower() + " " + abstract.lower()

        papers.append({
            "id": arxiv_id,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "categories": categories,
            "published": published.isoformat(),
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "affiliation_text": affiliation_text,
        })

    return papers


def _match_org(org_name: str) -> str:
    """Match HuggingFace org name to our ORG_BOOST list. Returns matched org or empty."""
    if not org_name:
        return ""
    org_lower = org_name.lower()
    # Mapping from HF org names to our ORG_BOOST names
    hf_to_org = {
        "openai": "openai",
        "anthropic": "anthropic",
        "meta": "meta", "fair": "meta",
        "nvidia": "nvidia",
        "google": "google", "deepmind": "google deepmind",
        "apple": "apple",
        "bytedance": "bytedance",
        "microsoft": "microsoft",
        "deepseek": "deepseek", "deepseek-ai": "deepseek",
        "alibaba": "alibaba", "qwen": "alibaba",
        "tencent": "tencent",
        "together": "together ai", "togetherai": "together ai",
        "berkeley": "uc berkeley",
        "stanford": "stanford",
        "mit": "mit",
        "cmu": "cmu", "carnegiemellon": "cmu",
    }
    for key, val in hf_to_org.items():
        if key in org_lower:
            return val
    return ""


def _fetch_hf_daily_papers() -> list[dict]:
    """Fetch trending papers from HuggingFace Daily Papers API.

    Filters for papers from monitored institutions and returns them
    with org info and high base score.
    """
    url = "https://huggingface.co/api/daily_papers"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DailyLLMBriefing/2.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] HF Daily Papers fetch failed: {e}")
        return []

    papers = []
    for entry in data:
        paper = entry.get("paper", {})
        arxiv_id = paper.get("id", "")
        if not arxiv_id or not re.match(r"\d{4}\.\d{4,5}", arxiv_id):
            continue

        # Check org from HF organization field
        hf_org = paper.get("organization") or entry.get("organization")
        org_name = ""
        if isinstance(hf_org, dict):
            org_name = hf_org.get("fullname", "") or hf_org.get("name", "")

        matched_org = _match_org(org_name)
        if not matched_org:
            continue

        title = paper.get("title", "")
        authors = [a.get("name", "") for a in paper.get("authors", [])]
        abstract = paper.get("summary", "")
        upvotes = paper.get("upvotes", 0)

        papers.append({
            "id": arxiv_id,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "categories": [],
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "org": matched_org,
            "source": "org_search",
            "affiliation_text": " ".join(authors).lower() + " " + abstract.lower(),
            "score": 20.0 + min(upvotes, 50),  # Base 20 + upvote bonus (capped)
        })

    return papers


def _classify_papers_via_cli(papers: list[dict]) -> dict:
    """Use Claude CLI to classify papers by track relevance.

    Returns dict of arxiv_id -> {"relevant": bool, "track": str}.
    """
    claude_path = shutil.which("claude")
    if not claude_path:
        print("  [WARN] Claude CLI not found, skipping classification")
        return {}

    track_info = "\n".join(
        f"  {i+1}. {t['name']}: {', '.join(t['positive_keywords'][:8])}"
        for i, t in enumerate(config.TRACKS)
    )

    paper_list = "\n".join(
        f"- {p['id']}: {p['title']}\n  Abstract: {p.get('abstract', '')[:300]}"
        for p in papers
    )

    prompt = f"""Classify whether the following papers are relevant to AI/ML systems researchers.

Research tracks:
{track_info}

Paper list:
{paper_list}

For each paper:
1. Determine if it falls under one of the above tracks (if not relevant, set relevant=false)
2. Specify the matching track name

Return JSON only (no other text):
{{"2603.12345": {{"relevant": true, "track": "ML Systems"}}, "2603.67890": {{"relevant": false, "track": ""}}}}"""

    try:
        result = subprocess.run(
            [claude_path, "-p", "-", "--output-format", "text", "--allowedTools", ""],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  [WARN] Classification CLI failed: {result.stderr[:200]}")
            return {}

        output = result.stdout.strip()
        start = output.find('{')
        end = output.rfind('}')
        if start == -1 or end == -1:
            print(f"  [WARN] No JSON found in classification output")
            return {}

        classified = json.loads(output[start:end + 1])
        relevant_count = sum(1 for v in classified.values() if v.get("relevant"))
        print(f"  Classification: {relevant_count}/{len(classified)} papers relevant to our tracks")
        return classified

    except subprocess.TimeoutExpired:
        print(f"  [WARN] Classification timed out")
        return {}
    except json.JSONDecodeError as e:
        print(f"  [WARN] Classification JSON parse failed: {e}")
        return {}
    except Exception as e:
        print(f"  [WARN] Classification failed: {e}")
        return {}


def collect_fresh_papers(fresh_db, archive_db) -> list[dict]:
    """Collect fresh papers: HF institution papers (primary) + arXiv keywords (supplementary)."""
    from src.scoring import score_paper

    all_papers = {}

    # 1. Primary: HuggingFace Daily Papers from monitored institutions
    print("  [Primary] Fetching papers from monitored institutions (HF Daily Papers)...")
    org_papers = _fetch_hf_daily_papers()
    for p in org_papers:
        if fresh_db.contains(p["id"]) or archive_db.contains(p["id"]):
            continue
        all_papers[p["id"]] = p

    new_org = len(all_papers)
    print(f"  Found {len(org_papers)} org papers, {new_org} new after dedup")
    for p in list(all_papers.values())[:5]:
        print(f"    [{p['org']}] {p['title'][:60]}")

    # 2. Supplementary: arXiv API keyword search
    print("  [Supplementary] arXiv keyword search...")
    queries = []
    for track in config.TRACKS:
        top_kws = track["positive_keywords"][:5]
        query = " OR ".join(f'"{kw}"' for kw in top_kws)
        queries.append(query)

    for q in queries:
        print(f"  Searching: {q[:80]}...")
        results = search_arxiv(q, max_results=30)
        for p in results:
            if fresh_db.contains(p["id"]) or archive_db.contains(p["id"]):
                continue
            if p["id"] not in all_papers:
                all_papers[p["id"]] = p
        time.sleep(3)  # arXiv rate limiting

    # Classify org papers via Claude CLI (track relevance + interest)
    org_in_pool = [p for p in all_papers.values() if p.get("source") == "org_search"]
    if org_in_pool:
        classified = _classify_papers_via_cli(org_in_pool)
        for p in org_in_pool:
            info = classified.get(p["id"])
            if info and info.get("relevant"):
                p["track"] = info.get("track", "Other")
            else:
                p["score"] = -1  # Mark for removal

    # Score keyword-search papers normally
    papers = list(all_papers.values())
    for p in papers:
        if p.get("source") == "org_search":
            continue  # Already classified by Claude
        score, track = score_paper(p)
        p["score"] = score
        p["track"] = track

    # Filter out rejected papers (score < 0)
    papers = [p for p in papers if p["score"] >= 0]
    papers.sort(key=lambda x: x["score"], reverse=True)
    return papers
