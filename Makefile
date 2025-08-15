.PHONY: help install-dev setup-dev format lint test clean secrets-baseline

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install-dev: ## Install development dependencies
	pip install pre-commit detect-secrets

setup-dev: install-dev ## Set up development environment
	pre-commit install
	@echo "Creating initial secrets baseline..."
	detect-secrets scan > .secrets.baseline || true
	@echo "Development environment setup complete!"

format: ## Format code with black and isort
	black src/ tests/
	isort src/ tests/

lint: ## Run linting with ruff
	ruff check src/ tests/
	ruff check --fix src/ tests/

test: ## Run tests
	pytest -v

test-coverage: ## Run tests with coverage
	pytest --cov=src --cov-report=html --cov-report=term

clean: ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -f .coverage

secrets-baseline: ## Update secrets baseline
	detect-secrets scan > .secrets.baseline

pre-commit-all: ## Run all pre-commit hooks
	pre-commit run --all-files
