"""
Compatibility alias for the default circular target configuration.

New shape-specific code should import ``config.circle_config`` or
``config.square_config`` directly.
"""
from .circle_config import *  # noqa: F401,F403
