"""Compatibility exports for the retained Borges geometry method."""
from ..geometry_update_methods.borges import BorgesUpdate, LocalSpace
from ..errors import UpdateRefused, refusal_from_value_error as _refusal
from .geometry import speed_ratio
