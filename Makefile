.PHONY: test evaluate demo check lint
export PYTHONPATH := src

test:
	python -m unittest discover -s tests -v

evaluate:
	python -m evidence_gateway evaluate --output reports/evaluation.json

demo:
	python -m evidence_gateway demo

lint:
	python -m ruff check src tests scripts
	python -m ruff format --check src tests scripts

check: test evaluate
	python -m compileall -q src
