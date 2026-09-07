.PHONY: init ingest transform validate serve test docs all clean

# Default target
all: init ingest transform validate serve

# Initialize environment
init:
	docker compose up -d
	pip install -r requirements.txt
	@echo "Initializing Great Expectations..."
	@if not exist great_expectations\great_expectations.yml (gx init --config-dir great_expectations) else (echo "GX already initialized")

# Download and convert Olist data to partitioned Parquet
ingest:
	python scripts/ingest.py

# Transform raw to curated
transform:
	python scripts/transform.py

# Run Great Expectations checkpoints
validate:
	python scripts/gx_run_checkpoint.py

# Build serving layer and configure Superset
serve:
	python scripts/build_serving.py
	python scripts/superset_init.py

# Run tests
test:
	pytest tests/ -v --cov=scripts --cov-report=term-missing

# Generate documentation
docs:
	@echo "Data Docs available at: great_expectations/uncommitted/data_docs/local_site/index.html"
	@echo "Superset available at: http://localhost:8088 (admin/admin)"

# Clean generated data (preserves structure)
clean:
	@if exist data_lake\00_landing rmdir /s /q data_lake\00_landing
	@if exist data_lake\01_raw rmdir /s /q data_lake\01_raw
	@if exist data_lake\02_curated rmdir /s /q data_lake\02_curated
	@if exist data_lake\03_serving rmdir /s /q data_lake\03_serving
	@mkdir data_lake\00_landing data_lake\01_raw data_lake\02_curated data_lake\03_serving
	@echo "Data directories cleaned and recreated"

# Full rebuild from scratch
rebuild: clean all

# Help
help:
	@echo "Available targets:"
	@echo "  init      - Start Docker services and install dependencies"
	@echo "  ingest    - Download Olist data and convert to partitioned Parquet"
	@echo "  transform - Clean and enrich raw data to curated layer"
	@echo "  validate  - Run Great Expectations checkpoints"
	@echo "  serve     - Build serving layer and configure Superset"
	@echo "  test      - Run pytest suite"
	@echo "  docs      - Show documentation URLs"
	@echo "  all       - Run full pipeline (default)"
	@echo "  clean     - Remove all generated data"
	@echo "  rebuild   - Clean and rebuild everything"