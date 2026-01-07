#!/bin/bash
# Скрипт для создания начальной миграции
cd backend
python -m alembic revision --autogenerate -m "Initial migration: create all tables"
python -m alembic upgrade head
