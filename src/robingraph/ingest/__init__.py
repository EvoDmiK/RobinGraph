"""Canonical staging validation and future source adapters."""

from .validation import ValidationIssue, validate_source_registry_record, validate_staging_record

__all__ = ["ValidationIssue", "validate_source_registry_record", "validate_staging_record"]
