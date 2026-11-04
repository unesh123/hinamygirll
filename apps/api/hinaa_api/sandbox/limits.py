"""Resource quotas, memory limits, and timeout boundaries for code execution."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResourceLimits(BaseModel):
    """Resource boundaries strictly enforced on sandbox processes."""

    timeout_seconds: float = Field(default=30.0, description="Maximum wall-clock execution time in seconds.")
    cpu_seconds_limit: float = Field(default=20.0, description="Maximum total CPU time in seconds.")
    memory_mb_limit: int = Field(default=512, description="Maximum memory allocation in megabytes.")
    max_pids: int = Field(default=32, description="Maximum number of active processes in process tree.")
    max_output_bytes: int = Field(default=1024 * 1024, description="Maximum captured stdout/stderr buffer (1 MB).")
    max_disk_write_mb: int = Field(default=256, description="Maximum disk writes allowed in MB.")
    allow_network: bool = Field(default=False, description="Whether network egress is permitted (default False).")
