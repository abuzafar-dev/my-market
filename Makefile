PY    ?= .venv/bin/python
PHONE ?= +998900000001
COUNT ?= 500

.PHONY: help run seed migrate test docker

help:
	@echo "make run      — backend + frontend (localhost va telefon, HTTPS)"
	@echo "make seed     — lokal bazani rasmli demo mahsulotlar bilan to'ldirish"
	@echo "                (PHONE=$(PHONE) COUNT=$(COUNT) bilan o'zgartirish mumkin)"
	@echo "make migrate  — migratsiyalarni qo'llash"
	@echo "make test     — testlar"
	@echo "make docker   — butun stekni Docker Compose'da ishga tushirish"

run: migrate
	./scripts/dev.sh

seed: migrate
	$(PY) manage.py seed_demo
	$(PY) manage.py seed_demo_products --phone "$(PHONE)" --count $(COUNT)

migrate:
	$(PY) manage.py migrate --noinput

test:
	DJANGO_SETTINGS_MODULE=config.settings.test $(PY) manage.py test

docker:
	./run.sh
