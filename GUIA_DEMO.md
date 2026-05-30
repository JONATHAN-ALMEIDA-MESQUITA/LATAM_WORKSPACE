# Guia de Demo — LATAM Analytics Platform

Documento operacional para **clonar, instalar, rodar e apresentar** a plataforma no computador do trabalho.  
Para detalhes técnicos das fases e APIs, veja o [README principal](./README.md).

---

## O que você vai rodar

| Serviço   | URL                              | Função                          |
|-----------|----------------------------------|---------------------------------|
| Frontend  | http://localhost:5173            | Interface React (demo)          |
| Backend   | http://127.0.0.1:8001            | API FastAPI                     |
| Swagger   | http://127.0.0.1:8001/docs       | Documentação interativa da API  |

**Login:** escolha um usuário na tela `/login` — **sem senha**.  
Recomendado para a apresentação: `admin@latam.com`.

---

## Requisitos

Instale **antes** de clonar (no PC pessoal e no PC do trabalho):

| Software    | Versão mínima | Verificar              |
|-------------|---------------|------------------------|
| Python      | 3.11+         | `python --version`     |
| Node.js     | 18+           | `node --version`       |
| npm         | (vem com Node)| `npm --version`        |
| Git         | qualquer      | `git --version`        |
| VS Code     | recomendado   | —                      |

**Espaço em disco:** ~500 MB (venv + node_modules + dados demo).  
**Rede na apresentação:** não precisa de internet depois do setup — tudo roda local.

---

## Fluxo: GitHub → PC do trabalho

### 1. Subir no GitHub (PC pessoal)

Na pasta `latam-analytics-platform`:

```powershell
git init
git add .
git commit -m "Demo LATAM Analytics Platform"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/latam-analytics-platform.git
git push -u origin main
```

> **Importante:** o `.gitignore` já exclui `.venv/`, `node_modules/`, `*.db` e uploads.  
> Não commite secrets — esta demo não usa `.env` com credenciais reais.

### 2. Clonar no PC do trabalho

```powershell
cd C:\Users\SEU_USUARIO\Documents   # ou pasta permitida pela TI
git clone https://github.com/SEU_USUARIO/latam-analytics-platform.git
cd latam-analytics-platform
code .   # abre no VS Code
```

### 3. Setup (só na primeira vez)

No terminal integrado do VS Code (**Terminal → New Terminal**), na **raiz do projeto**:

```powershell
.\scripts\setup-demo.ps1
```

Esse script:
- cria o virtualenv Python em `backend/.venv`
- instala dependências (`pip` + `npm`)
- executa todos os seeds (usuários, datasets, dashboards, pipelines, etc.)
- garante `frontend/.env.local` apontando para a API na porta 8001

**Tempo estimado:** 5–15 minutos (depende da rede para `npm install`).

### 4. Rodar a demo (todo dia / antes da reunião)

Na raiz do projeto:

```powershell
.\scripts\start-demo.ps1
```

Isso abre **duas janelas PowerShell** (backend e frontend). Aguarde ~10 segundos e acesse:

**http://localhost:5173**

Para encerrar:

```powershell
.\scripts\stop-demo.ps1
```

---

## Alternativa: tudo dentro do VS Code (sem janelas extras)

Com o projeto aberto, use **dois terminais** no VS Code (ícone **+** ou split):

**Terminal 1 — Backend:**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

**Terminal 2 — Frontend:**
```powershell
cd frontend
npm run dev
```

---

## Checklist antes da apresentação

- [ ] `.\scripts\setup-demo.ps1` já rodou com sucesso (primeira vez)
- [ ] `.\scripts\start-demo.ps1` — Swagger abre em http://127.0.0.1:8001/docs
- [ ] http://localhost:5173 carrega a tela de login
- [ ] Login com `admin@latam.com` → menu Builder Studio visível
- [ ] Business Portal mostra dashboards publicados
- [ ] Notebook na tomada; fechar apps pesados se necessário
- [ ] (Opcional) Testar Export PDF em um dashboard

