class IngestionError(Exception):
    """A document cannot be ingested. The message is user-readable and safe to show (no stack, no document text)."""
