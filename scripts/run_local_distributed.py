"""Run three local FastAPI instances behind the development round-robin proxy."""

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple
from urllib.request import urlopen

from sqlalchemy.engine import make_url

from app.config import Settings, get_settings


class ProcessSpec(NamedTuple):
    name: str
    module: str
    port: int
    environment: dict[str, str]


def build_process_specs(
    database_url: str,
    app_base_port: int = 8101,
    proxy_port: int = 8080,
) -> list[ProcessSpec]:
    app_specs = [
        ProcessSpec(
            name=f"app-{index + 1}",
            module="app.main:app",
            port=app_base_port + index,
            environment={
                "APP_INSTANCE": f"app-{index + 1}",
                "DATABASE_URL": database_url,
                "TEST_DATABASE_URL": database_url,
            },
        )
        for index in range(3)
    ]
    upstreams = ",".join(
        f"http://127.0.0.1:{spec.port}" for spec in app_specs
    )
    return [
        *app_specs,
        ProcessSpec(
            name="load-balancer",
            module="scripts.local_round_robin_proxy:app",
            port=proxy_port,
            environment={
                "UPSTREAMS": upstreams,
                "DATABASE_URL": database_url,
                "TEST_DATABASE_URL": database_url,
            },
        ),
    ]


def configured_database_url(env_file: Path | None) -> str:
    settings = Settings(_env_file=env_file) if env_file is not None else get_settings()
    database_url = settings.load_test_database_url or settings.test_database_url
    database_name = make_url(database_url).database or ""
    if not database_name.endswith("_test"):
        raise ValueError("local distributed launcher requires a _test database")
    return database_url


def ensure_ports_available(specs: list[ProcessSpec]) -> None:
    for spec in specs:
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", spec.port))
            except OSError as exc:
                raise RuntimeError(f"端口 {spec.port} 已被占用：{spec.name}") from exc


def wait_for_health(spec: ProcessSpec, timeout_seconds: float = 20) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{spec.port}/healthz", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"{spec.name} 健康检查超时")


def stop_processes(processes: list[subprocess.Popen]) -> None:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
    for process in reversed(processes):
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="启动本地三实例分布式压测环境")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--app-base-port", type=int, default=8101)
    parser.add_argument("--proxy-port", type=int, default=8080)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        database_url = configured_database_url(args.env_file)
        specs = build_process_specs(database_url, args.app_base_port, args.proxy_port)
        ensure_ports_available(specs)
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc

    processes: list[subprocess.Popen] = []
    try:
        for spec in specs:
            environment = os.environ.copy()
            environment.update(spec.environment)
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    spec.module,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(spec.port),
                    "--log-level",
                    "info",
                ],
                env=environment,
            )
            processes.append(process)
            wait_for_health(spec)
            print(f"{spec.name}: http://127.0.0.1:{spec.port} pid={process.pid}")

        print(f"负载均衡入口：http://127.0.0.1:{args.proxy_port}")
        print("按 Ctrl+C 停止全部实例")
        while True:
            for spec, process in zip(specs, processes, strict=True):
                return_code = process.poll()
                if return_code is not None:
                    raise RuntimeError(f"{spec.name} 异常退出，返回码 {return_code}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("正在停止本地多实例环境")
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    main()
