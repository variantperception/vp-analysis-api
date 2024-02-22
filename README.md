# VP Analysis API

This package allows access to the VP models and data via our API. Users need an API key from the VP portal in order to query for data.

To install:

```
pip install vp-analysis-api
```

To use:

```
from vp_analysis_api import VPAnalysisAPI

vp = VPAnalysisAPI(<api-key>)

vp.get_series(['vp:spx_fast_money'])
```

You can also set the api key as an environment variable: VP_ANALYSIS_API_KEY
