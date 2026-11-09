"""Importing this package registers all built-in parsers."""
from app.parsers import (  # noqa: F401
    archive_parser,
    binary_parser,
    image_parser,
    media_parser,
    office_parser,
    pdf_parser,
)
