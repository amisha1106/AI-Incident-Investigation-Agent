"""
Local data providers for IncidentIQ.

These providers wrap the existing local data loaders so the
current investigation behavior remains unchanged while allowing
real external providers to be added later.
"""

from utils.parser import (
    load_logs,
    load_metrics,
    load_deployments,
)

from providers.base import (
    LogProvider,
    MetricsProvider,
    DeploymentProvider,
)


class LocalLogProvider(LogProvider):
    """Provides application logs from IncidentIQ's local data source."""

    def get_logs(self):
        return load_logs()


class LocalMetricsProvider(MetricsProvider):
    """Provides service metrics from IncidentIQ's local data source."""

    def get_metrics(self):
        return load_metrics()


class LocalDeploymentProvider(DeploymentProvider):
    """Provides deployment history from IncidentIQ's local data source."""

    def get_deployments(self):
        return load_deployments()