---

## Roteiro rápido de apresentação (~30 min)

1. **Login** `admin@latam.com` — visão geral RBAC e workspaces  
2. **Dataset Explorer** — dados sintéticos + Lineage + Quality  
3. **Metric Builder** — métrica certificada + criar uma nova  
4. **Dashboard Builder** — widgets drag-and-drop + Export PDF  
5. **Publish Center** — enviar para aprovação  
6. Trocar para **`finance.owner@latam.com`** — aprovar/publicar  
7. **`viewer.br@latam.com`** — Business Portal (consumo read-only)  
8. **Pipeline Studio** — run pipeline → dataset gerado  
9. **Forecasting Studio** — treinar + gráfico  
10. **Admin** — Users, Permissions, Audit Logs  

Roteiro completo (passos 1–47): [README.md § Fluxo de demonstração](./README.md#fluxo-de-demonstração-sugerido).

---

## Resetar dados demo

Se algo corromper o banco local:

```powershell
Remove-Item backend\latam_analytics.db -ErrorAction SilentlyContinue
.\scripts\seed-all.ps1
```

---

## Problemas comuns

| Sintoma | Solução |
|---------|---------|
| `python` não reconhecido | Reinstalar Python marcando **Add to PATH** |
| Erro ao rodar `.ps1` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Porta 8001 em uso | `.\scripts\stop-demo.ps1` e tentar de novo |
| Frontend sem dados / erro de rede | Backend precisa estar rodando **antes**; conferir `frontend/.env.local` |
| `npm install` bloqueado pela TI | Pedir liberação do registry npm ou usar mirror corporativo |
| Seeds falham | Apagar `backend\latam_analytics.db` e rodar `.\scripts\seed-all.ps1` |

---

## Riscos em ambiente corporativo

Esta versão é um **protótipo de demonstração**. Use estes pontos na conversa com TI / segurança:

### Riscos técnicos e de segurança

| Risco | Nível na demo | Detalhe |
|-------|---------------|---------|
| **Autenticação fraca** | Alto | Login simulado, sem senha, sem MFA. Qualquer pessoa com acesso à URL “vira” qualquer usuário demo. |
| **Sem HTTPS** | Médio | Tráfego HTTP local; aceitável só em localhost, inaceitável se exposto na rede. |
| **Dados sintéticos** | Baixo | Não há dados reais de clientes/colaboradores — reduz risco de vazamento na demo. |
| **Upload de arquivos** | Médio | Usuário pode enviar CSV/XLSX; em produção exige antivírus, limites de tamanho e sandbox. |
| **SQL / expressões** | Médio | Report SQL e métricas têm guardrails, mas não substituem revisão de segurança em produção. |
| **Dependências open source** | Médio | `pip` + `npm` — TI pode exigir scan de vulnerabilidades (Snyk, Dependabot). |
| **Scheduler local** | Baixo | APScheduler roda jobs no mesmo processo; em produção usar fila/worker dedicado. |
| **Auditoria** | Baixo | Audit logs existem na demo, mas em SQLite local — não substituem SIEM corporativo. |
| **Exposição na rede** | Alto se mal configurado | Por padrão escuta `127.0.0.1` — **não** publique na LAN/internet sem hardening. |

### Riscos organizacionais / compliance

- **LGPD / dados pessoais:** demo usa dados fictícios — ok para POC; produção exige base legal, minimização e DPA.
- **Política de software:** instalar Python/Node pode exigir aprovação da TI ou uso de versões corporativas.
- **GitHub:** repositório privado recomendado; evitar código ou nomes que sugiram dados reais.
- **Expectativa de stakeholders:** deixar claro que é **POC funcional**, não produto homologado.

### O que dizer para aprovação interna

> “É uma demo **offline**, com **dados sintéticos**, rodando **apenas em localhost**, sem integração a sistemas produtivos. Serve para validar UX, fluxos de governança (RBAC, publish, lineage) e arquitetura antes de investir em infraestrutura real.”

---

## Rodar localmente vs. VM corporativa

### Opção A — Local no notebook (recomendado para POC rápida)

**Prós**
- Setup em minutos com os scripts deste guia
- Sem custo de infra
- Funciona offline na sala de reunião
- Ideal para 1 apresentador, 1 máquina

**Contras**
- Pode conflitar com políticas de instalação (Python/Node)
- Antivírus pode bloquear scripts ou portas
- Ambiente “sujo” mistura demo com ferramentas do dia a dia

**Quando escolher:** apresentação interna, POC, validação de conceito com 5–10 pessoas olhando sua tela.

---

### Opção B — VM dedicada (recomendado se TI for conservadora)

**Prós**
- **Isolamento:** demo separada do notebook corporativo
- Snapshot antes da apresentação — rollback fácil
- TI pode padronizar imagem (Python, Node, firewall)
- Possível compartilhar link interno (`http://vm-interna:5173`) para audiência remota *(requer config explícita + aprovação)*

**Contras**
- Provisionar VM leva tempo (Azure VM, AWS EC2, VMware interno)
- Ainda precisa instalar dependências na VM (mesmos scripts)
- Custo e processo de aprovação

**Quando escolher:** empresa exige ambientes isolados, demo compartilhada por vários avaliadores, ou notebook bloqueado para instalações.

---

### Opção C — Não recomendado agora

| Abordagem | Por quê evitar na fase demo |
|-----------|----------------------------|
| Expor na internet pública | Auth mock + sem WAF = risco inaceitável |
| Conectar a banco produtivo | Viola princípio de least privilege na POC |
| Docker na rede corporativa | Registry/pull images often blocked; use só se TI já tiver padrão |

---

### Recomendação prática

| Cenário | Melhor opção |
|---------|--------------|
| Apresentação presencial, TI permissiva | **Local** + `start-demo.ps1` |
| TI restritiva / notebook gerenciado | **VM** com snapshot + mesmo setup |
| Avaliação remota (5+ pessoas) | **VM** na rede interna + screen share ou URL interna *(com auth real no futuro)* |
| Piloto pós-aprovação | Kubernetes + Postgres + SSO — **fora do escopo desta demo** |

---

## Evolução pós-aprovação (visão resumida)

1. **Infra:** PostgreSQL + containers + CI/CD  
2. **Identidade:** Azure AD / Okta (SSO + MFA)  
3. **Dados:** conexão read-only ao lake/warehouse corporativo  
4. **Segurança:** HTTPS, secrets manager, scan de dependências, WAF  
5. **Observabilidade:** logs centralizados, métricas, alertas  

Esqueleto futuro já existe em `docker-compose.yml` (Postgres + backend + frontend).

---

## Comandos de referência

```powershell
# Primeira vez (após clone)
.\scripts\setup-demo.ps1

# Subir demo
.\scripts\start-demo.ps1

# Parar demo
.\scripts\stop-demo.ps1

# Só recriar dados
.\scripts\seed-all.ps1
```

---

## Usuários demo

| Email | Perfil | Uso na apresentação |
|-------|--------|---------------------|
| `admin@latam.com` | Platform Admin | Demo completa + Admin |
| `data.dev@latam.com` | Data Developer | Pipelines e métricas |
| `finance.owner@latam.com` | Finance Owner | Aprovar dashboards |
| `viewer.br@latam.com` | Viewer | Business Portal Brazil |
| `ml.owner@latam.com` | ML Owner | Forecasting + Model Registry |

Matriz completa: `backend/app/services/permission_service.py`.

---

## Suporte rápido

- Documentação técnica: [README.md](./README.md)  
- API interativa (com backend rodando): http://127.0.0.1:8001/docs  
- Dúvidas de arquitetura pós-demo: planejar workshop com TI (auth, rede, dados)
