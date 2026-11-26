"""Tests for the typed loop tool registry (schemas + approval flags)."""

import pytest
from pydantic import ValidationError

from hinaa_api.harness.loop_tools import (
    TOOL_REGISTRY,
    describe_tools,
    validate_action,
)


def test_registry_has_five_tools_with_approval_flags():
    assert set(TOOL_REGISTRY) == {"write_file", "delete_file", "run_command", "read_file", "list_files"}
    side_effects = {name: spec.side_effect for name, spec in TOOL_REGISTRY.items()}
    assert side_effects == {
        "write_file": True,
        "delete_file": True,
        "run_command": True,
        "read_file": False,
        "list_files": False,
    }


def test_describe_tools_lists_every_tool():
    text = describe_tools()
    for name in TOOL_REGISTRY:
        assert name in text


def test_read_only_tools_auto_approved():
    spec, args, error = validate_action({"type": "read_file", "path": "src/app.py"})
    assert error is None
    assert spec.approval({"type": "read_file"}) == "auto"
    assert args.path == "src/app.py"

    spec, args, error = validate_action({"type": "list_files"})
    assert error is None
    assert args.pattern == "**/*"


def test_side_effecting_tool_without_confirm_is_refused():
    spec, args, error = validate_action({"type": "write_file", "path": "a.txt", "content": "hi"})
    assert spec is TOOL_REGISTRY["write_file"]
    assert args is None
    assert error is not None and error.startswith("blocked:")


def test_side_effecting_tool_with_confirm_true_is_approved():
    spec, args, error = validate_action(
        {"type": "write_file", "path": "a.txt", "content": "hi", "confirm": True}
    )
    assert error is None
    assert args.content == "hi"


def test_delete_and_run_command_require_confirm_too():
    _, _, err1 = validate_action({"type": "delete_file", "path": "a.txt"})
    _, _, err2 = validate_action({"type": "run_command", "command": "ls"})
    assert err1 is not None and err2 is not None
    assert all(e.startswith("blocked:") for e in (err1, err2))


def test_confirm_false_still_refused():
    _, _, error = validate_action({"type": "delete_file", "path": "a.txt", "confirm": False})
    assert error is not None and error.startswith("blocked:")


def test_unknown_and_non_object_actions_error():
    _, _, err1 = validate_action({"type": "explode", "confirm": True})
    _, _, err2 = validate_action("write the file please")
    assert "unknown action type" in err1
    assert err2 == "action is not an object"


def test_pydantic_validation_rejects_bad_args():
    with pytest.raises(ValidationError):
        TOOL_REGISTRY["read_file"].args_model.model_validate({"path": ""})
    with pytest.raises(ValidationError):
        TOOL_REGISTRY["run_command"].args_model.model_validate({"command": "   "})
    _, _, error = validate_action({"type": "read_file"})
    assert error is not None and error.startswith("invalid arguments")
