import importlib.util
from pathlib import Path


def _load_proxy_module():
    path = Path(__file__).parents[2] / "scripts" / "local_round_robin_proxy.py"
    spec = importlib.util.spec_from_file_location("local_round_robin_proxy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_launcher_module():
    path = Path(__file__).parents[2] / "scripts" / "run_local_distributed.py"
    spec = importlib.util.spec_from_file_location("run_local_distributed", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_round_robin_pool_cycles_through_all_upstreams() -> None:
    module = _load_proxy_module()
    pool = module.RoundRobinPool(["http://app-1", "http://app-2", "http://app-3"])

    assert [pool.next() for _ in range(4)] == [
        "http://app-1",
        "http://app-2",
        "http://app-3",
        "http://app-1",
    ]


def test_local_launcher_builds_three_apps_and_one_proxy() -> None:
    module = _load_launcher_module()

    specs = module.build_process_specs("mysql://test", app_base_port=8101, proxy_port=8080)

    assert [spec.name for spec in specs] == ["app-1", "app-2", "app-3", "load-balancer"]
    assert [spec.port for spec in specs] == [8101, 8102, 8103, 8080]
    assert [spec.environment.get("APP_INSTANCE") for spec in specs[:3]] == [
        "app-1",
        "app-2",
        "app-3",
    ]
    assert specs[3].environment["UPSTREAMS"] == (
        "http://127.0.0.1:8101,http://127.0.0.1:8102,http://127.0.0.1:8103"
    )
