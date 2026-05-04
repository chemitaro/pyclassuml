"""Framework-specific enrichment seams."""

from pyclassuml.frameworks.sqlalchemy import (
    SqlalchemyEnrichmentHints,
    extract_sqlalchemy_enrichment_hints,
)

__all__ = [
    "SqlalchemyEnrichmentHints",
    "extract_sqlalchemy_enrichment_hints",
]
