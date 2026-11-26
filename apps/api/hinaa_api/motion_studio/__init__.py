"""Local, editable motion graphics. No model API or video subscription required."""

from .compiler import compile_composition
from .spec import MotionComposition

__all__ = ["MotionComposition", "compile_composition"]
