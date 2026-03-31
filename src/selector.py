"""Paper selection: 2 fresh (institution) + 1 track paper (round-robin), with fallback."""

from __future__ import annotations

import datetime
import json
import os
from typing import Optional

from src import config
from src.dedup import FreshDB, ArchiveDB

NUM_FRESH = 2
NUM_TRACK = 1
TOTAL_PAPERS = NUM_FRESH + NUM_TRACK


def _get_track_index(date: datetime.date) -> int:
    """Round-robin track selection: day_of_year % num_tracks."""
    return date.timetuple().tm_yday % len(config.TRACKS)


def _select_track_paper(
    track_index: int,
    archive_db: ArchiveDB,
    track_pool: dict,
    tried_tracks: set = None,
) -> Optional[dict]:
    """Select an unbriefed paper from the given track's pool.

    Returns paper dict or None if track is exhausted.
    """
    if tried_tracks is None:
        tried_tracks = set()

    tracks = config.TRACKS
    # Try all tracks (starting from track_index, wrapping around)
    for offset in range(len(tracks)):
        idx = (track_index + offset) % len(tracks)
        if idx in tried_tracks:
            continue

        track_name = tracks[idx]["name"]
        pool_papers = track_pool.get(track_name, [])

        # Pool-size warning
        unbriefed = [p for p in pool_papers if not archive_db.contains(p["arxiv_id"])]
        if len(unbriefed) < 5:
            print(f"  [WARN] Track '{track_name}' has only {len(unbriefed)} unbriefed papers")

        if not unbriefed:
            print(f"  [WARN] Track '{track_name}' pool exhausted, trying next track")
            tried_tracks.add(idx)
            continue

        # Pick the first unbriefed paper
        paper = unbriefed[0]
        tried_tracks.add(idx)
        return {
            "id": paper["arxiv_id"],
            "title": f"[Pool] {paper['arxiv_id']}",  # Title fetched later by analyzer
            "authors": [],
            "abstract": "",
            "url": f"https://arxiv.org/abs/{paper['arxiv_id']}",
            "track": track_name,
            "source": "track_pool",
            "source_repo": paper.get("source_repo", ""),
        }

    return None


def select_daily_papers(
    date: datetime.date,
    fresh_db: FreshDB,
    archive_db: ArchiveDB,
    track_pool: dict,
    fresh_papers: list[dict],
) -> list[dict]:
    """Select papers for today's briefing: up to 2 fresh + 1 track.

    Args:
        date: Today's date
        fresh_db: 30-day rolling dedup DB
        archive_db: Permanent dedup DB
        track_pool: Awesome repo paper pool
        fresh_papers: Pre-scored fresh papers (already filtered/deduped)

    Returns:
        List of paper dicts (target: 3, minimum: 2).

    Raises:
        RuntimeError if unable to select at least 2 papers.
    """
    selected = []
    selected_ids = set()
    track_index = _get_track_index(date)
    tried_tracks = set()

    # 1. Fresh papers: top 2 scored papers (institution papers prioritized by score)
    for paper in fresh_papers[:NUM_FRESH]:
        paper["source"] = "arxiv_fresh"
        selected.append(paper)
        selected_ids.add(paper["id"])
        fresh_db.add(paper["id"], {
            "title": paper["title"],
            "track": paper.get("track", "Other"),
            "org": paper.get("org", ""),
            "score": paper.get("score", 0),
            "date": date.isoformat(),
        })

    # 2. Track paper: round-robin from pool
    track_paper = _select_track_paper(track_index, archive_db, track_pool, tried_tracks)
    if track_paper and track_paper["id"] not in selected_ids:
        selected.append(track_paper)
        selected_ids.add(track_paper["id"])
        archive_db.add(track_paper["id"], {
            "title": track_paper["title"],
            "track": track_paper["track"],
            "date_briefed": date.isoformat(),
        })

    # 3. Fallback: fill remaining slots from track pool or fresh papers
    while len(selected) < 2:
        # Try more fresh papers
        for paper in fresh_papers:
            if paper["id"] not in selected_ids:
                paper["source"] = "arxiv_fresh"
                selected.append(paper)
                selected_ids.add(paper["id"])
                fresh_db.add(paper["id"], {
                    "title": paper["title"],
                    "track": paper.get("track", "Other"),
                    "score": paper.get("score", 0),
                    "date": date.isoformat(),
                })
                break
        else:
            # Try more track papers
            next_idx = (track_index + len(tried_tracks)) % len(config.TRACKS)
            fallback = _select_track_paper(next_idx, archive_db, track_pool, tried_tracks)
            if fallback and fallback["id"] not in selected_ids:
                selected.append(fallback)
                selected_ids.add(fallback["id"])
                archive_db.add(fallback["id"], {
                    "title": fallback["title"],
                    "track": fallback["track"],
                    "date_briefed": date.isoformat(),
                })
            else:
                break

    if len(selected) < 2:
        raise RuntimeError(
            f"Could not select 2 papers. Only found {len(selected)}. "
            "Track pools may be exhausted. Run crawler to refresh."
        )

    return selected
