"""Parser plugin interface.

Every format parser implements this interface so new formats can be added
without touching the rest of the application. `get_capabilities` must be
honest about what the parser can and cannot do for the given file, since
the UI shows this directly to the user.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.models.schemas import Capability, MetadataSection


class BaseParser(ABC):
    #: short machine name, e.g. "image", "video", "pdf"
    name: str = "base"

    @abstractmethod
    def supports(self, detected_format: str, mime_type: str, extension: str) -> bool:
        """Return True if this parser should handle the given file."""

    @abstractmethod
    def extract_metadata(self, path: Path) -> list[MetadataSection]:
        """Extract metadata sections. Must never raise for routine parse
        failures — those go into a section with status=FAILED instead."""

    def get_capabilities(self, path: Path) -> list[Capability]:
        return []


_REGISTRY: list[BaseParser] = []


def register(parser: BaseParser) -> None:
    _REGISTRY.append(parser)


def parsers_for(detected_format: str, mime_type: str, extension: str) -> list[BaseParser]:
    return [p for p in _REGISTRY if p.supports(detected_format, mime_type, extension)]


def all_parsers() -> list[BaseParser]:
    return list(_REGISTRY)
