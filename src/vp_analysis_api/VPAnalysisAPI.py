import os
import time
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
import pandas as pd
import pyarrow as pa


class VPAnalysisAPIError(Exception):
    """Base exception for all VP Analysis API errors."""

    pass


class AuthenticationError(VPAnalysisAPIError):
    """Raised when there are authentication issues."""

    pass


class APIRequestError(VPAnalysisAPIError):
    """Raised when there are issues with the API request."""

    pass


class RateLimitError(VPAnalysisAPIError):
    """Raised when rate limits are exceeded."""

    pass


def is_server_overload_error(res: httpx.Response) -> bool:
    """Check if the response indicates a server overload or rate limit error.

    Args:
        res: The HTTP response to check.

    Returns:
        bool: True if the response indicates a server overload or rate limit error.
    """
    if (
        res.status_code == 503
        and res.text
        == "upstream connect error or disconnect/reset before headers. reset reason: connection termination"
    ) or (res.status_code == 429 and res.text == "Rate exceeded."):
        return True
    return False


class VPAnalysisAPI:
    """Client for interacting with the VP Analysis Data API.

    This class provides methods to interact with the VP Analysis Data API, including
    retrieving series data, security factors, and running models.

    Attributes:
        api_key (str): The API key for authentication.
        data_api_url (str): The base URL for the API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """Initialize the VP Analysis API client.

        Args:
            api_key: Optional API key. If not provided, will look for VP_ANALYSIS_API_KEY
                    in environment variables.

        Raises:
            AuthenticationError: If no API key is found.
        """
        env_key = os.environ.get("VP_ANALYSIS_API_KEY")
        if api_key is not None:
            self.api_key = api_key
        elif env_key is not None:
            self.api_key = env_key
        else:
            raise AuthenticationError(
                "No API key provided. Set VP_ANALYSIS_API_KEY environment variable or pass api_key parameter."
            )

        self.data_api_url = (
            os.environ.get("VP_DATA_API_URL", "https://api.variantperception.com") + "/api/v1"
        )

    def get_series(
        self,
        series_list: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Get series data for the specified series list.

        Args:
            series_list: List of series tickers to retrieve.
            start_date: Optional start date in YYYY-MM-DD format.
            end_date: Optional end date in YYYY-MM-DD format.

        Returns:
            pd.DataFrame: DataFrame containing the requested series data.

        Raises:
            APIRequestError: If the API request fails.
            RateLimitError: If rate limits are exceeded.
        """
        try:
            df = self._get_series_internal(
                [f"vp:{s}" for s in series_list], start_date=start_date, end_date=end_date
            )
            df.rename(columns=lambda x: x[3:], inplace=True)
            return df
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please try again later.") from e
            raise APIRequestError(f"Failed to get series data: {str(e)}") from e
        except Exception as e:
            raise APIRequestError(f"Unexpected error while getting series data: {str(e)}") from e

    def _get_series_internal(
        self,
        series_list: List[str],
        freq: Optional[str] = None,
        validate_old: Optional[bool] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> pd.DataFrame:
        """Internal method to get series data with chunking support.

        Args:
            series_list: List of series tickers to retrieve.
            freq: Optional frequency for the data.
            validate_old: Optional flag to validate old data.
            start_date: Optional start date in YYYY-MM-DD format.
            end_date: Optional end date in YYYY-MM-DD format.
            currency: Optional currency code.

        Returns:
            pd.DataFrame: DataFrame containing the requested series data.

        Raises:
            APIRequestError: If the API request fails.
            RateLimitError: If rate limits are exceeded.
        """
        CHUNKING = 100
        unique_series_list = list(set(series_list))
        series_chunks = [
            unique_series_list[i : i + CHUNKING]
            for i in range(0, len(unique_series_list), CHUNKING)
        ]

        df_list = []
        for chunk in series_chunks:
            data_body: Dict[str, Any] = {"series": chunk}
            if validate_old is not None:
                data_body["validate_old"] = validate_old
            if freq is not None:
                data_body["freq"] = freq
            if currency is not None:
                data_body["currency"] = currency
            if start_date is not None:
                data_body["start_date"] = start_date
            if end_date is not None:
                data_body["end_date"] = end_date

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            try:
                with httpx.Client(http2=True, base_url=self.data_api_url) as client:
                    response = client.post("/series", json=data_body, headers=headers, timeout=600)

                if response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded. Please try again later.")
                if response.status_code != 200:
                    raise APIRequestError(
                        f"API request failed with status {response.status_code}: {response.text}"
                    )

                with pa.ipc.open_file(response.content) as reader:
                    df_list.append(reader.read_pandas())

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded. Please try again later.") from e
                raise APIRequestError(f"Failed to get series data: {str(e)}") from e
            except Exception as e:
                raise APIRequestError(
                    f"Unexpected error while getting series data: {str(e)}"
                ) from e

        return pd.concat(df_list, axis=1)

    def get_df_from_series_list(
        self,
        series_list: List[str],
        freq: Optional[str] = None,
        currency: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        validate_old: Optional[bool] = None,
    ) -> pd.DataFrame:
        """Get DataFrame from a list of series with optional parameters.

        Args:
            series_list: List of series tickers to retrieve.
            freq: Optional frequency for the data.
            currency: Optional currency code.
            start_date: Optional start date in YYYY-MM-DD format.
            end_date: Optional end date in YYYY-MM-DD format.
            validate_old: Optional flag to validate old data.

        Returns:
            pd.DataFrame: DataFrame containing the requested series data.

        Raises:
            APIRequestError: If the API request fails.
            RateLimitError: If rate limits are exceeded.
        """
        return self._get_series_internal(
            series_list,
            freq=freq,
            validate_old=validate_old,
            start_date=start_date,
            end_date=end_date,
            currency=currency,
        )

    def clean_df(
        self,
        df: pd.DataFrame,
        freq: str = "B",
        start_date: str = "1997-01-01",
    ) -> pd.DataFrame:
        """Clean and format the DataFrame.

        Args:
            df: Input DataFrame to clean.
            freq: Frequency to resample the data to (default: "B" for business days).
            start_date: Start date to filter the data from (default: "1997-01-01").

        Returns:
            pd.DataFrame: Cleaned and formatted DataFrame.
        """
        df = df.loc[pd.to_datetime(start_date) :].asfreq(freq)
        for col in df:
            df[col] = df[col].ffill().where(df[col].bfill().notnull())
        df = df.loc[df.first_valid_index() :]
        return df

    def get_security_factors(
        self,
        securities: List[str],
        factors: List[str],
    ) -> pd.DataFrame:
        """Get security factors data.

        Args:
            securities: List of security tickers.
            factors: List of factor identifiers.

        Returns:
            pd.DataFrame: DataFrame containing the security factors data.

        Raises:
            APIRequestError: If the API request fails.
            RateLimitError: If rate limits are exceeded.
        """
        data_body = {"securities": securities, "factors": factors}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(http2=True, base_url=self.data_api_url) as client:
                response = client.post(
                    "/security_factors", json=data_body, headers=headers, timeout=600
                )

            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please try again later.")
            if response.status_code != 200:
                raise APIRequestError(
                    f"API request failed with status {response.status_code}: {response.text}"
                )

            with pa.ipc.open_file(response.content) as reader:
                df = reader.read_pandas()

            df = df.pivot(index="dt", columns=["stock_code", "factor_identifier"], values="value")
            return df

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please try again later.") from e
            raise APIRequestError(f"Failed to get security factors: {str(e)}") from e
        except Exception as e:
            raise APIRequestError(
                f"Unexpected error while getting security factors: {str(e)}"
            ) from e

    def get_factors(self) -> pd.DataFrame:
        """Get available factors data.

        Returns:
            pd.DataFrame: DataFrame containing the available factors.

        Raises:
            APIRequestError: If the API request fails.
            RateLimitError: If rate limits are exceeded.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(http2=True, base_url=self.data_api_url) as client:
                response = client.get("/factors", headers=headers, timeout=600)

            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please try again later.")
            if response.status_code != 200:
                raise APIRequestError(
                    f"API request failed with status {response.status_code}: {response.text}"
                )

            with pa.ipc.open_file(response.content) as reader:
                return reader.read_pandas()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please try again later.") from e
            raise APIRequestError(f"Failed to get factors: {str(e)}") from e
        except Exception as e:
            raise APIRequestError(f"Unexpected error while getting factors: {str(e)}") from e

    def get_securities(self) -> pd.DataFrame:
        """Get available securities data.

        Returns:
            pd.DataFrame: DataFrame containing the available securities.

        Raises:
            APIRequestError: If the API request fails.
            RateLimitError: If rate limits are exceeded.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(http2=True, base_url=self.data_api_url) as client:
                response = client.get("/securities", headers=headers, timeout=600)

            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please try again later.")
            if response.status_code != 200:
                raise APIRequestError(
                    f"API request failed with status {response.status_code}: {response.text}"
                )

            with pa.ipc.open_file(response.content) as reader:
                return reader.read_pandas()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please try again later.") from e
            raise APIRequestError(f"Failed to get securities: {str(e)}") from e
        except Exception as e:
            raise APIRequestError(f"Unexpected error while getting securities: {str(e)}") from e

    def invalidate_cache(self, tickers: np.ndarray) -> None:
        """Invalidate the cache for specified tickers.

        Args:
            tickers: List of tickers to invalidate cache for.

        Raises:
            APIRequestError: If the API request fails.
            RateLimitError: If rate limits are exceeded.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data_body = {"tickers": tickers.tolist()}

        try:
            with httpx.Client(http2=True, base_url=self.data_api_url) as client:
                response = client.post(
                    "/series/invalidateCache", headers=headers, json=data_body, timeout=600
                )

            num_of_retries = 0
            while is_server_overload_error(response) and num_of_retries < 3:
                time.sleep(10)
                with httpx.Client(http2=True, base_url=self.data_api_url) as client:
                    response = client.post(
                        "/series/invalidateCache", json=data_body, headers=headers, timeout=600
                    )
                num_of_retries += 1

            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please try again later.")
            if response.status_code != 200:
                raise APIRequestError(
                    f"API request failed with status {response.status_code}: {response.text}"
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please try again later.") from e
            raise APIRequestError(f"Failed to invalidate cache: {str(e)}") from e
        except Exception as e:
            raise APIRequestError(f"Unexpected error while invalidating cache: {str(e)}") from e

    def run_lppl(
        self,
        dates: List[str],
        prices: List[float],
    ) -> pd.DataFrame:
        """Run the LPPL (Log-Periodic Power Law) model on the given data.

        Args:
            dates: List of dates in YYYY-MM-DD format.
            prices: List of prices corresponding to the dates.

        Returns:
            pd.DataFrame: DataFrame containing the LPPL model results.

        Raises:
            APIRequestError: If the API request fails.
            RateLimitError: If rate limits are exceeded.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data_body = {
            "format": "df",
            "index": dates,
            "price": prices,
        }

        try:
            with httpx.Client(http2=True, base_url=self.data_api_url) as client:
                response = client.post(
                    "/model/lppl", json=data_body, headers=headers, timeout=1200
                )

            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please try again later.")
            if response.status_code != 200:
                raise APIRequestError(
                    f"API request failed with status {response.status_code}: {response.text}"
                )

            with pa.ipc.open_file(response.content) as reader:
                return reader.read_pandas()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please try again later.") from e
            raise APIRequestError(f"Failed to run LPPL model: {str(e)}") from e
        except Exception as e:
            raise APIRequestError(f"Unexpected error while running LPPL model: {str(e)}") from e
