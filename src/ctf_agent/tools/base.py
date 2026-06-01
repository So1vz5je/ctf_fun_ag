"""Base interface for CTF solving tools."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseTool(ABC):
    """Abstract base class for all CTF tools."""

    name: str = ""
    description: str = ""

    @abstractmethod
    async def run(self, input_data: str | dict) -> str:
        """Execute the tool and return textual output."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"
