# 多实例分布式压测

## 架构

```text
JMeter
  -> Nginx / 本地轮询代理 :8080
      -> FastAPI app-1
      -> FastAPI app-2
      -> FastAPI app-3
          -> 共享 MySQL
```

每个 FastAPI 响应都包含 `X-App-Instance` 和 `X-Request-ID`。JMeter 将响应状态、任务 ID、实例名和请求 ID 写入 CSV；校验脚本再查询 MySQL，避免只根据 HTTP 200 判断成功。

## Docker 启动

前置条件：Docker Desktop、Java 17、JMeter 5.6.3。

```powershell
Copy-Item .env.distributed.example .env.distributed
```

编辑 `.env.distributed`，设置 MySQL 密码。容器应用和宿主机压测脚本共同使用 `task_scheduler_distributed_test`：容器内 `DATABASE_URL` 使用主机名 `mysql:3306`，宿主机 `LOAD_TEST_DATABASE_URL` 使用 `127.0.0.1:3307`。`TEST_DATABASE_URL` 指向单独的 `task_scheduler_test`。

```powershell
docker compose --env-file .env.distributed -f docker-compose.distributed.yml up --build -d
docker compose --env-file .env.distributed -f docker-compose.distributed.yml ps
Invoke-WebRequest http://127.0.0.1:8080/healthz
```

迁移服务会同时迁移 `task_scheduler_distributed_test` 和 `task_scheduler_test`。查看 Nginx 和应用日志：

```powershell
docker compose --env-file .env.distributed -f docker-compose.distributed.yml logs -f nginx app-1 app-2 app-3
```

## 无 Docker 启动

本机已有 MySQL 时，在一个终端运行：

```powershell
.venv/Scripts/python.exe scripts/run_local_distributed.py
```

它会连接 `.env` 中的 `TEST_DATABASE_URL`，启动 `app-1/app-2/app-3` 和 `http://127.0.0.1:8080`。按 `Ctrl+C` 统一停止。

## JMeter 测试

先准备独立批次。Docker 环境追加 `--env-file .env.distributed`，本地环境省略：

```powershell
.venv/Scripts/python.exe scripts/prepare_http_load_test.py --claim-tasks 100
```

运行 20 个线程、每线程认领 5 次，共 100 次请求：

```powershell
jmeter.bat -n -t tests/jmeter/claim-concurrency.jmx -q load-test-results/jmeter.properties "-Jhost=127.0.0.1" "-Jport=8080" "-Jthreads=20" "-Jloops=5" -l load-test-results/claim.jtl
```

运行 20 个线程，同时完成同一个步骤：

```powershell
jmeter.bat -n -t tests/jmeter/completion-idempotency.jmx -q load-test-results/jmeter.properties "-Jhost=127.0.0.1" "-Jport=8080" "-Jthreads=20" -l load-test-results/completion.jtl
```

校验客户端结果和数据库：

```powershell
.venv/Scripts/python.exe scripts/verify_http_load_test.py
```

输出必须满足：认领请求无错误、任务 ID 无重复无遗漏、数据库全部为 `claimed`；完成请求全部成功、实例分布包含多个应用、`step_execution_logs` 只有一条日志、任务只推进一次并变为 `done`。

校验器默认要求认领和完成结果都至少观察到 3 个实例。只调试单实例链路时可追加 `--expected-instances 1`，正式答辩不要降低该值。

需要删除本批数据时：

```powershell
.venv/Scripts/python.exe scripts/verify_http_load_test.py --cleanup
```

## HTML 报告

```powershell
jmeter.bat -g load-test-results/claim.jtl -o load-test-results/claim-report
jmeter.bat -g load-test-results/completion.jtl -o load-test-results/completion-report
```

浏览器打开两个报告目录中的 `index.html`。

## 跨真实服务器

把 Nginx、三个 FastAPI 实例、MySQL 和 JMeter 压测机部署到不同主机。三个应用设置不同 `APP_INSTANCE`，但使用同一个 MySQL 地址；Nginx 上游改为三台应用服务器的内网地址；JMeter 在独立压测机上把 `-Jhost` 指向 Nginx 地址。安全组只开放 JMeter 到 Nginx、Nginx 到应用、应用到 MySQL 的必要端口。
