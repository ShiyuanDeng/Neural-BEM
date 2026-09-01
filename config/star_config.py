"""
Smooth star-shaped target simulation configuration.
"""
from .base_config import *  # noqa: F401,F403

TARGET_SHAPE = "star"
TARGET_MEAN_RADIUS = 0.05  # m
TARGET_STAR_AMPLITUDE = 0.25
TARGET_STAR_LOBES = 5
TARGET_SIZE = TARGET_MEAN_RADIUS * (1.0 + abs(TARGET_STAR_AMPLITUDE))
