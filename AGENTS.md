# VP Analysis API: Instructions for AI Agents

These instructions tell an AI agent how to fetch data from the Variant Perception (VP) Analysis Data API with the
`vp-analysis-api` Python package. Add them to your project's agent instruction file (`AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`, `.cursor/rules`, etc.), or reference this file from it.

## Setup

Install the package (Python 3.12+):

```bash
pip install git+https://github.com/variantperception/vp-analysis-api.git
```

Create the client. The API key comes from the `VP_ANALYSIS_API_KEY` environment variable or from `~/vp_api_key.txt`.
Never hard-code, print, or log the full key.

```python
import os

from vp_analysis_api import VPAnalysisAPI

api_key = os.environ.get("VP_ANALYSIS_API_KEY")
if api_key is None:
    with open(os.path.expanduser("~/vp_api_key.txt")) as f:
        api_key = f.read().strip()
api = VPAnalysisAPI(api_key)
```

## Data types

There are two kinds of data. Work out which one the request needs before writing any code.

| Type | What it is | Discovery methods | Fetch method |
|---|---|---|---|
| **Macro series** | Economy-level time series (e.g. leading indicators, liquidity, central bank policy, macro risk) | `get_macro_series_list()` | `get_df_from_macro_series_list(tickers)` |
| **Asset-factor data** | A VP factor for a specific asset (single stock, index, ETF, FX, rates, spreads) | `get_equity_assets()`, `get_macro_assets()`, `get_factors()` | `get_df_from_asset_factor_list([(asset_id, factor_identifier), ...])` |

The discovery methods return pandas DataFrames with these columns:

| Method | Key columns | Example IDs |
|---|---|---|
| `get_macro_series_list()` | `ticker`, `name`, `model`, `asset`, `region` | `globexliq24`, `lei_us_grow_rgdp` |
| `get_equity_assets()` | `asset_id`, `name`, `country`, `industry` | `AAPL:NasdaqGS`, `000001:SZSE` |
| `get_macro_assets()` | `asset_id`, `name`, `assetclass`, `country` | `spx`, `vix`, `ushysp` |
| `get_factors()` | `factor_identifier`, `factor_name`, `factor_description` | `quality_score`, `vp_fast_money` |

## Rules

1. **Never guess identifiers.** Tickers, asset IDs, and factor identifiers can't be inferred from names. Always look
   them up with the discovery methods first.
2. **Search, then confirm.** Use case-insensitive substring matching on `name` (and `factor_description` for
   factors). If several rows plausibly match, show them to the user instead of silently picking one.
   ```python
   equities = api.get_equity_assets()
   equities[equities["name"].str.contains("apple", case=False)]

   factors = api.get_factors()
   factors[factors["factor_name"].str.contains("quality", case=False)]
   ```
3. **Call each discovery method once per session** and reuse the DataFrame. Each call downloads the full list.
4. **Batch requests.** Pass every ticker or `(asset_id, factor)` pair in a single fetch call rather than looping one
   at a time. The client splits large requests automatically.
5. **Limit the date range** with `start_date` / `end_date` (`"YYYY-MM-DD"`) when only a window is needed.

## LPPL Factors

There are several public LPPL factors. 

Flagship signals:
- `lppl3`: LPPL buy and sell (+1/-1) on individual assets
- `lp_brd`: Percentage of active lppl3 signals among constituents of a stock index

Supplementary signals indicating when LPPL patterns have been found, but not fully triggered:
- `lppl_fnd`: LPPL pattern detected on some timeframes
- `lp_dbf`: LPPL bubble pattern detected on daily prices
- `lp_dcf`: LPPL crash pattern detected on daily prices

Deprecated:
- `lppl_bubble`
- `lppl_crash`
- `lppl_sig`

## Fetching

```python
# Macro series
macro_series = api.get_macro_series_list()
ticker = macro_series.query("name == 'Global Excess Liquidity'").ticker.squeeze()
df = api.get_df_from_macro_series_list([ticker], start_date="2010-01-01")

# Asset-factor data
equities = api.get_equity_assets()
factors = api.get_factors()
apple = equities.query("name == 'Apple Inc.'").asset_id.squeeze()
quality = factors.query("factor_name == 'VP Quality Score'").factor_identifier.squeeze()
df = api.get_df_from_asset_factor_list([(apple, quality)], start_date="2020-01-01")
```

Both fetch methods accept:

- `start_date`, `end_date`: `"YYYY-MM-DD"` strings.
- `first_revision`: `False` (default) returns the latest revised values. `True` returns values as first published.
  Use `True` for backtests to avoid look-ahead bias.
- `freq`: optional output frequency. See the [Swagger docs](https://api.variantperception.com/docs) for accepted
  values.

## Working with results

Results are a DataFrame indexed by date (`dt`) with one column per series. Column names use VP's internal format:

| Data type | Column name | With `first_revision=True` |
|---|---|---|
| Macro series | `vp:<ticker>` | `vp:<ticker>[0]` |
| Asset-factor data | `vp:ss:<asset_id>$<factor_identifier>` | `vp:ss:<asset_id>$<factor_identifier>[0]` |

- **Select columns by name, not position.** Column order isn't guaranteed to match the request order, and duplicate
  requests are dropped.
- **Simplify column names** before presenting results. Asset IDs can contain `:` (e.g. `AAPL:NasdaqGS`), so split
  on the last `$`, not on `:`.
  ```python
  # Macro: "vp:globexliq24" -> "globexliq24"
  df.columns = [c.removeprefix("vp:").removesuffix("[0]") for c in df.columns]

  # Asset-factor: "vp:ss:AAPL:NasdaqGS$quality_score" -> ("AAPL:NasdaqGS", "quality_score")
  df.columns = pd.MultiIndex.from_tuples(
      [tuple(c.removeprefix("vp:ss:").removesuffix("[0]").rsplit("$", 1)) for c in df.columns],
      names=["asset_id", "factor"],
  )
  ```
- **Series frequencies differ.** Some series are monthly, some daily (including weekend rows with `NaN`), so
  combined DataFrames will have gaps. `api.clean_df(df, freq="B", start_date="1997-01-01")` resamples to business
  days and forward-fills each series up to its last observation.

## Errors

All exceptions derive from `VPAnalysisAPIError` (importable from `vp_analysis_api.VPAnalysisAPI`):

- `AuthenticationError`: no API key was found. Ask the user to set `VP_ANALYSIS_API_KEY` or create
  `~/vp_api_key.txt`. Keys are generated on the [VP portal](https://portal.variantperception.com/vp-data-api).
- `APIRequestError`: the request failed. If the message mentions "Rate limit exceeded", wait and retry with
  backoff. Otherwise, check the identifiers and report the error to the user rather than retrying blindly.

## Other capabilities

- `run_lppl(dates, prices)` runs VP's LPPL (Log-Periodic Power Law) bubble/crash model on a price series you
  supply. It returns a DataFrame with `price` and `signal` columns.

## References

- [Introduction notebook](https://github.com/variantperception/vp-analysis-api/blob/main/examples/introduction.ipynb):
  macro and asset-factor examples
- [LPPL notebook](https://github.com/variantperception/vp-analysis-api/blob/main/examples/model_api_lppl.ipynb):
  running the LPPL model
- [Ticker finder on the VP portal](https://portal.variantperception.com/vp-data-api): interactive identifier search
- [Swagger docs](https://api.variantperception.com/docs): full REST API reference
