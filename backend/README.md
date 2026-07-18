# V1.0 Stage-1 Backend

This backend is the first-stage service wrapper for the existing dermatology
knowledge graph and KG-RAG research demos.

## Scope

Implemented in this stage:

- Health check.
- Knowledge graph status.
- HAM10000 seven-disease list.
- Disease evidence query.
- Feature-to-disease reverse lookup.
- Evidence context construction.
- KG-RAG prompt construction.
- Template fallback generation using only graph evidence.
- Reserved `analysis-runs` endpoint returning an explicit not-implemented error.

Not implemented in this stage:

- SQLAlchemy or SQLite business tables.
- Case workflow.
- Candidate disease ranking.
- Automatic evidence consistency validation.
- Vue frontend.
- Neo4j.
- Real LLM API calls.
- Image classification or Grad-CAM.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## Run

```bash
uvicorn backend.app.main:app --reload
```

## Test

Run tests from the repository root:

```bash
python -m pytest -q
```

Or run only backend tests:

```bash
python -m pytest -q backend/tests
```

## Configuration

`KG_CSV_DIR` can be set to override the default knowledge graph CSV directory.
By default the backend reads `kg/csv/` from the repository root.
