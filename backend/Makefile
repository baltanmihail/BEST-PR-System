# Makefile для удобства работы с проектом

.PHONY: help install migrate upgrade downgrade test run

help:
	@echo "Доступные команды:"
	@echo "  make install     - Установить зависимости"
	@echo "  make migrate     - Создать новую миграцию"
	@echo "  make upgrade     - Применить миграции"
	@echo "  make downgrade   - Откатить последнюю миграцию"
	@echo "  make test        - Запустить тесты"
	@echo "  make run         - Запустить сервер разработки"

install:
	pip install -r requirements.txt

migrate:
	alembic revision --autogenerate -m "$(msg)"

upgrade:
	alembic upgrade head

downgrade:
	alembic downgrade -1

test:
	pytest

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
