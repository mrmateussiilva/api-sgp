# Migracao do shared para fora da API (Windows Server + NSSM)

Este guia move o `shared/` para `C:\api\shared` mantendo a API em `C:\api\api-versao-x`.

## Pre-requisitos

- Servico NSSM configurado (ex.: `SGP-API`)
- Acesso administrativo ao servidor

## Passo a passo

1) Parar o servico:

```powershell
nssm stop SGP-API
```

2) Criar a estrutura do shared:

```powershell
mkdir C:\api\shared\db
mkdir C:\api\shared\media
mkdir C:\api\shared\logs
mkdir C:\api\shared\backups
```

3) Mover os dados atuais da API para o shared:

```powershell
Move-Item C:\api\api-versao-x\db\* C:\api\shared\db\
Move-Item C:\api\api-versao-x\media\* C:\api\shared\media\
Move-Item C:\api\api-versao-x\logs\* C:\api\shared\logs\
Move-Item C:\api\api-versao-x\backups\* C:\api\shared\backups\
```

4) Criar/ajustar o `.env` em `C:\api\api-versao-x\.env`:

```
API_ROOT=C:\api
DATABASE_URL=sqlite:///C:/api/shared/db/banco.db
MEDIA_ROOT=C:/api/shared/media
LOG_DIR=C:/api/shared/logs
```

5) Iniciar o servico novamente:

```powershell
nssm start SGP-API
```

6) Validar:
- Acesse `GET /health`
- Confirme que novos arquivos aparecem em `C:\api\shared\media`

## Observacoes

- O `API_ROOT` aponta para `C:\api`, e o `shared/` fica em `C:\api\shared`.
- Se o nome do servico NSSM for diferente, ajuste nos comandos.
