"""
Elliptical target simulation configuration.
"""
from .base_config import *  # noqa: F401,F403

TARGET_SHAPE = "ellipse"
TARGET_SEMI_MAJOR = 0.07  # m
TARGET_SEMI_MINOR = 0.035  # m
TARGET_SIZE = max(TARGET_SEMI_MAJOR, TARGET_SEMI_MINOR)
