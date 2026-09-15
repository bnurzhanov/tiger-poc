"""Perception workloads that turn frames into observations."""

from tiger_poc.perception.base import PerceptionWorkload
from tiger_poc.perception.motion import MotionWorkload
from tiger_poc.perception.observation import Observation

__all__ = ["MotionWorkload", "Observation", "PerceptionWorkload"]
