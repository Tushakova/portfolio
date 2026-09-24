"""Controlled topic taxonomy for London Data Radar."""

import re

DATA_ANALYTICS = "Data Analytics"
PRODUCT_ANALYTICS = "Product Analytics"
DATA_SCIENCE = "Data Science"
AI_ML = "AI & Machine Learning"
DATA_ENGINEERING = "Data Engineering"
ANALYTICS_ENGINEERING = "Analytics Engineering"
EXPERIMENTATION = "Experimentation"
DATA_VISUALISATION = "Data Visualisation"
STATISTICS = "Statistics"
CAREERS = "Data Careers"

CAREER_EVENT_TITLE = re.compile(
    r"\b(?:career\s+(?:day|fair|event|talk|network|growth|change|journey|switch)|"
    r"careers?\s+in\s+data|hiring\s+(?:event|fair|manager)|"
    r"job\s+(?:fair|hunt|search)|recruit(?:er|ment)\s+(?:event|fair))\b",
    re.IGNORECASE,
)


def is_career_event(title: str) -> bool:
    """Only label events with an explicit career-oriented title."""
    return bool(CAREER_EVENT_TITLE.search(title))


ALL_TOPICS = frozenset(
    {
        DATA_ANALYTICS,
        PRODUCT_ANALYTICS,
        DATA_SCIENCE,
        AI_ML,
        DATA_ENGINEERING,
        ANALYTICS_ENGINEERING,
        EXPERIMENTATION,
        DATA_VISUALISATION,
        STATISTICS,
        CAREERS,
    }
)
