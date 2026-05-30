# LATAM Analytics Platform — Demo

> **Para instalar e apresentar:** leia o [GUIA_DEMO.md](./GUIA_DEMO.md) — setup, scripts `.\scripts\start-demo.ps1`, checklist e riscos corporativos.

Plataforma corporativa de Analytics com dois ambientes:

- **Builder Studio** — para analistas e desenvolvedores: cadastrar conexões, fazer upload de dados, gerar bases sintéticas, explorar datasets, criar métricas, montar dashboards drag-and-drop e gerir o ciclo de publicação.
- **Business Portal** — para usuários finais (Finance, Operations, Supplier, Sales, LATAM Executive): consumir dashboards publicados, filtrados por RBAC.

Demo 100% local, modular e preparado para evoluir para uma stack corporativa (PostgreSQL, Auth real, MLflow, etc.).

---

## Stack

| Camada            | Tecnologias                                                                          |
| ----------------- | ------------------------------------------------------------------------------------ |
| **Backend**       | Python 3.11+, FastAPI, SQLAlchemy, Pydantic v2, Pandas, NumPy, PyArrow, DuckDB, Openpyxl, Uvicorn |
| **Frontend**      | React 18, TypeScript, Vite, Tailwind CSS, React Router, Zustand, Axios, TanStack Table, Plotly.js, React Grid Layout, react-dropzone |
| **Metadata DB**   | SQLite (demo) — código compatível com PostgreSQL                                     |
| **Storage**       | Arquivos locais em `backend/storage/{uploads,sample_data,processed}` (Parquet)       |
| **Auth**          | Tokens simulados (sem senha) — substituir por OIDC/SAML em produção                  |

---

## Estrutura do monorepo

```
latam-analytics-platform/
├── backend/                # FastAPI + SQLAlchemy + Pandas
│   ├── app/
│   │   ├── models/         # Tabelas SQLAlchemy
│   │   ├── schemas/        # Pydantic in/out
│   │   ├── services/       # Domínio: permission, dataset, metric_engine, dashboard_engine
│   │   ├── routers/        # Endpoints REST
│   │   └── utils/          # Profiling, synthetic data, file utils
│   ├── config.py
│   ├── database.py
│   ├── main.py             # Entry FastAPI
│   ├── seed.py             # Workspaces + usuários demo
│   ├── seed_dashboards.py  # Métricas + dashboards exemplo
│   └── requirements.txt
├── frontend/               # React + Vite
│   └── src/
│       ├── api/            # Axios client (AuthAPI, DatasetsAPI, MetricsAPI, DashboardsAPI…)
│       ├── components/
│       │   ├── layout/     # AppLayout, Sidebar, Header
│       │   ├── ui/         # Button, Card, Modal, Badge, DataTable, EmptyState
│       │   └── widgets/    # WidgetRenderer, WidgetConfigPanel, DashboardViewer
│       ├── pages/
│       │   ├── builder/    # Data Sources, Upload, Dataset Explorer, Metric Builder, Dashboard Builder, Publish Center
│       │   └── business/   # BusinessAreaView (renderiza 5 rotas)
│       ├── store/          # Zustand authStore
│       └── types/          # Tipos centralizados
├── docker-compose.yml      # Esqueleto para Postgres + backend + frontend
└── README.md
```

---

## Fases entregues

### Fase 1 — Fundação ✓

- Monorepo backend + frontend.
- Login simulado, sidebar dinâmica por perfil, layout corporativo.
- 8 usuários mock cobrindo todos os perfis RBAC.
- 7 workspaces (LATAM + países).
- Backend FastAPI rodando com SQLite + seed.

### Fase 2 — Data Management ✓

- Cadastro de **Data Sources** (PostgreSQL/SQL Server/MySQL/SQLite/DuckDB) com teste de conexão.
- Upload de **CSV/XLSX** com profiling automático (dtype, nulls, distincts, stats).
- Geração de **datasets sintéticos** (`sales_latam`, `finance_actual_budget`, `supplier_performance`, `cash_flow`, `commission_forecast`).
- **Dataset Explorer** com preview, perfil de colunas e mudança de status (Draft → Validated → Certified → Deprecated).
- Persistência em Parquet em `backend/storage/processed/`.

### Fase 3a — Analytics core ✓

- **Camada semântica** (`Metric`): SUM/AVG/COUNT/MIN/MAX, RATIO, VARIATION_ABS/PCT, MTD, YTD, YOY e DSL CUSTOM_LIMITED (SUM/SUB/ADD/MULT/DIVIDE/COUNT/AVG/MIN/MAX) sem `eval` aberto.
- **Metric Builder**: lista, criação, edição com formulário dinâmico por tipo, pré-visualização do valor calculado, certificação.
- **Dashboard Builder**: react-grid-layout drag-and-drop (12 colunas), paleta com 8 widgets (KPI, Bar, Line, Area, Pie, Donut, Table, Text), edição inline com preview ao vivo, persistência de layout.
- **8 tipos de widget** renderizados via Plotly.js (charts) ou componentes nativos (KPI/Table/Text).
- **Publish flow** completo: Draft → Pending Approval → Published → Archived, com RBAC por área (`publish_finance`, `publish_operations`, `publish_any`).
- **Publish Center**: fila de aprovação dividida em 3 abas (Pendentes/Rascunhos/Publicados) com ações por papel.
- **Business Portal**: 5 áreas (Operations, Finance, Supplier, Sales, LATAM Executive) consumindo dashboards publicados via `DashboardViewer` (read-only).
- **6 dashboards exemplo** com 39 widgets totais + 15 métricas certificadas via `seed_dashboards.py`.

