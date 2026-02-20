# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python client library for the Variant Perception Analysis Data API. Provides access to VP's financial data series, security factors, and models (e.g., LPPL). Built with httpx (HTTP/2), pandas, and pyarrow (Arrow IPC format for data transfer).

## Development Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run all code quality tools (auto-fix formatting + type check)
python check_code.py

# Individual tools
black .                      # Format code
isort .                      # Sort imports
ruff check --fix .           # Lint with auto-fix
mypy src/vp_analysis_api     # Type checking

# Build package
python -m build
```

## Architecture

The entire library is a single class `VPAnalysisAPI` in `src/vp_analysis_api/VPAnalysisAPI.py`. It authenticates via API key (constructor param or `VP_ANALYSIS_API_KEY` env var) and makes HTTP/2 POST/GET requests to `https://api.variantperception.com/api/v1`.

Key patterns:
- All API responses use **Apache Arrow IPC format** (`pyarrow.ipc.open_file`), deserialized to pandas DataFrames
- Series requests are **chunked in batches of 40** via `_get_series_internal()`
- `get_series()` is the simplified public method (auto-prepends `vp:` prefix, strips it from results); `get_df_from_series_list()` is the raw version
- Custom exception hierarchy: `VPAnalysisAPIError` -> `AuthenticationError`, `APIRequestError`, `RateLimitError`
- Base API URL is overridable via `VP_DATA_API_URL` env var

## Fetching Data

When asked to retrieve data, follow this workflow:

1. **Initialize the client**: Read the API key from `VP_ANALYSIS_API_KEY` env var or `~/vp_api_key.txt`.
2. **Identify the data type**: There are two categories:
   - **Macro series** (economy-level): use `get_macro_series_list()` to browse available tickers, then `get_df_from_macro_series_list()` to fetch.
   - **Asset-factor data** (per-security): use `get_equity_assets()` or `get_macro_assets()` to find asset IDs, and `get_factors()` to find factor identifiers, then `get_df_from_asset_factor_list()` to fetch.
3. **Look up identifiers**: Asset IDs and factor identifiers are not guessable. Always query the discovery endpoints first. Search the returned DataFrames using `str.contains()` or `.query()` to find matches (e.g., `equities[equities["name"].str.contains("Apple", case=False)]`).
4. **Fetch and post-process**: `get_df_from_asset_factor_list()` takes a list of `(asset_id, factor_identifier)` tuples. Column names in the result follow the format `vp:ss:ASSET$factor` — simplify them by parsing out the asset ID for readability.

Example: to get quality scores for specific stocks, call `get_equity_assets()` to find their asset IDs (e.g., `AAPL:NasdaqGS`), then fetch with `get_df_from_asset_factor_list([(asset_id, "quality_score") for asset_id in ids])`.

Refer to `examples/introduction.ipynb` for working examples of both macro and asset-factor data retrieval.

## Code Style

- Line length: 120 characters
- Target Python: 3.12+
