from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """Stub interface for Phase 6 plugin system."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    def register(self, app): ...
    def unregister(self, app): ...