### Fase 3b — Pipeline Studio (ETL Builder) ✓

- **Models**: `Pipeline`, `PipelineStep` (linear ordenado), `PipelineRun` (histórico).
- **10 operadores** no `pipeline_engine.py` (Pandas):
  - `SOURCE` (lê dataset) • `FILTER` (AND com 11 ops) • `SELECT` (colunas + rename) •
  - `COMPUTED_COLUMN` (expressão via `pandas.eval` — sem `eval` Python aberto) •
  - `GROUP_BY` (sum/avg/min/max/count/nunique + alias) • `JOIN` (left/inner/right/outer) •
  - `UNION` (concat) • `SORT` • `LIMIT` • `TARGET` (grava como `Dataset` source=ETL Output).
- **Preview por step**: o editor mostra um sample do DataFrame até o step selecionado (zero persistência).
- **Run on-demand** com `PipelineRun` registrado (status, duração, rows in/out, logs por step, target_dataset_id).
- **RBAC**: `view_pipelines`, `create_pipeline`, `run_pipeline`, `publish_pipeline` (+ `publish_any`).
- **Pipeline Studio UI** (3 colunas):
  - Paleta de 10 operadores (cards coloridos por tipo)
  - Canvas vertical com cards sequenciais, mover ↑↓, remover
  - Config dinâmico por tipo de step + preview do DataFrame até aquele step + modal de histórico
- **3 pipelines exemplo** via `seed_pipelines.py`:
  1. **Sales Brazil — High-margin Top Clients** (8 steps): SOURCE → FILTER country=BR → COMPUTED margin_pct → FILTER >0.3 → GROUP_BY client → SORT desc → LIMIT 50 → TARGET
  2. **Finance — Variance Actual vs Budget** (6 steps): SOURCE → COMPUTED var_abs/var_pct → GROUP_BY country/account_group → SORT → TARGET
  3. **Supplier — Risk Watchlist** (7 steps): SOURCE → FILTER risk_level in [High,Medium] → COMPUTED savings_rate → SELECT subset → SORT sla_score → LIMIT 100 → TARGET
- **Ciclo fechado**: o dataset gerado pelo TARGET aparece automaticamente no Dataset Explorer / Metric Builder / Dashboard Builder.

### Fase 4 — Forecasting Studio ✓

- **Models**: `Forecast` (config + status workflow) + `ForecastRun` (histórico com MAE/RMSE/MAPE).
- **3 algoritmos** no `forecast_engine.py` (Pandas + scikit-learn + statsmodels):
  - `NAIVE_SEASONAL` — baseline: média dos últimos N ciclos do mesmo slot sazonal (params: `season`, `lookback_cycles`).
  - `LINEAR_TREND` — `sklearn.LinearRegression` com features de trend + dummies sazonais.
  - `HOLT_WINTERS` — `statsmodels.ExponentialSmoothing` triple (trend + sazonalidade, com fallback automático se não houver ciclos suficientes).
- **Forecast agrupado** (`group_by=["country", ...]`) — gera 1 série + 1 conjunto de métricas por grupo. Ex: receita prevista por país.
- **Backtest com holdout**: separa últimos N períodos para validação. Calcula MAE/RMSE/MAPE por grupo.
- **Intervalo de confiança 95%** baseado no desvio dos resíduos do treino.
- **Publish → Dataset**: o output (`ds, y, yhat, yhat_lower, yhat_upper, is_forecast, group_key`) vira um `Dataset` (source=`Forecast`) consumível por Metric/Dashboard Builder.
- **RBAC**: `view_forecasts`, `create_forecast`, `run_forecast`, `publish_forecast` (+ `publish_any`).
- **Forecasting Studio UI** (3 colunas):
  - Esquerda: configuração (dataset, target, date, frequency, group_by, algoritmo, params JSON, filtros)
  - Centro: gráfico Plotly com histórico (linha sólida) + backtest (tracejada) + forecast futuro (linha cheia) + banda de IC 95%, linha vertical marcando o início do horizonte
  - Direita: tabela de métricas com coloração por qualidade (verde `<15%`, âmbar `<30%`, vermelho `>30%` MAPE), audit info, histórico de runs em modal
- **3 forecasts exemplo** via `seed_forecasts.py`:
  1. **LATAM Revenue Forecast (Holt-Winters)** — receita LATAM agregada, horizon 6m, holdout 6m (MAPE ~13%)
  2. **Revenue Forecast by Country (Linear Trend)** — receita por país (6 grupos), horizon 6m
  3. **Finance Actual Forecast Baseline (Naive Seasonal)** — realizado financeiro por país, horizon 12m
- **Ciclo fechado**: o dataset gerado pelo publish aparece automaticamente no Dataset Explorer / Metric Builder / Dashboard Builder.

