"""Connectors that publish process events to a digital-twin platform."""

from tiger_poc.connectors.base import TwinConnector
from tiger_poc.connectors.local_sink import LocalSinkConnector

__all__ = ["LocalSinkConnector", "TwinConnector"]
