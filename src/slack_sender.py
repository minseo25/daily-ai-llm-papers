"""Slack DM delivery: header + per-paper analysis messages + Figure 1 images."""

import os
import tempfile
import time
import urllib.request

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from src import config


def _split_message(text: str, max_len: int = 3800) -> list[str]:
    """Split text into chunks respecting Slack's 4000 char limit."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len and current:
            chunks.append(current)
            current = line
        else:
            current += "\n" + line if current else line
    if current:
        chunks.append(current)
    return chunks


def _upload_figure(client: WebClient, channel: str, image_url: str,
                   paper_num: int, paper_title: str):
    """Download Figure 1 from arXiv HTML and upload to Slack."""
    headers = {"User-Agent": "DailyLLMBriefing/2.0"}
    try:
        req = urllib.request.Request(image_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            image_data = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except Exception as e:
        print(f"  [WARN] Could not download Figure 1 for paper {paper_num}: {e}")
        return

    ext = ".png"
    if "jpeg" in content_type or "jpg" in content_type:
        ext = ".jpg"
    elif "svg" in content_type:
        ext = ".svg"

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(image_data)
            tmp_path = f.name

        client.files_upload_v2(
            channel=channel,
            file=tmp_path,
        )
    except SlackApiError as e:
        print(f"  [WARN] Could not upload Figure 1 for paper {paper_num}: {e}")
    except Exception as e:
        print(f"  [WARN] Figure 1 upload failed for paper {paper_num}: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def send_briefing(date_str: str, papers: list[dict], analyses: list[str]):
    """Send daily briefing to Slack DM.

    Sends: 1 header + per-paper (analysis message + Figure 1 image).
    """
    client = WebClient(token=config.SLACK_BOT_TOKEN)

    # Header message
    lines = [f"🤖 [{date_str}] AI/LLM Daily Paper Briefing\n"]
    for i, p in enumerate(papers, 1):
        track = p.get("track", "Other")
        title = p.get("title", p.get("id", "Unknown"))
        org = p.get("org", "")
        org_label = f" | 🏢 {org}" if org else ""
        lines.append(f"{i}. {title}\n   [{track}]{org_label}")
    header = "\n".join(lines)

    try:
        client.chat_postMessage(channel=config.SLACK_CHANNEL, text=header)
    except SlackApiError as e:
        print(f"  [ERROR] Slack header: {e}")

    # Per-paper analysis messages + Figure 1
    for i, (paper, analysis) in enumerate(zip(papers, analyses)):
        if not analysis:
            error_msg = f"⚠️ Paper {i+1} ({paper.get('title', paper['id'])}): analysis generation failed"
            try:
                client.chat_postMessage(channel=config.SLACK_CHANNEL, text=error_msg)
            except SlackApiError as e:
                print(f"  [ERROR] Slack error msg: {e}")
            continue

        title = paper.get("title", paper.get("id", "Unknown"))
        track = paper.get("track", "Other")
        url = paper.get("url", "")
        org = paper.get("org", "")
        org_line = f"\n🏢 {org}" if org else ""
        prefix = f"📄 *{i+1}. {title}*\n🔗 {url}\n🏷️ {track}{org_line}\n\n"
        full_msg = prefix + analysis

        chunks = _split_message(full_msg)
        for chunk in chunks:
            try:
                client.chat_postMessage(channel=config.SLACK_CHANNEL, text=chunk)
                time.sleep(1)
            except SlackApiError as e:
                print(f"  [ERROR] Slack paper {i+1}: {e}")

        # Upload Figure 1 if available
        figure1_url = paper.get("figure1_url")
        if figure1_url:
            time.sleep(2)  # Ensure message ordering before file upload
            _upload_figure(client, config.SLACK_CHANNEL, figure1_url, i + 1, title)
            time.sleep(5)
