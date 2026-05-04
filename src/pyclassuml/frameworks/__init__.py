"""Framework-specific enrichment seams."""

from pyclassuml.frameworks.pydantic import (
    PydanticEnrichmentHints,
    extract_pydantic_enrichment_hints,
)
from pyclassuml.frameworks.sqlalchemy import (
    SqlalchemyEnrichmentHints,
    extract_sqlalchemy_enrichment_hints,
)

__all__ = [
    "PydanticEnrichmentHints",
    "SqlalchemyEnrichmentHints",
    "extract_pydantic_enrichment_hints",
    "extract_sqlalchemy_enrichment_hints",
]