### Fase 5 — Alerts & Notifications ✓

- **Models**: `Alert` (regra configurada) + `Notification` (instância disparada por recipient).
- **5 tipos de alerta** no `alert_engine.py`:
  - `metric_threshold` — métrica `<`, `>`, `<=`, `>=`, `==`, `!=` valor (com filtro de período: MTD, YTD, last_30d, etc.)
  - `metric_change` — variação % entre período atual vs anterior (direction: drop / raise / any)
  - `forecast_quality` — MAPE do último run de um forecast acima de threshold (scope: any / all / average)
  - `pipeline_failure` — último run de um pipeline com status `Failed` (com lookback em minutos)
  - `dashboard_stale` — dashboard publicado sem atualização há N dias
- **Severidades**: `info` · `warning` · `critical` (badges coloridos no frontend).
- **Canais**: in-app (sempre) + e-mail mock (log em `storage/notifications/emails.jsonl`).
- **Cooldown**: evita re-disparo repetido (default 60 min, configurável por alerta).
- **Disparo**:
  - Manual: **Evaluate** (1 alerta) ou **Evaluate All** (batch)
  - Teste seco: **Test** (ignora cooldown, não cria notification)
  - Automático: após run de pipeline ou train/publish de forecast (`alert_triggers.py`)
- **RBAC**: `view_alerts`, `create_alert`, `manage_alerts` (+ todos os viewers recebem `view_alerts` para ver inbox).
- **Alerts UI** (`/builder/alerts`):
  - Cards com tipo, severidade, target, enabled toggle, fire_count, última avaliação
  - Modal **AlertBuilder** com UI dinâmica por tipo de regra
  - Botões: Evaluate, Test, Toggle, Delete
- **Notifications UI**:
  - **NotificationBell** no header (badge unread + dropdown com últimas 5, polling 30s)
  - **NotificationCenter** (`/notifications`) — inbox com filtros (status, severidade, tipo), ack com nota, read-all
- **6 alertas exemplo** via `seed_alerts.py`:
  1. Revenue YTD abaixo de 5M USD (metric_threshold, warning)
  2. Margin % abaixo de 25% (metric_threshold, critical)
  3. Revenue MTD caiu >10% vs mês anterior (metric_change, warning)
  4. Forecast por país com MAPE > 25% (forecast_quality, warning)
  5. Pipeline Sales Brazil falhou (pipeline_failure, critical)
  6. Dashboard Sales LATAM sem atualização >7d (dashboard_stale, info)

### Fase 6 — Scheduler ✓ (esta entrega)

- **Models**: `ScheduledJob` (cron + target) + `ScheduledJobRun` (histórico de execuções).
- **APScheduler** (`BackgroundScheduler`) integrado ao lifecycle do FastAPI (startup/shutdown).
- **3 tipos de job**:
  - `pipeline_run` — executa pipeline completo (persiste TARGET, dispara alertas)
  - `forecast_train` — treina forecast (registra ForecastRun, dispara alertas)
  - `alerts_evaluate` — avalia todos os alertas enabled de um workspace
- **Cron 5 campos** (min hour dom month dow, UTC): ex. `0 6 * * *` = diário 06:00.
- **Próxima execução** calculada e exibida na UI (`next_run_at`).
- **Controles**: enabled, pause/resume, run-now manual, histórico de runs.
- **RBAC**: capability `schedule_job` (Platform Admin, Data Developer).
- **Scheduler UI** (`/builder/scheduler`):
  - Status APScheduler (running / active jobs)
  - Cards com cron, target, próxima/última execução, run_count
  - Modal criar job (presets de cron, select pipeline/forecast)
  - Run now, Pause/Resume, Histórico
- **5 jobs seed** via `seed_scheduled_jobs.py`:
  - 3 pipeline_run (sync dos pipelines com `schedule_cron`)
  - 1 forecast_train (Holt-Winters LATAM, 05:00 UTC)
  - 1 alerts_evaluate (LATAM, 06:30 UTC)

### Fase 7 — Ad-Hoc Report Builder ✓ (esta entrega)

- **Engine DuckDB** (`ad_hoc_engine.py`): SQL read-only sobre parquet do dataset (view `data`).
- **Segurança**: apenas `SELECT`/`WITH`; bloqueio de DDL/DML; `LIMIT` forçado no preview (até 5000).
- **Ações**:
  - Preview tabular (até 200 linhas na UI)
  - Export CSV (até 10k linhas, capability `create_report`)
  - Salvar query (`SavedReport`) para reutilizar
  - Salvar resultado como novo `Dataset` (source=`Report Output`)
- **RBAC**: `view_datasets` (preview/listar) + `create_report` (export/salvar).
- **UI** (`/builder/ad-hoc-report`):
  - Seletor de dataset + colunas clicáveis
  - Editor SQL + templates de exemplo
  - Queries salvas (seed + criadas pelo usuário)
  - Tabela de preview
- **2 queries seed** via `seed_reports.py` sobre `sales_latam`.
- **Dimensões para join** (`client_master`, `product_catalog`) via `seed_report_tables.py` — aliases `clients` / `products`.
- **Dois modos na UI**: Visual Builder (colunas, filtros, agrupar) + SQL Editor (joins cross-table).

