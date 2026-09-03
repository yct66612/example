import importlib.util
from pathlib import Path


def _load_build_parser(script_name: str):
    script_path = Path(__file__).parents[2] / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_parser


def test_evidence_scripts_support_explicit_keep_data_mode() -> None:
    build_claim_parser = _load_build_parser("run_claim_evidence.py")
    build_completion_parser = _load_build_parser("run_completion_evidence.py")
    build_distributed_parser = _load_build_parser("run_distributed_completion_evidence.py")

    assert build_claim_parser().parse_args([]).keep_data is False
    assert build_claim_parser().parse_args(["--keep-data"]).keep_data is True

    assert build_completion_parser().parse_args([]).keep_data is False
    assert build_completion_parser().parse_args(["--keep-data"]).keep_data is True

    assert build_distributed_parser().parse_args([]).keep_data is False
    assert build_distributed_parser().parse_args(["--keep-data"]).keep_data is True
