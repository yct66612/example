from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).parents[2]


def test_compose_defines_mysql_migration_three_apps_and_nginx() -> None:
    compose = (ROOT / "docker-compose.distributed.yml").read_text(encoding="utf-8")

    for service in ("mysql", "migrate", "app-1", "app-2", "app-3", "nginx"):
        assert f"  {service}:" in compose
    assert "python scripts/migrate_databases.py" in compose
    assert "condition: service_healthy" in compose
    assert "condition: service_completed_successfully" in compose
    assert "APP_INSTANCE: app-1" in compose
    assert "APP_INSTANCE: app-2" in compose
    assert "APP_INSTANCE: app-3" in compose
    assert '"8080:80"' in compose


def test_nginx_round_robins_across_all_application_instances() -> None:
    nginx = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")

    assert "server app-1:8000" in nginx
    assert "server app-2:8000" in nginx
    assert "server app-3:8000" in nginx
    assert "proxy_pass http://scheduler_api" in nginx
    assert "proxy_set_header X-Request-ID $request_id" in nginx
    assert "$upstream_addr" in nginx


def test_container_image_runs_as_non_root_user() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.11-slim" in dockerfile
    assert "COPY scripts ./scripts" in dockerfile
    assert "USER app" in dockerfile
    assert 'CMD ["uvicorn", "app.main:app"' in dockerfile


def test_container_application_and_host_load_tools_share_a_dedicated_test_database() -> None:
    environment = (ROOT / ".env.distributed.example").read_text(encoding="utf-8")

    assert "MYSQL_DATABASE=task_scheduler_distributed_test" in environment
    assert "@mysql:3306/task_scheduler_distributed_test" in environment
    assert "@127.0.0.1:3307/task_scheduler_distributed_test" in environment
    assert "TEST_DATABASE_URL=" in environment


def test_claim_jmeter_plan_records_task_and_instance_results() -> None:
    path = ROOT / "tests" / "jmeter" / "claim-concurrency.jmx"
    ElementTree.parse(path)
    plan = path.read_text(encoding="utf-8")

    assert "/api/tasks/claim" in plan
    assert "task_name_prefix" in plan
    assert "claimPrefix" in plan
    assert "claimResultsFile" in plan
    assert "X-App-Instance" in plan


def test_completion_jmeter_plan_synchronizes_duplicate_requests() -> None:
    path = ROOT / "tests" / "jmeter" / "completion-idempotency.jmx"
    ElementTree.parse(path)
    plan = path.read_text(encoding="utf-8")

    assert "SyncTimer" in plan
    assert "/steps/0/complete" in plan
    assert "taskId" in plan
    assert "workerId" in plan
    assert "completionResultsFile" in plan
    assert "X-App-Instance" in plan
