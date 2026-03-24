"""GitHub archiving: daily markdown, README rebuild, git commit & push."""

import datetime
import os
import subprocess

from src import config
from src.dedup import ArchiveDB

# Root of the git repo (one level up from src/)
ROOT_DIR = os.path.dirname(config.REPO_DIR)


def md_escape(s: str) -> str:
    """Escape pipe characters for Markdown table cells."""
    return s.replace("|", "\\|")


def save_daily_markdown(
    date: datetime.date,
    papers: list[dict],
    analyses: list[str],
):
    """Write daily briefing markdown file."""
    year_month = date.strftime("%Y/%m")
    filename = date.strftime("%Y-%m-%d.md")
    dir_path = os.path.join(config.REPO_DIR, year_month)
    os.makedirs(dir_path, exist_ok=True)

    filepath = os.path.join(dir_path, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# 📚 AI/LLM Daily Paper Briefing - {date.isoformat()}\n\n")
        f.write(f"> Auto-generated | Top 2 papers analyzed across 5 tracks\n\n")

        # Paper list table
        f.write("## 📋 Paper List\n\n")
        f.write("| # | Title | Track | Source | Link |\n")
        f.write("|---|-------|-------|--------|------|\n")
        for i, p in enumerate(papers, 1):
            title = md_escape(p.get("title", p.get("id", "")))
            track = p.get("track", "Other")
            source = "Fresh" if p.get("source") == "arxiv_fresh" else "Track Pool"
            url = p.get("url", "")
            f.write(f"| {i} | {title} | {track} | {source} | [arXiv]({url}) |\n")

        # Detailed analyses
        f.write("\n## 📝 Detailed Analysis\n\n")
        for i, (paper, analysis) in enumerate(zip(papers, analyses)):
            title = paper.get("title", paper.get("id", ""))
            track = paper.get("track", "Other")
            url = paper.get("url", "")
            f.write(f"### {i+1}. {title}\n\n")
            f.write(f"**Track**: {track} | **Link**: [arXiv]({url})\n\n")
            if analysis:
                f.write(f"{analysis}\n\n")
            else:
                f.write("_Analysis generation failed_\n\n")

    return filepath


def rebuild_readme(archive_db: ArchiveDB):
    """Update root README.md: preserve static content above marker, regenerate below."""
    readme_path = os.path.join(ROOT_DIR, "README.md")
    marker = "<!-- AUTO-GENERATED BELOW -->"

    # Read existing README and keep everything above the marker
    static_part = ""
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
        if marker in content:
            static_part = content[:content.index(marker)]
        else:
            static_part = content.rstrip() + "\n\n"

    # Collect archive entries from daily files (under src/YYYY/MM/)
    archive_entries = []
    for root, dirs, files in os.walk(config.REPO_DIR):
        for fname in files:
            if fname.endswith(".md") and fname[:4].isdigit() and len(fname) == 13:
                # Path relative to repo root (e.g., src/2026/03/2026-03-24.md)
                rel = os.path.relpath(os.path.join(root, fname), ROOT_DIR)
                date_str = fname.replace(".md", "")
                archive_entries.append((date_str, rel))
    archive_entries.sort(key=lambda x: x[0], reverse=True)

    # Group archived papers by track
    categorized: dict[str, list] = {}
    for pid, info in sorted(archive_db.data.items(), key=lambda x: x[1].get("date_briefed", ""), reverse=True):
        track = info.get("track", "Other")
        if track not in categorized:
            categorized[track] = []
        categorized[track].append({"id": pid, **info})

    # Write: static part + marker + auto-generated part
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(static_part)
        f.write(marker + "\n\n")

        # Recent papers by track
        f.write("## 📊 Recent Papers (by Track)\n\n")
        track_order = [t["name"] for t in config.TRACKS]
        for track_name in track_order:
            papers = categorized.get(track_name, [])
            if not papers:
                continue
            f.write(f"### {track_name}\n\n")
            f.write("| Date | Title | Link |\n")
            f.write("|------|-------|------|\n")
            for info in papers[:20]:  # Last 20 per track
                date = info.get("date_briefed", "")
                title = md_escape(info.get("title", info.get("id", "")))
                url = f"https://arxiv.org/abs/{info.get('id', info.get('arxiv_id', ''))}"
                f.write(f"| {date} | {title} | [arXiv]({url}) |\n")
            f.write("\n")

        # Archive
        f.write("## 📚 Briefing Archive\n\n")
        for date_str, rel_path in archive_entries:
            f.write(f"- [{date_str}](./{rel_path})\n")


def git_commit_and_push(date: datetime.date, daily_md_path: str):
    """Git add specific files, commit, and push."""
    os.chdir(ROOT_DIR)

    # Paths relative to repo root
    daily_rel = os.path.relpath(daily_md_path, ROOT_DIR)
    files_to_add = [
        daily_rel,
        "src/papers_db/fresh_db.json",
        "src/papers_db/archive_db.json",
        "src/papers_db/track_pool.json",
        "README.md",
    ]

    for f in files_to_add:
        if os.path.exists(os.path.join(ROOT_DIR, f)):
            subprocess.run(["git", "add", f], check=False)

    result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
    if result.returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", f"📚 Daily briefing: {date.isoformat()}"],
            check=True,
        )
        push_result = subprocess.run(["git", "push"], capture_output=True)
        if push_result.returncode != 0:
            subprocess.run(
                ["git", "push", "--set-upstream", "origin", "main"],
                check=True,
            )
        print(f"  Pushed to GitHub")
    else:
        print("  No changes to commit")
