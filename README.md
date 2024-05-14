# VP Analysis API

This package allows access to the VP data and models via the API.

Steps to use:

1. Contact the client team to ensure you have permissions to the api
2. Go to the [API Key settings on the VP portal](https://portal.variantperception.com/user/settings?tab=api%20keys) to generate an api key.
3. Download the file or copy the key into your environment variables as VP_ANALYSIS_API_KEY
4. Install the repo into your python project

To install:

```shell
pip install git+https://github.com/variantperception/vp-analysis-api.git
```

To use:

```python
from vp_analysis_api import VPAnalysisAPI

vp = VPAnalysisAPI("your-api-key")

vp.get_series(['lei_us_grow'])
vp.get_security_factors(['AAPL:NasdaqGS'],['vp_crowding_score', 'capital_cycle_score'])
```
