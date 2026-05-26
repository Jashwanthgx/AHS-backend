"""
Runs the 4/5ths (80%) disparate impact rule across all hiring decisions.
Called monthly by Celery Beat or on-demand by the recruiter dashboard.
"""
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
from pydantic import BaseModel
from typing import Optional

# langdetect is lightweight: pip install langdetect
try:
    from langdetect import detect as detect_lang, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

FOUR_FIFTHS_THRESHOLD = 0.80  # EEOC standard

class SegmentResult(BaseModel):
    segment_name: str
    dimension: str               # "language" | "resume_length" | "apply_hour" | "github_active"
    applications: int
    selected: int
    selection_rate: float
    impact_ratio: float          # relative to baseline group
    flag: str                    # "pass" | "watch" | "flag"

class BiasAuditReport(BaseModel):
    period_start: str
    period_end: str
    total_decisions: int
    flagged_segments: int
    segments: list[SegmentResult]
    summary: str
    generated_at: str

def _detect_language(text: str) -> str:
    if not LANGDETECT_AVAILABLE or not text:
        return "unknown"
    try:
        return detect_lang(text[:500])   # sample first 500 chars
    except Exception:
        return "unknown"

def _flag(ratio: float) -> str:
    if ratio >= FOUR_FIFTHS_THRESHOLD:
        return "pass"
    elif ratio >= 0.65:
        return "watch"
    return "flag"

def run_bias_audit(
    db,
    candidate_model,
    days_back: int = 30
) -> BiasAuditReport:
    """
    Full 4/5ths bias audit across 4 dimensions.
    Pass in the SQLAlchemy db session and Candidate model class.
    """
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    candidates = db.query(candidate_model).filter(
        candidate_model.created_at >= cutoff,
        candidate_model.status.in_(["selected", "rejected", "manual_review"])
    ).all()

    if not candidates:
        return BiasAuditReport(
            period_start=cutoff.date().isoformat(),
            period_end=datetime.utcnow().date().isoformat(),
            total_decisions=0,
            flagged_segments=0,
            segments=[],
            summary="No decided candidates in this period.",
            generated_at=datetime.utcnow().isoformat(),
        )

    segments: list[SegmentResult] = []

    # ── Dimension 1: Resume language ──────────────────────────────────
    lang_buckets: dict[str, list[bool]] = defaultdict(list)
    for c in candidates:
        lang = _detect_language(c.reason or "")  # reason contains AI summary of resume
        # Normalise to major groups
        lang_group = lang if lang in ("en", "es", "fr", "hi") else "other"
        lang_buckets[lang_group].append(c.status == "selected")

    lang_rates = {
        g: (sum(v) / len(v), len(v))
        for g, v in lang_buckets.items() if len(v) >= 5
    }
    baseline_rate = lang_rates.get("en", (0.5, 1))[0] or 0.5
    for group, (rate, count) in lang_rates.items():
        ratio = rate / baseline_rate if baseline_rate > 0 else 1.0
        segments.append(SegmentResult(
            segment_name=group,
            dimension="language",
            applications=count,
            selected=sum(lang_buckets[group]),
            selection_rate=round(rate, 3),
            impact_ratio=round(min(ratio, 1.0), 3),
            flag=_flag(ratio) if group != "en" else "pass",
        ))

    # ── Dimension 2: Resume length (using reason text as proxy) ───────
    short_res = [c for c in candidates if len(c.reason or "") < 200]
    long_res  = [c for c in candidates if len(c.reason or "") >= 200]
    if short_res and long_res:
        short_rate = sum(1 for c in short_res if c.status == "selected") / len(short_res)
        long_rate  = sum(1 for c in long_res  if c.status == "selected") / len(long_res)
        base_len = long_rate or 0.01
        segments.append(SegmentResult(
            segment_name="Short resume", dimension="resume_length",
            applications=len(short_res), selected=int(short_rate * len(short_res)),
            selection_rate=round(short_rate, 3),
            impact_ratio=round(min(short_rate / base_len, 1.0), 3),
            flag=_flag(short_rate / base_len),
        ))

    # ── Dimension 3: Application hour ─────────────────────────────────
    biz_hours  = [c for c in candidates if 9 <= c.created_at.hour < 18]
    off_hours  = [c for c in candidates if not (9 <= c.created_at.hour < 18)]
    if biz_hours and off_hours:
        biz_rate = sum(1 for c in biz_hours if c.status == "selected") / len(biz_hours)
        off_rate = sum(1 for c in off_hours if c.status == "selected") / len(off_hours)
        base_hr  = biz_rate or 0.01
        segments.append(SegmentResult(
            segment_name="Off-hours applicants", dimension="apply_hour",
            applications=len(off_hours), selected=int(off_rate * len(off_hours)),
            selection_rate=round(off_rate, 3),
            impact_ratio=round(min(off_rate / base_hr, 1.0), 3),
            flag=_flag(off_rate / base_hr),
        ))

    # ── Dimension 4: GitHub activity ──────────────────────────────────
    with_gh  = [c for c in candidates if c.github_url and "github.com" in (c.github_url or "")]
    without_gh = [c for c in candidates if not (c.github_url and "github.com" in (c.github_url or ""))]
    if with_gh and without_gh:
        gh_rate   = sum(1 for c in with_gh    if c.status == "selected") / len(with_gh)
        nogh_rate = sum(1 for c in without_gh if c.status == "selected") / len(without_gh)
        base_gh   = gh_rate or 0.01
        segments.append(SegmentResult(
            segment_name="No GitHub profile", dimension="github_active",
            applications=len(without_gh), selected=int(nogh_rate * len(without_gh)),
            selection_rate=round(nogh_rate, 3),
            impact_ratio=round(min(nogh_rate / base_gh, 1.0), 3),
            flag=_flag(nogh_rate / base_gh),
        ))

    flagged = sum(1 for s in segments if s.flag == "flag")
    watches  = sum(1 for s in segments if s.flag == "watch")
    summary = (
        f"{flagged} segment(s) flagged, {watches} under watch out of {len(segments)} tested. "
        + ("Review the flagged segments and audit the AI prompt for bias-inducing language." if flagged
           else "No significant disparate impact detected this period.")
    )

    return BiasAuditReport(
        period_start=cutoff.date().isoformat(),
        period_end=datetime.utcnow().date().isoformat(),
        total_decisions=len(candidates),
        flagged_segments=flagged,
        segments=segments,
        summary=summary,
        generated_at=datetime.utcnow().isoformat(),
    )

