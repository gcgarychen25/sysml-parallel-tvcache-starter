"""Standalone prototype and trajectory analysis; not yet hooked into Rust TVCache."""
from .cache.prototype import ParallelCache, ToolCall, ToolResult, BatchResult
__all__ = ["ParallelCache", "ToolCall", "ToolResult", "BatchResult"]
