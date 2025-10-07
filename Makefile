# Makefile for VirtualBox EDR Malware Analysis System

.PHONY: help install install-dev test lint format clean build release

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install production dependencies"
	@echo "  install-dev  - Install development dependencies"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code with black and isort"
	@echo "  clean        - Clean build artifacts"
	@echo "  build        - Build distribution packages"
	@echo "  release      - Create a new release (requires VERSION=x.y.z)"
	@echo "  run          - Run the development server"


# Installation targets
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -e ".[dev]"
	pre-commit install

# Testing and quality
test:
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term

test-fast:
	pytest tests/ -v -x

lint:
	flake8 app/ tests/
	black --check app/ tests/
	isort --check-only app/ tests/
	bandit -r app/
	safety check

format:
	black app/ tests/
	isort app/ tests/

# Security checks
security:
	bandit -r app/ -f json -o bandit-report.json
	safety check --json --output safety-report.json

# Build and release
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

release:
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION is required. Usage: make release VERSION=1.0.1"; \
		exit 1; \
	fi
	python scripts/release.py $(VERSION)

# Development server
run:
	python main.py

run-dev:
	uvicorn main:app --host 0.0.0.0 --port 8000 --reload



# Documentation
docs:
	@echo "Documentation is available in README.md"
	@echo "API docs will be available at http://localhost:8000/docs when running"

# Setup development environment
setup-dev: install-dev
	@echo "Development environment setup complete!"
	@echo "Run 'make run-dev' to start the development server"

# Check project health
check: lint test
	@echo "All checks passed!"

# Show project info
info:
	@echo "VirtualBox EDR Malware Analysis System"
	@echo "======================================"
	@python -c "from app import __version__; print(f'Version: {__version__}')"
	@echo "Python: $(shell python --version)"
	@echo "Platform: $(shell python -c 'import platform; print(platform.platform())')"
