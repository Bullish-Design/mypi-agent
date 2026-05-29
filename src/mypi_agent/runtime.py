from __future__ import annotations

from .base_model import AlliumBase


class RuntimePolicyResult(AlliumBase):
    runtime_env_load_attempted: bool
    runtime_env_load_completed: bool
    config_write_attempted: bool
    config_write_blocked: bool
    secrets_available_at_evaluation_time: bool
    secrets_written_to_generated_config: bool
    missing_env_files_warning: bool
    warning_reason_missing_env_files_only: bool


def evaluate_runtime_policy() -> RuntimePolicyResult:
    return RuntimePolicyResult(
        runtime_env_load_attempted=True,
        runtime_env_load_completed=True,
        config_write_attempted=False,
        config_write_blocked=True,
        secrets_available_at_evaluation_time=False,
        secrets_written_to_generated_config=False,
        missing_env_files_warning=True,
        warning_reason_missing_env_files_only=True,
    )
