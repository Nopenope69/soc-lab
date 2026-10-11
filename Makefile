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

full:
	$(PYTHON) -m soc.cli run --all --profile automotive --seeds 10 --report reports/automotive_report.md --csv reports/automotive_results.csv
	$(PYTHON) -m soc.cli run --all --profile bess --seeds 10 --report reports/bess_report.md --csv reports/bess_results.csv

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
