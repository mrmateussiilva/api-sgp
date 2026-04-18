# Deploy Automatizado na Intranet

Este fluxo padroniza o deploy da API na intranet usando:

- release ZIP versionada
- diretório `shared/` para dados persistentes
- diretório `releases/` para versões isoladas
- serviço Windows via NSSM
- rollback automático em caso de falha no deploy

## Estrutura recomendada no servidor

```text
C:\api\
├── releases\
│   ├── current -> v1.0.20
│   ├── v1.0.19\
│   └── v1.0.20\
└── shared\
    ├── db\
    ├── media\
    ├── logs\
    ├── backups\
    └── .env
```

## 1. Gerar a release

Na máquina de desenvolvimento:

```powershell
cd C:\caminho\api-sgp
powershell -ExecutionPolicy Bypass -File .\scripts\build-release.ps1
```

Saída esperada:

```text
dist\api-sgp-<versao>.zip
```

Se quiser forçar outra versão ou outro diretório:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-release.ps1 `
  -Version 1.0.21 `
  -OutputDir C:\deploy `
  -Force
```

## 2. Preparar o servidor

Pré-requisitos no Windows Server:

- PowerShell 5.1+
- Python 3.12+ instalado
- `nssm.exe` no `PATH`
- serviço executado como administrador

Crie um arquivo base em `C:\api\shared\.env` com as variáveis sensíveis do ambiente, por exemplo:

```env
SECRET_KEY=troque-isto
LOG_LEVEL=INFO
DB_USER=
DB_PASS=
DB_HOST=
DB_PORT=3306
DB_NAME=
VPS_SYNC_URL=
VPS_SYNC_API_KEY=
```

O deploy complementa automaticamente:

- `API_ROOT`
- `DATABASE_URL`
- `MEDIA_ROOT`
- `LOG_DIR`
- `ENVIRONMENT`
- `VERSION`
- `PORT`

## 3. Fazer o deploy

Copie o ZIP para o servidor e execute:

```powershell
cd C:\api-sgp
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-releases.ps1 `
  -Action deploy `
  -Version 1.0.20 `
  -ReleaseZip C:\deploy\api-sgp-1.0.20.zip `
  -ApiRoot C:\api `
  -ServiceName SGP-API `
  -Port 8000
```

O script faz automaticamente:

1. para o serviço
2. cria backup do banco em `shared\backups\`
3. extrai a release em `releases\v<versao>\`
4. cria a `venv`
5. instala dependências com `pip`
6. prepara o `.env` da release
7. roda migrations
8. troca o link `current`
9. atualiza o serviço NSSM
10. sobe a API
11. valida `http://127.0.0.1:<porta>/health`

Se o healthcheck falhar, o script tenta rollback automático para a release anterior.

## 4. Rollback manual

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-releases.ps1 `
  -Action rollback `
  -RollbackVersion 1.0.19 `
  -ApiRoot C:\api `
  -ServiceName SGP-API `
  -Port 8000
```

## 5. Consultas operacionais

Listar releases:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-releases.ps1 -Action list -ApiRoot C:\api
```

Ver status:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-releases.ps1 `
  -Action status `
  -ApiRoot C:\api `
  -ServiceName SGP-API `
  -Port 8000
```

## 6. Operação recomendada

- Gere a release sempre com `build-release.ps1`.
- Não faça deploy copiando a pasta do projeto manualmente.
- Deixe dados de produção apenas em `shared/`.
- Use sempre o `shared\.env` como fonte das variáveis sensíveis.
- Mantenha pelo menos uma release anterior para rollback.
- Valide o endpoint `/health` também de outra máquina da intranet após o deploy.