### Fase 8 — Admin Panel ✓ (esta entrega)

- **Users** (`/admin/users`): lista 8 usuários seed, criar/editar role, workspace, ativo/inativo.
- **Workspaces** (`/admin/workspaces`): editar descrição e scope (regional/country).
- **Permissions** (`/admin/permissions`): matriz read-only roles × capabilities + workspace/business area access.
- **Audit Logs** (`/admin/audit-logs`): trilha filtrável (email, action, workspace).
- **System Jobs** (`/admin/system-status`): saúde da plataforma, contadores de entidades, APScheduler, link ao Scheduler.
- **RBAC**: `manage_users`, `manage_workspaces`, `manage_permissions`, `view_audit_logs`, `view_admin`.
- **Seed audit logs** via `seed_audit_logs.py` (12 eventos demo se &lt; 10 registros).

### Fase 9 — Features extras ✓ (esta entrega)

- **Data Lineage** (`Dataset Explorer → aba Lineage`): grafo upstream/downstream de datasets derivados de pipelines, forecasts e reports.
- **Data Quality** (`Dataset Explorer → aba Quality`): checks automáticos (not_null, positive, row_count, distinct) com score e histórico.
- **PDF Export** (`Dashboard Builder` e `Business Portal`): botão **Exportar PDF** renderiza widgets em PDF via `fpdf2`.
- **Slack / Teams** (Alert Builder): canais mock adicionais — entregas gravadas em `backend/data/notifications/slack.jsonl` e `teams.jsonl`.
- **Model Registry** (`/builder/model-registry`): catálogo de modelos ML/forecast com registro, promoção Staging → Production.
- **RBAC**: `view_lineage`, `run_quality_checks`, `export_dashboard`, `view_model_registry`, `register_model`.
- **Seed Phase 9** via `seed_phase9.py` (rebuild lineage, quality em `sales_latam`, modelos a partir de forecasts).

### Roadmap concluído

Todas as fases planejadas (1–9) estão implementadas na demo.

---

## Como rodar localmente

### Pré-requisitos

- Python 3.11+
- Node.js 18+
- Windows / macOS / Linux

### Backend

```powershell
cd backend

# Cria virtualenv
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # macOS/Linux

# Dependências
pip install -r requirements.txt

# Inicializa DB e cria usuários, workspaces, datasets, métricas, dashboards e pipelines
python seed.py
python seed_dashboards.py
python seed_pipelines.py
python seed_forecasts.py
python seed_alerts.py
python seed_scheduled_jobs.py
python seed_report_tables.py
python seed_reports.py
python seed_audit_logs.py
python seed_phase9.py

# Sobe o backend
python -m uvicorn main:app --host 127.0.0.1 --port 8001
# → http://127.0.0.1:8001
# Docs interativas: http://127.0.0.1:8001/docs
```

> **Nota Windows**: se a porta 8000 ficar travada em "phantom socket" (problema conhecido do stack TCP do Windows), use a porta 8001 como acima e configure o frontend com `VITE_API_TARGET=http://127.0.0.1:8001`.

### Frontend

```powershell
cd frontend
npm install

# Vite vai proxar /api -> http://127.0.0.1:8001 via VITE_API_TARGET
$env:VITE_API_TARGET = "http://127.0.0.1:8001"
npm run dev
# → http://127.0.0.1:5173
```

---

## Usuários demo

Login simulado: basta selecionar o usuário no /login (sem senha). Roles disponíveis:

| Email                           | Role                      | O que ele vê                                                 |
| ------------------------------- | ------------------------- | ------------------------------------------------------------ |
| `admin@latam.com`               | Platform Admin            | Tudo: Builder Studio + Business Portal + Admin               |
| `data.dev@latam.com`            | Data Developer            | Builder completo (LATAM workspace)                           |
| `analyst.br@latam.com`          | Data Analyst              | Builder restrito ao workspace **Brazil**                     |
| `finance.owner@latam.com`       | Finance Owner             | Builder + publish_finance                                    |
| `operations.owner@latam.com`    | Operations Owner          | Builder + publish_operations                                 |
| `regional.manager@latam.com`    | LATAM Executive Viewer    | Business Portal LATAM Executive                              |
| `viewer.br@latam.com`           | Viewer                    | Business Portal restrito a Brazil                            |
| `ml.owner@latam.com`            | ML Owner                  | Builder + forecasting + publish_forecast                     |

A matriz completa de permissões está em `backend/app/services/permission_service.py`.

---

## Fluxo de demonstração sugerido

1. **`admin@latam.com`**: login → home mostra workspaces, áreas e capabilities.
2. **Builder Studio → Dataset Explorer**: ver os 5 datasets sintéticos já carregados (`sales_latam`, `finance_actual_budget`, etc.).
3. **Builder Studio → Metric Builder**: ver as 15 métricas certificadas. Criar uma nova métrica:
   - Tipo: `CUSTOM_LIMITED`
   - Fórmula: `DIVIDE(SUM(savings), SUM(spend))` no dataset `supplier_performance`
   - Formato: `percent`
   - Pré-visualizar → ver o valor calculado em tempo real
