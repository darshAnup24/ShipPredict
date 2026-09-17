# Supply Chain Risk Intelligence

End-to-end supply chain risk analytics platform: ingests DataCo supply chain data into Snowflake, transforms it with dbt into a layered analytics warehouse, and trains an ML model to predict late-delivery risk with SHAP explainability.

## Architecture

```
DataCo CSVs -> Python ingestion -> Snowflake (RAW) -> dbt staging/marts/reporting -> features -> LightGBM -> SHAP
```

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Ingestion | Python | Loads DataCo supply chain CSVs into the Snowflake `RAW` schema |
| Orchestration | Airflow | Daily 6 AM DAG that runs ingestion and dbt build |
| Transformation | dbt | Staging → marts → reporting layers with tests |
| Machine Learning | LightGBM / XGBoost | Predicts late-delivery risk, SHAP feature importance |
| CI/CD | GitHub Actions | Automated dbt build and test on push |

## Repository Layout

- `ingestion/` — Snowflake ingestion script
- `airflow/dags/` — Airflow DAG for scheduling
- `models/` — dbt models (staging, marts, reporting)
- `tests/` — custom dbt tests for data quality
- `macros/`, `seeds/`, `snapshots/`, `analyses/` — dbt support directories
- `ml/` — model training and outputs
- `.github/workflows/` — CI pipeline

## Getting Started

### Prerequisites

- Python 3.9+
- Snowflake account
- dbt-core and the Snowflake adapter (`dbt-snowflake`)
- Airflow (for scheduled runs)

### 1. Configure Environment

Copy the template and fill in your Snowflake credentials:

```bash
cp .env.example .env
```

### 2. Run Ingestion

```bash
python ingestion/load_to_snowflake.py
```

### 3. Build the Warehouse with dbt

```bash
dbt deps
dbt run
dbt test
```

### 4. Select Features (SHAP)

Ranks a broad set of candidate features by mean |SHAP| value, drops
those below `SHAP_MIN_RATIO` (default `0.01`) of the top feature, and
writes the result to `ml/outputs/selected_features.json`.

```bash
python ml/select_features.py
# Optional threshold override:
# SHAP_MIN_RATIO=0.05 python ml/select_features.py
```

Outputs written to `ml/outputs/`:

- `selected_features.json` — chosen + dropped feature lists
- `feature_importance.csv` — ranked SHAP importance table
- `feature_importance.png` — importance bar chart

### 5. Train the Model

```bash
python ml/train_model.py
```

Outputs are written to `ml/outputs/`:

- `best_model.pkl` — saved LightGBM model
- `shap_summary.png` — SHAP feature importance plot
- `predictions.csv` — test set predictions

## Reporting Layer

The reporting models surface delivery KPIs, revenue, risk, and web traffic aggregates for business monitoring.