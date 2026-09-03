import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[2]


def _load_script(script_name: str):
    script_path = ROOT / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_claim_summary_detects_duplicates_missing_and_instances() -> None:
    verifier = _load_script("verify_http_load_test.py")
    rows = [
        {"status": "200", "task_id": "10", "instance": "app-1"},
        {"status": "200", "task_id": "10", "instance": "app-2"},
        {"status": "200", "task_id": "11", "instance": "app-1"},
    ]

    summary = verifier.summarize_claim_results({10, 11, 12}, rows)

    assert summary["successful_responses"] == 3
    assert summary["duplicate_count"] == 1
    assert summary["missing_ids"] == [12]
    assert summary["unexpected_ids"] == []
    assert summary["instances"] == {"app-1": 2, "app-2": 1}
    assert verifier.has_expected_instances(summary["instances"], 2) is True
    assert verifier.has_expected_instances(summary["instances"], 3) is False


def test_test_database_guard_rejects_runtime_database() -> None:
    preparer = _load_script("prepare_http_load_test.py")

    try:
        preparer.require_test_database_url("mysql+pymysql://app:secret@localhost/scheduler")
    except ValueError as exc:
        assert "_test" in str(exc)
    else:
        raise AssertionError("runtime database URL should be rejected")


def test_load_test_scripts_accept_a_distributed_environment_file() -> None:
    preparer = _load_script("prepare_http_load_test.py")
    verifier = _load_script("verify_http_load_test.py")

    assert preparer.build_parser().parse_args(
        ["--env-file", ".env.distributed"]
    ).env_file == Path(".env.distributed")
    assert verifier.build_parser().parse_args(
        ["--env-file", ".env.distributed"]
    ).env_file == Path(".env.distributed")
    assert verifier.build_parser().parse_args([]).expected_instances == 3