4. **Builder Studio → Dashboard Builder**: criar um dashboard novo:
   - Adicionar um KPI Card (Revenue YTD)
   - Adicionar um Bar Chart (Revenue por country)
   - Adicionar um Line Chart (Revenue por mês com time_grain=month)
   - Adicionar um Text Box com insights
   - Arrastar/redimensionar widgets no grid
   - Clicar em **Enviar para aprovação** (status muda para `Pending Approval`)
5. **Logout, login como `finance.owner@latam.com`** (ou admin):
   - **Builder Studio → Publish Center → aba Pendentes**: aprovar e publicar
6. **Logout, login como `viewer.br@latam.com`**:
   - Acessa só **Business Portal → Sales** com o dashboard `Brazil Sales` (workspace Brazil)
7. **Logout, login como `regional.manager@latam.com`**:
   - Acessa **Business Portal → LATAM Executive** com o `LATAM Executive Summary` (KPIs + charts + briefing executivo)

### Fluxo Pipeline Studio (Fase 3b)

8. **`data.dev@latam.com`** → **Builder Studio → Pipeline Studio**: ver os 3 pipelines seed.
9. Abrir **"Sales Brazil — High-margin Top Clients"** → clicar em cada step e ver o **preview do DataFrame** após aquele step (filtros aplicados em cascata).
10. Clicar em **Run now** → mostra status, duração, rows in/out e o **dataset_id** gerado.
11. Voltar pro **Dataset Explorer** → o novo dataset (`Brazil Top Clients (high margin)`) aparece com source `ETL Output`, já pronto pra ser usado no Metric Builder.
12. Criar um pipeline novo do zero: adicionar steps da paleta → SOURCE → FILTER → COMPUTED → GROUP_BY → TARGET; usar preview pra validar a cada step.

### Fluxo Forecasting Studio (Fase 4)

13. **`ml.owner@latam.com`** → **Builder Studio → Forecasting Studio**: ver os 3 forecasts seed (Holt-Winters, Linear Trend, Naive Seasonal).
14. Abrir **"LATAM Revenue Forecast (Holt-Winters)"** → clicar em **Train & Backtest**:
   - Gráfico Plotly aparece com histórico (linha sólida), backtest no holdout (tracejada), forecast futuro (linha + losangos) e **banda de confiança 95%** (área translúcida).
   - Tabela de métricas mostra MAE/RMSE/MAPE — Holt-Winters atinge ~13% MAPE no histórico LATAM.
15. Abrir **"Revenue Forecast by Country"** → Train → o gráfico mostra **6 séries simultâneas** (uma por país), com toggle pela legenda. Métricas separadas por país.
16. Trocar o algoritmo para `naive_seasonal` na coluna esquerda → **Salvar config** → **Train** novamente → comparar MAPE entre algoritmos.
17. **Login como `admin@latam.com`** → na lista de forecasts, clicar em **Publicar** no forecast escolhido:
   - Backend re-treina, grava o output como `Dataset` com colunas `ds, y, yhat, yhat_lower, yhat_upper, is_forecast, group_key`.
18. **Builder Studio → Dataset Explorer** → o novo dataset `forecast_N_<nome>` aparece com source `Forecast`, pronto para ser referenciado no Metric Builder e exibido em dashboards.

### Fluxo Alerts & Notifications (Fase 5)

19. **`admin@latam.com`** → **Builder Studio → Alerts**: ver os 6 alertas seed (5 tipos cobertos).
20. Clicar **Evaluate All** → 2 alertas disparam (Revenue YTD < 5M e Forecast MAPE > 25%).
21. Observar o **sino no header** (badge vermelho com contador unread) → dropdown mostra últimas notificações com severidade colorida.
22. Clicar **Ver todas** → **Notification Center** (`/notifications`):
   - Filtrar por severidade `warning` ou status `unread`
   - Clicar **Acknowledge** em uma notification (com nota opcional)
   - Clicar **Marcar todas como lidas**
23. Voltar em **Alerts** → clicar **Test** em um alerta (dry-run, não cria notification) → ver resultado no alert dialog.
24. **`data.dev@latam.com`** → **Pipeline Studio** → rodar um pipeline que falha → alerta `pipeline_failure` dispara **automaticamente** (trigger pós-run).
25. Inspecionar e-mail mock: `backend/storage/notifications/emails.jsonl` (se canal `email` configurado no alerta).

### Fluxo Scheduler (Fase 6)

26. **`admin@latam.com`** → **Builder Studio → Scheduler**: ver badge **APScheduler: Running** e 5 jobs seed.
27. Observar **próxima execução** (`next_run_at`) calculada para cada job (cron UTC).
28. Clicar **Run now** em um pipeline job → execução imediata, status Success/Failed, duração em ms.
29. Clicar **Histórico** → ver runs anteriores com triggered_by (`manual` ou `scheduler`).
30. **Pause** um job → some do APScheduler (active_jobs diminui). **Resume** → volta a agendar.
31. **+ Novo job** → criar forecast_train semanal ou alerts_evaluate customizado.

### Fluxo Ad-Hoc Report Builder (Fase 7)

