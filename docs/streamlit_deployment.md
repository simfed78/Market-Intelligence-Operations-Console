# Streamlit Deployment

## Recommended Community Cloud Settings

- repository: `simfed78/Market-Intelligence-Operations-Console`
- branch: `main`
- main file path: `streamlit_app.py`

## Why Use `streamlit_app.py`

The dashboard implementation lives in `app/dashboard.py`, but `streamlit_app.py` gives Streamlit Community Cloud a simple root entrypoint.

## First Run Behavior

The dashboard can bootstrap itself.

If no saved payload exists yet, the app will offer a button to generate an initial sample payload so the UI can render without committed runtime artifacts.

## Environment Variables

Optional:

- `FRED_API_KEY`

If not provided, the app can still run using fallback/sample paths where supported.

## Deploy Steps

1. Log in to Streamlit Community Cloud.
2. Create a new app from GitHub.
3. Select repo `simfed78/Market-Intelligence-Operations-Console`.
4. Choose branch `main`.
5. Set main file path to `streamlit_app.py`.
6. Add secrets only if you want live FRED access.
7. Deploy.

## Operational Note

The dashboard is research-oriented. On hosted environments, initial runs may use fallback or synthetic data if live market and macro access is unavailable.
