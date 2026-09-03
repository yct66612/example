# 多实例分布式压测设计

## 目标

为现有任务调度系统增加一套可重复运行的完整请求链路：JMeter 通过 Nginx 访问三个 FastAPI 实例，所有实例共享同一个 MySQL。答辩时既能展示请求确实分发到不同实例，也能用客户端结果和数据库状态证明任务唯一认领与步骤完成幂等。

## 架构

容器编排包含 MySQL、一次性 Alembic 迁移服务、三个 FastAPI 服务和一个 Nginx。FastAPI 保持无状态，任务状态、认领信息和执行日志继续只存放在 MySQL。Nginx 使用轮询上游并记录 `$upstream_addr`，FastAPI 在响应中返回 `X-App-Instance` 与 `X-Request-ID`。

本机没有 Docker 和 Nginx，因此本次会完成并静态验证容器配置，同时使用已安装的 JMeter 5.6.3 对本地 FastAPI/MySQL 实际执行测试计划。安装 Docker 后可直接切换到 Nginx 的 `8080` 入口运行相同 JMX。

## 压测场景

唯一认领场景先在独立测试数据库中创建一批单步骤任务，再由多个 JMeter 线程调用认领接口。客户端结果文件记录每次返回的任务 ID 和处理实例；校验脚本要求返回数量等于任务数量、任务 ID 无重复无遗漏，并检查数据库中整批任务均为 `claimed`。

幂等完成场景先创建、认领并启动一个单步骤任务。JMeter 使用 Synchronizing Timer 让多个线程同时向同一个任务、同一个步骤发送相同完成请求。校验脚本要求所有请求成功、至少观察到一个应用实例、数据库只有一条 `(task_id, step_index)` 日志、步骤只推进一次且任务为 `done`。

## 数据与清理

准备脚本只操作名称带随机压测前缀的数据，并把任务 ID、worker ID、批次前缀写入 JSON 上下文。默认校验后保留数据以便答辩查询；显式传入清理选项才删除本批数据。所有压测命令使用 `task_scheduler_test`，避免影响网页演示库。

## 验证边界

Docker Compose 方案验证负载均衡、多应用实例和共享数据库的完整链路。本机实际运行因为缺少 Docker/Nginx，只能证明 JMX、HTTP 并发和 MySQL 并发逻辑可执行；真正跨物理服务器还需要把 Nginx、FastAPI、MySQL 和 JMeter 注入机部署到可互通的不同主机。
