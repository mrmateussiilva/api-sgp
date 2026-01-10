# Makefile para gerenciamento de releases da API SGP
# Arquitetura de releases versionadas com diretórios compartilhados

# Configurações
VERSION ?= 1.0.5
API_ROOT ?= /opt/api
RELEASES_DIR = $(API_ROOT)/releases
SHARED_DIR = $(API_ROOT)/shared
CURRENT_LINK = $(RELEASES_DIR)/current
RELEASE_DIR = $(RELEASES_DIR)/v$(VERSION)
SERVICE_NAME ?= sgp-api
PORT ?= 8000

# Cores para output
INFO = \033[0;36m
SUCCESS = \033[0;32m
WARNING = \033[0;33m
ERROR = \033[0;31m
NC = \033[0m

.PHONY: help deploy rollback list status clean setup-shared check-uv create-venv install-deps copy-files create-env update-current-link install-systemd start-service stop-service restart-service

help: ## Mostrar ajuda
	@echo "$(INFO)========================================"
	@echo "  API SGP - Gerenciamento de Releases"
	@echo "========================================$(NC)"
	@echo ""
	@echo "Uso: make [target] [VERSION=X.X.X] [API_ROOT=/path] [SERVICE_NAME=name] [PORT=8000]"
	@echo ""
	@echo "Targets disponíveis:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(INFO)%-25s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

setup-shared: ## Criar estrutura de diretórios compartilhados
	@echo "$(INFO)[INFO]$(NC) Criando estrutura de diretórios compartilhados..."
	@mkdir -p $(SHARED_DIR)/db
	@mkdir -p $(SHARED_DIR)/media/pedidos
	@mkdir -p $(SHARED_DIR)/media/fichas
	@mkdir -p $(SHARED_DIR)/media/templates
	@mkdir -p $(SHARED_DIR)/logs
	@mkdir -p $(SHARED_DIR)/backups
	@mkdir -p $(RELEASES_DIR)
	@echo "$(SUCCESS)[SUCCESS]$(NC) Estrutura de diretórios criada"

check-uv: ## Verificar se uv está instalado
	@which uv > /dev/null 2>&1 || (echo "$(ERROR)[ERROR]$(NC) uv não encontrado. Instale com: cargo install uv" && exit 1)
	@echo "$(SUCCESS)[SUCCESS]$(NC) uv encontrado: $$(uv --version)"

create-venv: ## Criar ambiente virtual para a release
	@echo "$(INFO)[INFO]$(NC) Criando ambiente virtual para release v$(VERSION)..."
	@if [ -d "$(RELEASE_DIR)/venv" ]; then \
		echo "$(WARNING)[WARNING]$(NC) Ambiente virtual já existe. Removendo..."; \
		rm -rf $(RELEASE_DIR)/venv; \
	fi
	@cd $(RELEASE_DIR) && uv venv venv
	@echo "$(SUCCESS)[SUCCESS]$(NC) Ambiente virtual criado: $(RELEASE_DIR)/venv"

install-deps: ## Instalar dependências na release
	@echo "$(INFO)[INFO]$(NC) Instalando dependências para release v$(VERSION)..."
	@cd $(RELEASE_DIR) && \
		. venv/bin/activate && \
		pip install --upgrade pip && \
		uv pip install -r requirements.txt
	@echo "$(SUCCESS)[SUCCESS]$(NC) Dependências instaladas com sucesso"

copy-files: ## Copiar arquivos para a release (excluindo db, media, logs, venv)
	@echo "$(INFO)[INFO]$(NC) Copiando arquivos para release v$(VERSION)..."
	@mkdir -p $(RELEASE_DIR)
	@rsync -av --progress \
		--exclude='db/' \
		--exclude='media/' \
		--exclude='logs/' \
		--exclude='backups/' \
		--exclude='venv/' \
		--exclude='__pycache__/' \
		--exclude='.git/' \
		--exclude='releases/' \
		--exclude='shared/' \
		--exclude='.venv/' \
		--exclude='*.pyc' \
		--exclude='*.pyo' \
		--exclude='*.db' \
		--exclude='*.db-shm' \
		--exclude='*.db-wal' \
		--exclude='.env' \
		./ $(RELEASE_DIR)/
	@echo "$(SUCCESS)[SUCCESS]$(NC) Arquivos copiados com sucesso"

create-env: ## Criar arquivo .env para a release
	@echo "$(INFO)[INFO]$(NC) Criando arquivo .env para release v$(VERSION)..."
	@cat > $(RELEASE_DIR)/.env <<EOF
# Configurações de Diretórios Compartilhados
API_ROOT=$(API_ROOT)
DATABASE_URL=sqlite:///$(shell echo $(SHARED_DIR)/db/banco.db | sed 's| |\\ |g')
MEDIA_ROOT=$(SHARED_DIR)/media
LOG_DIR=$(SHARED_DIR)/logs

# Configurações da API
ENVIRONMENT=production
VERSION=$(VERSION)
PORT=$(PORT)

# Configurações de Segurança
# IMPORTANTE: Gere uma SECRET_KEY única para produção!
SECRET_KEY=change-me-$$(uuidgen 2>/dev/null || openssl rand -hex 32)
EOF
	@echo "$(SUCCESS)[SUCCESS]$(NC) Arquivo .env criado: $(RELEASE_DIR)/.env"

update-current-link: ## Atualizar link simbólico 'current'
	@echo "$(INFO)[INFO]$(NC) Atualizando link simbólico 'current'..."
	@if [ -L "$(CURRENT_LINK)" ]; then \
		rm -f $(CURRENT_LINK); \
	elif [ -e "$(CURRENT_LINK)" ]; then \
		echo "$(WARNING)[WARNING]$(NC) 'current' existe mas não é um link simbólico. Removendo..."; \
		rm -rf $(CURRENT_LINK); \
	fi
	@ln -s $(RELEASE_DIR) $(CURRENT_LINK)
	@echo "$(SUCCESS)[SUCCESS]$(NC) Link simbólico 'current' atualizado: $(CURRENT_LINK) -> $(RELEASE_DIR)"

install-systemd: ## Instalar serviço systemd
	@echo "$(INFO)[INFO]$(NC) Instalando serviço systemd '$(SERVICE_NAME)'..."
	@if [ $$(id -u) -ne 0 ]; then \
		echo "$(ERROR)[ERROR]$(NC) Execute como root para instalar serviço"; \
		exit 1; \
	fi
	@cat > /etc/systemd/system/$(SERVICE_NAME).service <<EOF
[Unit]
Description=SGP API - Sistema de Gestão de Produção v$(VERSION)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$(CURRENT_LINK)
Environment="API_ROOT=$(API_ROOT)"
Environment="PYTHONPATH=$(CURRENT_LINK)"
Environment="PORT=$(PORT)"
ExecStart=$(CURRENT_LINK)/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port $(PORT)
Restart=always
RestartSec=10
StandardOutput=append:$(SHARED_DIR)/logs/service_stdout.log
StandardError=append:$(SHARED_DIR)/logs/service_stderr.log

[Install]
WantedBy=multi-user.target
EOF
	@systemctl daemon-reload
	@systemctl enable $(SERVICE_NAME)
	@echo "$(SUCCESS)[SUCCESS]$(NC) Serviço systemd instalado e habilitado"

start-service: ## Iniciar serviço
	@echo "$(INFO)[INFO]$(NC) Iniciando serviço '$(SERVICE_NAME)'..."
	@sudo systemctl start $(SERVICE_NAME)
	@sleep 3
	@sudo systemctl status $(SERVICE_NAME) --no-pager -l || true

stop-service: ## Parar serviço
	@echo "$(INFO)[INFO]$(NC) Parando serviço '$(SERVICE_NAME)'..."
	@sudo systemctl stop $(SERVICE_NAME)
	@echo "$(SUCCESS)[SUCCESS]$(NC) Serviço parado"

restart-service: ## Reiniciar serviço
	@echo "$(INFO)[INFO]$(NC) Reiniciando serviço '$(SERVICE_NAME)'..."
	@sudo systemctl restart $(SERVICE_NAME)
	@sleep 3
	@sudo systemctl status $(SERVICE_NAME) --no-pager -l || true

deploy: check-uv setup-shared copy-files create-venv install-deps create-env update-current-link install-systemd restart-service ## Deploy completo de nova release
	@echo ""
	@echo "$(SUCCESS)========================================"
	@echo "  ✅ Deploy da release v$(VERSION) concluído!"
	@echo "========================================$(NC)"
	@echo "Release ativa: $(CURRENT_LINK) -> $(RELEASE_DIR)"
	@echo "Diretórios compartilhados: $(SHARED_DIR)"
	@echo ""
	@echo "Status do serviço:"
	@sudo systemctl status $(SERVICE_NAME) --no-pager -l || true

rollback: ## Rollback para versão anterior (use VERSION=X.X.X)
	@if [ -z "$(VERSION)" ]; then \
		echo "$(ERROR)[ERROR]$(NC) Versão não especificada. Use: make rollback VERSION=X.X.X"; \
		exit 1; \
	fi
	@if [ ! -d "$(RELEASES_DIR)/v$(VERSION)" ]; then \
		echo "$(ERROR)[ERROR]$(NC) Release v$(VERSION) não encontrada: $(RELEASES_DIR)/v$(VERSION)"; \
		exit 1; \
	fi
	@echo "$(INFO)[INFO]$(NC) Iniciando rollback para versão v$(VERSION)..."
	@RELEASE_DIR=$(RELEASES_DIR)/v$(VERSION) $(MAKE) update-current-link VERSION=$(VERSION)
	@$(MAKE) restart-service
	@echo ""
	@echo "$(SUCCESS)========================================"
	@echo "  ✅ Rollback para versão v$(VERSION) concluído!"
	@echo "========================================$(NC)"
	@echo "Release ativa: $(CURRENT_LINK) -> $(RELEASES_DIR)/v$(VERSION)"

list: ## Listar releases disponíveis
	@echo "$(INFO)[INFO]$(NC) Releases disponíveis:"
	@if [ ! -d "$(RELEASES_DIR)" ]; then \
		echo "$(WARNING)[WARNING]$(NC) Diretório de releases não existe: $(RELEASES_DIR)"; \
		exit 0; \
	fi
	@CURRENT=$$([ -L "$(CURRENT_LINK)" ] && basename $$(readlink -f $(CURRENT_LINK)) || echo ""); \
	for release in $$(ls -1d $(RELEASES_DIR)/v* 2>/dev/null | sort -Vr); do \
		V=$$(basename $$release); \
		if [ "$$V" = "$$CURRENT" ]; then \
			echo "$(SUCCESS)[ATIVA]$(NC) $$V"; \
		else \
			echo "        $$V"; \
		fi; \
	done
	@if [ -L "$(CURRENT_LINK)" ]; then \
		echo ""; \
		echo "$(INFO)Release ativa:$(NC) $$(basename $$(readlink -f $(CURRENT_LINK)))"; \
	else \
		echo ""; \
		echo "$(WARNING)[WARNING]$(NC) Nenhuma release ativa (link 'current' não encontrado)"; \
	fi

status: ## Mostrar status do sistema de releases
	@echo "$(INFO)========================================"
	@echo "  Status do Sistema de Releases"
	@echo "========================================$(NC)"
	@echo ""
	@echo "📁 API Root: $(API_ROOT)"
	@echo "📁 Releases: $(RELEASES_DIR)"
	@echo "📁 Shared: $(SHARED_DIR)"
	@echo ""
	@$(MAKE) list
	@echo ""
	@echo "🔧 Serviço '$(SERVICE_NAME)':"
	@sudo systemctl status $(SERVICE_NAME) --no-pager -l 2>/dev/null || echo "$(WARNING)[WARNING]$(NC) Serviço não encontrado ou não está rodando"

clean: ## Limpar releases antigas (mantém apenas as últimas 5)
	@echo "$(INFO)[INFO]$(NC) Limpando releases antigas (mantendo últimas 5)..."
	@if [ ! -d "$(RELEASES_DIR)" ]; then \
		echo "$(WARNING)[WARNING]$(NC) Diretório de releases não existe"; \
		exit 0; \
	fi
	@CURRENT=$$([ -L "$(CURRENT_LINK)" ] && basename $$(readlink -f $(CURRENT_LINK)) || echo ""); \
	KEEP=$$(ls -1td $(RELEASES_DIR)/v* 2>/dev/null | head -5 | xargs -n1 basename); \
	for release in $$(ls -1td $(RELEASES_DIR)/v* 2>/dev/null); do \
		V=$$(basename $$release); \
		if echo "$$KEEP" | grep -q "$$V" || [ "$$V" = "$$CURRENT" ]; then \
			echo "$(INFO)[KEEP]$(NC) Mantendo: $$V"; \
		else \
			echo "$(WARNING)[REMOVE]$(NC) Removendo: $$V"; \
			rm -rf $$release; \
		fi; \
	done
	@echo "$(SUCCESS)[SUCCESS]$(NC) Limpeza concluída"
