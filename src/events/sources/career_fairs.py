"""Selected public London job fairs with explicitly advertised data roles."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.events.http import FetchError, fetch_html
from src.events.models import Event
from src.events.sources.standalone import page_text
from src.events.topics import CAREERS, CAREER_FAIRS

URL = "https://www.londonjobshow.co.uk/shepherdsbush/want-to-visit/"
TECH_URL = "https://www.londonjobshow.co.uk/shepherdsbush/want-to-exhibit/it-job-fair-london/"
LONDON = ZoneInfo("Europe/London")


def parse_london_job_show(html: str, tech_html: str) -> Event:
    """Accept the general fair only while the organiser advertises data roles."""
    text = page_text(html)
    tech_text = page_text(tech_html)
    match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*&\s*"
                      r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(20\d{2})\b", text, re.I)
    hours = re.search(r"(\d{1,2})\s*am\s*[–-]\s*(\d{1,2})\s*pm\s+on\s+both\s+days", text, re.I)
    if not match or not hours or not re.search(r"Westfield London", text, re.I):
        raise ValueError("London Job Show dates, hours or venue missing")
    if not re.search(r"Data Management Professionals", tech_text, re.I):
        raise ValueError("London Job Show no longer advertises data roles")
    first = datetime.strptime(f"{match[1]} {match[3]} {match[4]}", "%d %B %Y")
    last = datetime.strptime(f"{match[2]} {match[3]} {match[4]}", "%d %B %Y")
    if last != first + timedelta(days=1):
        raise ValueError("London Job Show dates are not consecutive")
    return Event(
        id=f"london-job-show-{match[4]}-{match[1]}-{match[3].lower()}",
        title="London Job Show (general careers fair, including data roles)",
        start_at=first.replace(hour=int(hours[1]), tzinfo=LONDON).isoformat(),
        end_at=last.replace(hour=int(hours[2]) + 12, tzinfo=LONDON).isoformat(),
        format="in_person", organiser="London Job Show", source="London Job Show",
        source_url=URL, venue_name="Westfield London, Shepherd's Bush",
        is_free=True, price_from_gbp=0.0, registration_status="open" if "Register free" in text else "unknown",
        topics=(CAREERS, CAREER_FAIRS),
    )


def get_events() -> tuple[list[Event], list[str]]:
    try:
        return [parse_london_job_show(fetch_html(URL), fetch_html(TECH_URL))], []
    except (FetchError, ValueError) as exc:
        return [], [f"London Job Show: {exc}"]