32. **`data.analyst@latam.com`** (ou `admin@latam.com`) → **Builder Studio → Ad-Hoc Report Builder**.
33. Selecionar dataset `sales_latam` → ver colunas à esquerda → clicar template **Revenue por país**.
34. **Executar preview** → tabela agregada por `country` (limitada a 200 linhas).
35. **Export CSV** → download do arquivo completo (até 10k linhas).
36. **Salvar query** com nome descritivo → aparece em **Queries salvas** (2 exemplos no seed).
37. **Salvar como Dataset** → novo dataset com source `Report Output` visível no **Dataset Explorer**.

### Fluxo Admin Panel (Fase 8)

38. **`admin@latam.com`** → menu **Admin → Users**: ver 8 usuários, editar role/workspace, criar usuário demo.
39. **Admin → Workspaces** → editar descrição do workspace Brazil ou LATAM.
40. **Admin → Permissions** → explorar matriz RBAC (roles × capabilities).
41. **Admin → Audit Logs** → filtrar por `admin@latam.com` ou action `publish_dashboard`.
42. **Admin → System Jobs** → ver saúde APScheduler, contadores de entidades, link para Scheduler.

### Fluxo Phase 9 — Extras

43. **`admin@latam.com`** → **Dataset Explorer** → selecionar `sales_latam` → aba **Lineage**: ver upstream/downstream e edges de pipelines/forecasts.
44. Aba **Quality** → **Executar checks** → score % e tabela de checks (not_null, row_count, etc.).
45. **Dashboard Builder** → abrir dashboard publicado → **Exportar PDF** (download do relatório).
46. **Alert Builder** → editar alerta → marcar canais **Slack (mock)** e **Teams (mock)** → salvar; disparar alerta e ver entradas em `backend/data/notifications/`.
47. **`ml.owner@latam.com`** → **Model Registry** → ver modelos seed → **Promover p/ Production** ou **+ Registrar modelo** vinculado a um forecast.

---

## API principal (Fase 3)

### Metrics
- `GET /metrics` — lista (filtra por dataset/workspace/status)
- `POST /metrics` — cria
- `PUT /metrics/{id}` — atualiza
- `DELETE /metrics/{id}` — remove
- `POST /metrics/preview` — calcula sob amostra (sem persistir)

### Dashboards
- `GET /dashboards` — lista (acessíveis por workspace)
- `GET /dashboards/published` — só Published, filtrados por business_area do user
- `POST /dashboards` — cria draft
- `PUT /dashboards/{id}` — atualiza metadata
- `DELETE /dashboards/{id}` — remove

### Widgets
- `POST /dashboards/{id}/widgets` — cria widget
- `PUT /dashboards/{id}/widgets/{wid}` — atualiza widget (layout + config)
- `DELETE /dashboards/{id}/widgets/{wid}` — remove widget
- `POST /dashboards/widgets/preview` — renderiza um widget ad-hoc (Dashboard Builder)
- `POST /dashboards/{id}/render` — renderiza todos os widgets do dashboard

### Publish flow
- `POST /dashboards/{id}/submit` — Draft → Pending Approval (capability `submit_for_approval`)
- `POST /dashboards/{id}/publish` — Pending/Draft → Published (capability `publish_finance|publish_operations|publish_any` por área)
- `POST /dashboards/{id}/reject` — Pending → Draft (apenas com permissão de publish na área)
- `POST /dashboards/{id}/archive` — Published → Archived

### Pipelines (Fase 3b)
- `GET /pipelines` — lista (acessíveis por workspace)
- `POST /pipelines` — cria draft (capability `create_pipeline`)
- `GET /pipelines/{id}` — detalhe (com steps)
- `PUT /pipelines/{id}` / `DELETE /pipelines/{id}` — atualiza/remove
- `POST /pipelines/{id}/steps` — adiciona step (append no final)
- `PUT /pipelines/{id}/steps/{sid}` / `DELETE /pipelines/{id}/steps/{sid}` — atualiza/remove
- `POST /pipelines/{id}/steps/reorder` — reordena (body: `{"step_ids": [...]}`)
- `POST /pipelines/preview` — preview ad-hoc (steps no payload, sem salvar)
- `POST /pipelines/{id}/preview` — preview do pipeline salvo até `up_to_index`
- `POST /pipelines/{id}/run` — executa (cria `PipelineRun`, grava TARGET, registra `Dataset`)
- `GET /pipelines/{id}/runs` — histórico de execuções
- `POST /pipelines/{id}/publish` — Draft → Published (capability `publish_pipeline|publish_any`)
- `POST /pipelines/{id}/archive` — → Archived

### Forecasts (Fase 4)
- `GET /forecasts` — lista (filtros: `workspace`, `business_area`, `status`)
- `POST /forecasts` — cria draft (capability `create_forecast`)
- `GET /forecasts/{id}` — detalhe completo
- `PUT /forecasts/{id}` / `DELETE /forecasts/{id}` — atualiza/remove
- `POST /forecasts/{id}/train` — treina + backtest (não persiste output, registra `ForecastRun`). Retorna `{points, metrics, rows_in, rows_forecast, groups_count}`.
- `POST /forecasts/{id}/publish` — treina E grava output como `Dataset` (source=`Forecast`) + status=`Published` (capability `publish_forecast|publish_any`)
- `POST /forecasts/{id}/archive` — → `Archived`
- `GET /forecasts/{id}/runs` — histórico de execuções

