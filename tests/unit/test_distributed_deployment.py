from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_compose_defines_mysql_migration_three_apps_and_nginx() -> None:
    compose = (ROOT / "docker-compose.distributed.yml").read_text(encoding="utf-8")

    for service in ("mysql", "migrate", "app-1", "app-2", "app-3", "nginx"):
        assert f"  {service}:" in compose
    assert "alembic upgrade head" in compose
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
    assert "USER app" in dockerfile
    assert 'CMD ["uvicorn", "app.main:app"' in dockerfile
