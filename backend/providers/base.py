"""
Base provider interfaces for IncidentIQ data sources.
"""

from abc import ABC, abstractmethod
from typing import Any


class LogProvider(ABC):
    """Interface for application log providers."""

    @abstractmethod
    def get_logs(self) -> Any:
        """Return application logs."""
        raise NotImplementedError


class MetricsProvider(ABC):
    """Interface for service metrics providers."""

    @abstractmethod
    def get_metrics(self) -> Any:
        """Return service metrics."""
        raise NotImplementedError


class DeploymentProvider(ABC):
    """Interface for deployment history providers."""

    @abstractmethod
    def get_deployments(self) -> Any:
        """Return deployment records."""
        raise NotImplementedError