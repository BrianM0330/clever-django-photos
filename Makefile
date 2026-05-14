PYTHON := .venv/bin/python

.PHONY: help check server console migrations migrate test lint format db-migrations db-migrate db-reset db-setup seed collectstatic

help:
	@printf "Available commands:\n"
	@printf "  make check          Run Django system checks\n"
	@printf "  make server         Start the Django development server\n"
	@printf "  make console        Open the Django shell\n"
	@printf "  make test           Run the Django test suite\n"
	@printf "  make lint           Run Ruff\n"
	@printf "  make format         Run Black\n"
	@printf "  make migrations     Alias for db-migrations\n"
	@printf "  make migrate        Alias for db-migrate\n"
	@printf "  make db-migrations  Create Django migrations\n"
	@printf "  make db-migrate     Apply Django migrations\n"
	@printf "  make db-reset       Delete SQLite DB and migrate\n"
	@printf "  make db-setup       Migrate and seed the database\n"
	@printf "  make seed           Run seed_all\n"
	@printf "  make collectstatic  Collect static files\n"

check:
	$(PYTHON) manage.py check

server:
	$(PYTHON) manage.py runserver

console:
	$(PYTHON) manage.py shell

migrations: db-migrations

migrate: db-migrate

test:
	$(PYTHON) manage.py test

lint:
	.venv/bin/ruff check .

format:
	.venv/bin/black .

db-migrations:
	$(PYTHON) manage.py makemigrations

db-migrate:
	$(PYTHON) manage.py migrate

db-reset:
	rm -f db.sqlite3
	$(PYTHON) manage.py migrate

db-setup:
	$(PYTHON) manage.py migrate
	$(PYTHON) manage.py seed_all

seed:
	$(PYTHON) manage.py seed_all

collectstatic:
	$(PYTHON) manage.py collectstatic --noinput
