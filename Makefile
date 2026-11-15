.PHONY: test bench run mcp

test:
	python -m unittest discover -s tests -v

bench:
	python scripts/bench.py --backend sqlite --tasks 200 --workers 8

run:
	python -m swarmlab serve --port 8788

mcp:
	python -m swarmlab mcp

quality:
	python -m ruff check swarmlab tests scripts
	python -m coverage run --source=swarmlab -m unittest discover -s tests -q
	python -m coverage report

cov: quality