### Alerts (Fase 5)
- `GET /alerts` — lista (filtros: `workspace`, `business_area`, `alert_type`, `severity`, `enabled`)
- `POST /alerts` — cria (capability `create_alert`)
- `GET /alerts/{id}` — detalhe
- `PUT /alerts/{id}` / `DELETE /alerts/{id}` — atualiza/remove
- `POST /alerts/{id}/toggle` — enabled ↔ disabled
- `POST /alerts/{id}/evaluate` — avalia agora (respeita cooldown, cria notification se fired)
- `POST /alerts/{id}/test` — dry-run (ignora cooldown, NÃO cria notification)
- `POST /alerts/evaluate-all` — batch de todos os enabled

### Notifications (Fase 5)
- `GET /notifications` — inbox do usuário (filtros: `status`, `severity`, `alert_type`, `workspace`)
- `GET /notifications/summary` — contadores + últimas 5 (header bell)
- `POST /notifications/{id}/read` — marca como read
- `POST /notifications/{id}/ack` — acknowledge (body: `{"note": "..."}`)
- `POST /notifications/read-all` — marca todas unread → read

### Scheduled Jobs (Fase 6)
- `GET /scheduled-jobs/status` — status APScheduler (running, active_jobs, next_runs)
- `GET /scheduled-jobs` — lista (filtros: `workspace`, `job_type`, `enabled`)
- `POST /scheduled-jobs` — cria (capability `schedule_job`)
- `GET /scheduled-jobs/{id}` — detalhe
- `PUT /scheduled-jobs/{id}` / `DELETE /scheduled-jobs/{id}` — atualiza/remove
- `POST /scheduled-jobs/{id}/pause` — pausa (remove do APScheduler)
- `POST /scheduled-jobs/{id}/resume` — retoma
- `POST /scheduled-jobs/{id}/run-now` — executa imediatamente
- `GET /scheduled-jobs/{id}/runs` — histórico de execuções

### Ad-Hoc Reports (Fase 7)
- `GET /reports/examples` — templates SQL de exemplo
- `POST /reports/preview` — preview tabular (capability `view_datasets`)
- `POST /reports/export-csv` — download CSV (capability `create_report`)
- `POST /reports/save-dataset` — grava resultado como Dataset (capability `create_report`)
- `GET /reports/saved` — lista queries salvas
- `POST /reports/saved` — cria query salva
- `GET /reports/saved/{id}` / `PUT` / `DELETE` — CRUD
- `POST /reports/saved/{id}/run` — executa query salva (preview)

### Admin (Fase 8)
- `GET /users` / `POST /users` / `PUT /users/{id}` — gestão de usuários (`manage_users`)
- `GET /workspaces/all` / `PUT /workspaces/{id}` — admin workspaces (`manage_workspaces`)
- `GET /admin/permissions/matrix` — matriz RBAC (`manage_permissions`)
- `GET /admin/audit-logs` — trilha de auditoria (`view_audit_logs`)
- `GET /admin/system-status` — saúde da plataforma (`view_admin`)

---

## Algoritmos de Forecast (Fase 4)

| Algoritmo         | Engine                         | Quando usar                                     | Params suportados                              |
| ----------------- | ------------------------------ | ----------------------------------------------- | ---------------------------------------------- |
| `naive_seasonal`  | numpy (sem deps externas)      | Baseline rápido p/ comparação                   | `season`, `lookback_cycles`                    |
| `linear_trend`    | `sklearn.LinearRegression`     | Séries com tendência clara + sazonalidade fraca | `season`                                       |
| `holt_winters`    | `statsmodels.ExponentialSmoothing` | Séries com tendência E sazonalidade marcantes  | `trend` (add/mul), `seasonal` (add/mul), `damped`, `season` |

**Métricas calculadas no holdout** (por grupo, se `group_by` definido):
- `MAE` (Mean Absolute Error) — erro absoluto médio, mesma unidade do alvo
- `RMSE` (Root Mean Squared Error) — penaliza erros grandes
- `MAPE` (Mean Absolute Percentage Error) — em %, ignora valores zero. Heurística UI: <15% verde · <30% âmbar · >30% vermelho.

---

## Tipos de Alerta (Fase 5)

| Tipo                | Target            | `rule_config` exemplo                                                                 | Quando dispara                                      |
| ------------------- | ----------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `metric_threshold`  | `metric_id`       | `{"operator": "<", "threshold": 5000000, "period": "ytd"}`                            | Valor da métrica viola o threshold no período       |
| `metric_change`     | `metric_id`       | `{"change_pct_threshold": 10, "direction": "drop", "current_period": "mtd", "previous_period": "prev_month"}` | Variação % supera threshold entre períodos            |
| `forecast_quality`  | `forecast_id`     | `{"mape_threshold": 25, "scope": "any"}`                                              | MAPE do último run acima do limite                    |
| `pipeline_failure`  | `pipeline_id`     | `{"lookback_minutes": 60}`                                                            | Último run falhou dentro do lookback                |
| `dashboard_stale`   | `dashboard_id`    | `{"max_age_days": 7}`                                                                 | Dashboard publicado sem update há N dias              |

