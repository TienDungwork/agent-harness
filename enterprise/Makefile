BACKEND_HOST ?= "127.0.0.1"
BACKEND_PORT = 3000
BACKEND_HOST_PORT = "$(BACKEND_HOST):$(BACKEND_PORT)"
FRONTEND_PORT = 3001
Creanova_PATH ?= ".."
Creanova := $(Creanova_PATH)
Creanova_FRONTEND_PATH = $(Creanova)/frontend/build

# ANSI color codes
GREEN=$(shell tput -Txterm setaf 2)
YELLOW=$(shell tput -Txterm setaf 3)
RED=$(shell tput -Txterm setaf 1)
BLUE=$(shell tput -Txterm setaf 6)
RESET=$(shell tput -Txterm sgr0)

build:
	@poetry install
	@cd $(Creanova) && $(MAKE) build


_run_setup:
	@echo "$(YELLOW)Starting backend server...$(RESET)"
	@cd app && FRONTEND_DIRECTORY=$(Creanova_FRONTEND_PATH) poetry run uvicorn saas_server:app --host $(BACKEND_HOST) --port $(BACKEND_PORT) &
	@echo "$(YELLOW)Waiting for the backend to start...$(RESET)"
	@until nc -z localhost $(BACKEND_PORT); do sleep 0.1; done
	@echo "$(GREEN)Backend started successfully.$(RESET)"

run:
	@echo "$(YELLOW)Running the app...$(RESET)"
	@$(MAKE) -s _run_setup
	@cd $(Creanova) && $(MAKE) -s start-frontend
	@echo "$(GREEN)Application started successfully.$(RESET)"

# Start backend
start-backend:
	@echo "$(YELLOW)Starting backend...$(RESET)"
	@echo "$(Creanova_FRONTEND_PATH)"
	@cd app && FRONTEND_DIRECTORY=$(Creanova_FRONTEND_PATH) poetry run uvicorn saas_server:app --host $(BACKEND_HOST) --port $(BACKEND_PORT) --reload-dir $(Creanova_PATH) --reload --reload-dir ./ --reload-exclude "./workspace"


lint:
	@poetry run pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
