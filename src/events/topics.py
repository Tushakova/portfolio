"""Controlled topic taxonomy for London Data Radar."""

DATA_ANALYTICS = "Data Analytics"
PRODUCT_ANALYTICS = "Product Analytics"
DATA_SCIENCE = "Data Science"
AI_ML = "AI & Machine Learning"
DATA_ENGINEERING = "Data Engineering"
ANALYTICS_ENGINEERING = "Analytics Engineering"
EXPERIMENTATION = "Experimentation"
DATA_VISUALISATION = "Data Visualisation"
STATISTICS = "Statistics"


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
    }
)
