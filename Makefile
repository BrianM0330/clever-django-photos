PYTHON := .venv/bin/python
DEPLOY_HOST ?= clever-vps
DEPLOY_PATH ?= /opt/clever/app
DEPLOY_SERVICE ?= clever-daphne
RAILS_DEPLOY_HOST ?= clever-vps
RAILS_DEPLOY_SOURCE ?= TEMP_RAILS_REFERENCE/rails-hotwire-trial/
RAILS_DEPLOY_PATH ?= /opt/rails-clever-gallery/app
RAILS_DEPLOY_SERVICE ?= rails-clever-gallery
RAILS_DEPLOY_DOMAIN ?= clever-rails-gallery.bmendo.dev

.PHONY: help check server console migrations migrate test lint format db-migrations db-migrate db-reset db-setup db-analytics seed collectstatic prod-build redeploy redeploy-rails

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
	@printf "  make db-analytics   Run analytics jobs\n"
	@printf "  make seed           Run seed_all\n"
	@printf "  make collectstatic  Collect static files\n"
	@printf "  make prod-build     Build CSS and collect static files\n"
	@printf "  make redeploy       Pull and redeploy on the VPS\n"
	@printf "  make redeploy-rails Sync and redeploy Rails on the VPS\n"

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

db-analytics:
	$(PYTHON) manage.py update_user_affinities
	$(PYTHON) manage.py update_photo_moods --only-missing
	$(PYTHON) manage.py update_photo_composition_scores --only-missing

seed:
	$(PYTHON) manage.py seed_all

collectstatic:
	$(PYTHON) manage.py collectstatic --noinput

prod-build:
	bin/tailwindcss -i assets/css/input.css -o static/css/app.css --minify
	$(PYTHON) manage.py collectstatic --noinput

redeploy:
	ssh $(DEPLOY_HOST) "cd $(DEPLOY_PATH) && sudo -u clever git pull && sudo -u clever .venv/bin/pip install -r requirements.txt && sudo -u clever bash -lc 'cd $(DEPLOY_PATH) && set -a && . ./.env && set +a && .venv/bin/python manage.py check && .venv/bin/python manage.py migrate && make prod-build' && sudo systemctl restart $(DEPLOY_SERVICE) && sudo systemctl status $(DEPLOY_SERVICE) --no-pager"

redeploy-rails:
	rsync -az --delete --exclude '.git/' --exclude '.bundle/' --exclude 'log/*' --exclude 'tmp/*' --exclude 'storage/*' --exclude 'node_modules/' --exclude '.ruby-lsp/' --exclude 'coverage/' --exclude '.DS_Store' $(RAILS_DEPLOY_SOURCE) $(RAILS_DEPLOY_HOST):$(RAILS_DEPLOY_PATH)/
	ssh $(RAILS_DEPLOY_HOST) "sudo chown -R railsclever:railsclever $(RAILS_DEPLOY_PATH) && sudo chmod o+x /opt/rails-clever-gallery $(RAILS_DEPLOY_PATH) && sudo -u railsclever mkdir -p $(RAILS_DEPLOY_PATH)/storage $(RAILS_DEPLOY_PATH)/log $(RAILS_DEPLOY_PATH)/tmp/pids && sudo -u railsclever perl -0pi -e 's/\"clever-rails-trial\.bmendo\.dev\"/\"clever-rails-trial.bmendo.dev\",\n    \"$(RAILS_DEPLOY_DOMAIN)\"/' $(RAILS_DEPLOY_PATH)/config/environments/production.rb && sudo -u railsclever bash -lc 'cd $(RAILS_DEPLOY_PATH) && set -a && . ./.env && set +a && bundle install && bundle exec rails db:prepare && bundle exec rails db:seed && bundle exec rails assets:precompile' && sudo systemctl restart $(RAILS_DEPLOY_SERVICE) && sudo systemctl status $(RAILS_DEPLOY_SERVICE) --no-pager"
