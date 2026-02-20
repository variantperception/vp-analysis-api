# VP Analysis API - Project Context

## Project Overview
This project is a Python client library for the Variant Perception Analysis Data API. It provides structured access to VP's financial data series, security factors, and models (e.g., LPPL). 

**Main Technologies:** 
- Python 3.12+
- `pandas` (Data manipulation)
- `httpx` (HTTP/2 requests)
- `pyarrow` (Arrow IPC format for high-performance data transfer)
- `hatchling` (Build system)

**Architecture:** 
The core functionality is encapsulated in a single class, `VPAnalysisAPI`, located in `src/vp_analysis_api/VPAnalysisAPI.py`. The client authenticates via an API key, executes HTTP/2 POST/GET requests against `https://api.variantperception.com/api/v1`, and deserializes responses from Apache Arrow IPC format directly into pandas DataFrames.

## Building and Running
*   **Install Development Dependencies:**
    ```bash
    pip install -e ".[dev]"
    ```
*   **Run All Quality Tools (Formatting, Linting, & Type Checking):**
    The project includes a custom script to automate formatting and linting.
    ```bash
    python check_code.py
    ```
*   **Individual Development Commands:**
    *   Format code: `black .`
    *   Sort imports: `isort .`
    *   Lint with auto-fix: `ruff check --fix .`
    *   Type checking: `mypy src/vp_analysis_api`
*   **Build Package:**
    ```bash
    python -m build
    ```
*   **Tests:** `pytest` and `pytest-cov` are included in the dev dependencies for running standard Python unit tests.

## Development Conventions
*   **Code Style & Typing:**
    *   Strict maximum line length of 120 characters.
    *   Target Python version is 3.12+.
    *   Use MyPy for strict type checking (`disallow_untyped_defs` and `check_untyped_defs` are enforced in `pyproject.toml`).
*   **API Implementation Patterns:**
    *   **Data Format:** API responses heavily utilize the Apache Arrow IPC format (`pyarrow.ipc.open_file`) before being transformed to pandas DataFrames.
    *   **Chunking:** Time series data requests are chunked in batches of 40 via the internal `_get_series_internal()` method.
    *   **Custom Exceptions:** Use the established exception hierarchy (`VPAnalysisAPIError` -> `AuthenticationError`, `APIRequestError`, `RateLimitError`).
*   **Fetching Data Workflow (For AI Assistance):**
    When writing scripts or fetching data using this library, follow this workflow:
    1.  **Initialize Client:** Read the API key from the `VP_ANALYSIS_API_KEY` environment variable or from `~/vp_api_key.txt`.
    2.  **Identify Data Type:** Categorize the request as **Macro series** (economy-level) or **Asset-factor data** (per-security).
    3.  **Lookup Identifiers First:** Asset IDs and factor identifiers are not guessable. Always query discovery endpoints (`get_macro_series_list()`, `get_equity_assets()`, `get_factors()`) and search the resulting DataFrames (e.g., `equities[equities["name"].str.contains("Apple", case=False)]`).
    4.  **Reference Examples:** See `examples/introduction.ipynb` for concrete usage patterns.
