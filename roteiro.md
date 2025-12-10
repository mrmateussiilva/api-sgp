# Roteiro de atualização automática no Windows

Objetivo: configurar uma rotina que verifica novas versões do SGP, baixa e instala o MSI automaticamente sempre que o servidor publicar uma release mais recente.

---

## 1. Pré-requisitos
- Windows 10 ou superior.
- Permissão para executar scripts PowerShell (ajuste `Set-ExecutionPolicy RemoteSigned` se precisar).
- Projeto clonado em um diretório acessível (ex.: `C:\SGP\api-sgp`).
- Manifesto JSON de releases publicado em `https://sgp.finderbit.com.br/update/releases/latest.json` (ajuste a URL se necessário).

## 2. Teste local do atualizador
1. Abra o **PowerShell**.
2. Navegue até a pasta do projeto: `cd C:\SGP\api-sgp`.
3. Rode:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\update.ps1 `
     -ManifestUrl https://sgp.finderbit.com.br/update/releases/latest.json `
     -MsiArgs "/qn"
   ```
4. Se houver versão nova, o script baixa o MSI para `%TEMP%\sgp_updater`, executa `msiexec /qn` e grava `C:\ProgramData\SGP\version.json`. Use `-Force` para reinstalar mesmo sem release nova.

## 3. Agendamento no Task Scheduler
1. Abra **Agendador de Tarefas** (Task Scheduler).
2. Clique em **Ação > Criar Tarefa**.
3. Aba **Geral**:
   - Nome: `SGP Updater`.
   - Marque “Executar com privilégios mais altos”.
4. Aba **Disparadores**:
   - Clique em **Novo...** e defina a frequência (ex.: diariamente às 03:00).
5. Aba **Ações**:
   - Ação: **Iniciar um programa**.
   - Programa/script: `powershell`
   - Adicionar argumentos:
     ```
     -ExecutionPolicy Bypass -File "C:\SGP\api-sgp\scripts\update.ps1" -ManifestUrl https://sgp.finderbit.com.br/update/releases/latest.json -MsiArgs "/qn"
     ```
   - Iniciar em: `C:\SGP\api-sgp`.
6. Opcional: configure a aba **Condições** para não rodar com bateria e a aba **Configurações** para repetir em caso de falha.
7. Clique em **OK** e forneça credenciais de administrador quando solicitado.

## 4. Monitoramento e manutenção
- O histórico da tarefa mostra se o script executou com sucesso. Consulte o **Visualizador de Eventos** se precisar debugar erros.
- O arquivo `C:\ProgramData\SGP\version.json` indica a última versão aplicada. Apague-o ou use `--force` se precisar reinstalar.
- Em caso de falhas de download, verifique conectividade com `https://sgp.finderbit.com.br` e espaço em disco em `%TEMP%`.

## 5. Checklist rápido
- [ ] PowerShell habilitado (ExecutionPolicy ajustado para permitir o script).
- [ ] Projeto atualizado com `scripts/update.ps1`.
- [ ] Manifesto válido acessível via HTTPS.
- [ ] Task Scheduler configurado com privilégio elevado.
- [ ] Teste manual executado pelo menos uma vez.

Salvar este roteiro junto ao repositório facilita replicar a configuração em máquinas novas.
