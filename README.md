# TonamiIbuki企业 IT 运维智能体系统

面向企业 IT 运维场景的智能体原型系统，包含 RAG 知识库、告警分析、多智能体诊断、工单处理、HITL 审批、安全审计与 Streamlit 控制台。

## 核心亮点

- **混合检索 RAG**：BM25 + Dense Embedding 向量检索 + RRF 融合 + Reranker 重排序，支持文档批量导入、自动分块和 RAG Top-K 命中率评测。
- **Embedding 服务**：多 Provider 向量化（mock / OpenAI-compatible / Ollama），自动维度探测与 L2 归一化。
- **Reranker 服务**：候选重排序（mock / cross-encoder 预留），提升检索精度。
- **ChromaDB 持久化向量存储**：全量 Embedding 向量持久化到 ChromaDB，支持语义检索与增量增删。
- **五角色协作诊断**：Monitor -> Diagnosis -> Code -> Execution -> Supervisor -> Report，基于 **LangGraph StateGraph** 实现状态机编排与条件路由。
- **PhaseManager 阶段追踪**：ANALYSIS → PLANNING → EXECUTION → VERIFICATION → COMPLETION 五阶段生命周期管理。
- **HITL 安全审批**：高风险操作进入等待审批状态，由管理员放行或拒绝。
- **证据链审计**：诊断、工具调用、审批、案例状态均可追踪，支持证据链拓扑与报告导出。
- **演示驾驶舱**：展示监控指标、业务拓扑、诊断会话、待审批队列与案例沉淀。
- **双模式工具层**：默认 simulate，保留真实 Ansible/K8s/SSH 适配入口。
- **工具沙箱与回滚提示**：每次工具执行生成沙箱记录，并在报告中给出回滚建议。
- **系统自检**：聚合 RAG 文档、Embedding/Reranker 状态、ChromaDB、LangGraph 节点、案例、审计、工具模式和审批状态，方便演示验收。
- **SQLite 持久化**：诊断会话、案例和审批记录持久化到 SQLite，服务重启后可恢复会话状态。
- **LLM 多 Provider 适配**：支持 mock、OpenAI-compatible、DeepSeek、Ollama、硅基流动与 Bedrock 预留入口，带响应缓存与降级。 
- **Prompt 模板系统**：内置 alert、diagnosis、code、ticket、rag、supervisor 模板，便于后续接入真实 Agent。
- **综合知识库**：9 篇种子文档覆盖数据库、K8s、磁盘、Redis、运维手册、故障排查 SOP、配置模板、安全策略、错误码对照表。

## 快速开始

端口约定：后端 API 默认运行在 `8000`，Web 前端默认运行在 `8080`。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

启动 Web 控制台：

```bash
streamlit run ui/app.py --server.address 0.0.0.0 --server.port 8080
```

运行测试：

```bash
pytest
```

## 主要接口

- `POST /api/alert/analyze`：告警分析
- `POST /api/ticket/process`：工单处理
- `GET /api/monitor/metrics`：模拟监控指标快照
- `GET /api/topology`：演示业务拓扑
- `GET /api/system/self-check`：系统自检汇总
- `GET /api/tools`：工具目录与风险等级
- `GET /api/tools/policy`：工具执行策略
- `GET /api/prompts`：Prompt 模板列表
- `GET /api/prompts/{name}`：Prompt 模板内容
- `POST /api/llm/chat`：LLM 多 Provider 调用入口
- `POST /api/rag/query`：知识库问答
- `POST /api/rag/import`：导入运维手册并重建索引
- `POST /api/rag/bulk-import`：批量导入文档并自动分块
- `POST /api/rag/evaluate`：运行 RAG Top-K 命中率评测
- `POST /api/rag/reload`：重载知识库索引
- `GET /api/rag/vector-index`：持久化向量索引适配器状态
- `GET /api/rag/embedding-status`：Embedding 服务状态（provider / model / dim）
- `GET /api/rag/reranker-status`：Reranker 服务状态
- `POST /api/diagnosis/run`：启动诊断并以 SSE 返回阶段事件
- `POST /api/diagnosis/run-sync`：启动诊断并同步返回会话，便于 Web 演示
- `GET /api/diagnosis/sessions`：诊断会话列表
- `GET /api/diagnosis/{session_id}/status`：查询诊断状态
- `GET /api/diagnosis/{session_id}/evidence`：查询证据链拓扑
- `GET /api/diagnosis/{session_id}/approvals`：查询审批记录
- `GET /api/diagnosis/{session_id}/report`：导出 Markdown 诊断报告
- `POST /api/diagnosis/{session_id}/case`：将诊断报告沉淀为案例
- `POST /api/diagnosis/{session_id}/approve`：HITL 审批
- `GET /api/cases`：案例列表
- `POST /api/cases`：新增案例沉淀
- `GET /api/audit/logs`：审计日志，支持 actor/action/target 筛选

## 安全配置

## 部署工程化

项目已提供：

- `Dockerfile`
- `docker-compose.yml`
- `Makefile`
- `deploy/tonamiibuki-api.service`
- `deploy/tonamiibuki-web.service`

Docker 启动：

```bash
docker compose up -d --build
```

Makefile：

```bash
make test
make api
make web
```

## 安全配置

- `API_TOKEN` 为空时不启用鉴权，便于本地演示。
- 设置 `API_TOKEN` 后，所有 `/api/*` 请求需携带 `X-API-Token` 请求头。
- 系统会自动写入 HTTP 请求审计、安全拒绝审计和工具执行审计。
