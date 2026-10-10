VENV := .venv
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest
SOC := $(VENV)/bin/soc

.PHONY: all install test smoke clean

all: test

install:
	$(PYTHON) -m pip install -e .

test:
	$(PYTEST) -v

smoke:
	$(PYTHON) -m soc.cli run --scenario configs/assumptions/scenarios/smoke.yaml --report reports/smoke_report.md --csv reports/smoke_results.csv

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
