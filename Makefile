.PHONY: install test run all clean

install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"

test:
	.venv/bin/pytest -q

run:
	.venv/bin/company-dataset all

all: install test run

clean:
	rm -rf .venv data