**Status de notification**: `unread` → `read` → `acknowledged`

**Trigger automático**: após `POST /pipelines/{id}/run` ou `POST /forecasts/{id}/train|publish`, o backend avalia alertas cujo `target_kind` + `target_id` correspondem ao objeto executado.

---

## Operadores de Pipeline (Fase 3b)

| Operador          | Config                                                                                                | Notas                                              |
| ----------------- | ----------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| `source`          | `{"dataset_id": N}`                                                                                    | Lê dataset processado                              |
| `filter`          | `{"conditions": [{"col", "op", "value"}]}` (AND, 11 ops: `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `not_in`, `contains`, `is_null`, `is_not_null`) | Coerção de tipo automática (numérica/data)         |
| `select`          | `{"columns": ["a","b"], "rename": {"a": "alpha"}}`                                                     | Subset + rename opcional                           |
| `computed`        | `{"new_col": "margin_pct", "expression": "(revenue - cost) / revenue"}`                                | `pandas.eval` (sem `eval` Python). Limite 500 char |
| `group_by`        | `{"by": ["country"], "aggs": [{"col": "revenue", "func": "sum", "as": "rev_total"}]}`                  | Funcs: sum/avg/min/max/count/nunique               |
| `join`            | `{"right_dataset_id": N, "how": "left", "left_on": "id", "right_on": "id", "suffix": "_r"}`            | left/inner/right/outer                             |
| `union`           | `{"datasets": [2, 3]}`                                                                                 | concat ignorando index                             |
| `sort`            | `{"by": ["col1", "col2"], "ascending": [false, true]}`                                                 | per-column ascending                               |
| `limit`           | `{"n": 100}`                                                                                           | head(n)                                            |
| `target`          | `{"dataset_name": "...", "workspace": "LATAM", "business_area": "Sales", "description": "..."}`        | Cria `Dataset` source=ETL Output                   |

---

## Tipos de métrica (camada semântica)

| Tipo              | Config                                                     | Exemplo                                     |
| ----------------- | ---------------------------------------------------------- | ------------------------------------------- |
| `SUM`             | `{"column": "revenue"}`                                    | Total Revenue                               |
| `AVERAGE`         | `{"column": "sla_score"}`                                  | Avg SLA Score                               |
| `COUNT`           | `{"column": "id", "distinct": true}`                       | Distinct clients                            |
| `MIN` / `MAX`     | `{"column": "lead_time"}`                                  | Min/Max lead time                           |
| `RATIO`           | `{"numerator": "margin", "denominator": "revenue"}`        | Margin ratio                                |
| `VARIATION_ABS`   | `{"actual": "actual", "baseline": "budget"}`               | Δ vs budget (absoluto)                      |
| `VARIATION_PCT`   | `{"actual": "actual", "baseline": "budget"}`               | Δ vs budget (%)                             |
| `MTD`             | `{"column": "revenue", "date_column": "date"}`             | Revenue mês corrente                        |
| `YTD`             | `{"column": "revenue", "date_column": "date"}`             | Revenue YTD                                 |
| `YOY`             | `{"column": "revenue", "date_column": "date", "mode": "percent"}` | Crescimento YoY                       |
| `CUSTOM_LIMITED`  | `{"formula": "DIVIDE(SUB(SUM(revenue), SUM(cost)), SUM(revenue))"}` | Margin % (DSL controlada)         |

---

## Notas técnicas

- **Sem `eval` aberto**: o `CUSTOM_LIMITED` é um mini-parser que aceita apenas funções permitidas (`SUM`, `AVG`, `MIN`, `MAX`, `COUNT`, `ADD`, `SUB`, `MULT`, `DIVIDE`).
- **Profiling automático**: `services/profiling_service.py` extrai dtype, null_count, distinct_count, min/max/mean/std e amostras.
- **DataFrame -> Parquet**: datasets ficam normalizados em Parquet para leitura rápida (`pyarrow`).
- **Layout drag-and-drop**: persistido no JSON `DashboardWidget.layout` (compatível com `react-grid-layout` 12 cols).
- **Render de dashboard**: backend serializa série de pontos para o Plotly do frontend (sem expor SQL/Pandas no client).
- **RBAC dupla**: capabilities + workspace + business_area. Validado em todo router via `require_capability`/`accessible_workspaces`/`can_publish_dashboard`/`can_view_business_area`.

---

## Variáveis de ambiente úteis

| Variável            | Default                            | Descrição                                                   |
| ------------------- | ---------------------------------- | ----------------------------------------------------------- |
| `VITE_API_TARGET`   | `http://127.0.0.1:8000`            | URL do backend usada pelo proxy do Vite                     |
| `LATAM_DB_URL`      | `sqlite:///./latam_analytics.db`   | (backend) String SQLAlchemy. Trocar para Postgres em prod   |
| `LATAM_CORS_ORIGINS`| `http://localhost:5173`            | (backend) Origins permitidos                                |

---

## Licença & uso

Demo interna para apresentação executiva. Dados sintéticos. Não usar em produção sem revisão de autenticação, ACL, logs, observabilidade e hardening.
