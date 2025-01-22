import httpx
import os
import pandas as pd
import pyarrow as pa
import time

def is_server_overload_error(res):
    if (
        res.status_code == 503
        and res.text == "upstream connect error or disconnect/reset before headers. reset reason: connection termination"
    ) or (res.status_code == 429 and res.text == "Rate exceeded."):
        return True
    return False

class VPAnalysisAPI:
    def __init__(
        self,
        api_key=None,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = os.environ.get("VP_ANALYSIS_API_KEY")

        # api endpoint
        self.dataApiUrl = (
            os.environ.get("VP_DATA_API_URL", "https://api.variantperception.com")
            + "/api/v1"
        )

    def get_series(self, series_list):
        df = self._get_series_internal([f"vp:{s}" for s in series_list])
        # remove vp: from the column names
        df.rename(columns=lambda x: x[3:], inplace=True)
        return df

    def _get_series_internal(
        self,
        series_list,
        freq=None,
        validate_old=None,
        currency=None,
    ):
        """
        :param series_list: list of series to be retrieved
        :return: dataframe of series
        """

        # split the request into chunks of 30 series at a time
        CHUNKING = 100
        unique_series_list = list(set(series_list))
        # get_run_logger().info(f"length of series list: {len(unique_series_list)}")
        series_chunks = [
            unique_series_list[i : i + CHUNKING]
            for i in range(0, len(unique_series_list), CHUNKING)
        ]
        df_list = []
        for chunk in series_chunks:
            # get_run_logger().info(f"chunk of length: {len(chunk)}")
            dataBody = {"series": chunk}
            if validate_old is not None:
                dataBody["validate_old"] = validate_old
            if freq is not None:
                dataBody["freq"] = freq
            if currency is not None:
                dataBody["currency"] = currency
            requestsHeaders = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            # df_res = httpx.post(dataApiUrl, json=dataBody, headers=requestsHeaders)
            with httpx.Client(http2=True) as client:
                df_res = client.post(
                    self.dataApiUrl + "/series",
                    json=dataBody,
                    headers=requestsHeaders,
                    timeout=600,
                )
            if df_res.status_code != 200:
                raise ValueError(df_res.text)

            with pa.ipc.open_file(df_res.content) as reader:
                df_list.append(reader.read_pandas())

        return pd.concat(df_list, axis=1)

    def get_df_from_series_list(
        self,
        series_list,
        freq=None,
        currency=None,
        first_revision=False,
        validate_old=None,
    ):
        return self._get_series_internal(
            series_list,
            freq=freq,
            validate_old=validate_old,
            currency=currency,
        )

    def clean_df(self, df, freq="B", start_date="1997-01-01"):
        df = df.loc[start_date:].asfreq(freq)
        for col in df:
            df[col] = df[col].ffill().where(df[col].bfill().notnull())
        # the start date will be whatever the earliest start date of any column is
        df = df.loc[df.first_valid_index() :]
        return df

    def get_security_factors(self, securities, factors):
        dataBody = {"securities": securities, "factors": factors}
        requestsHeaders = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # the dataframe is streamed as media type vnd/apache.arrow.file
        with httpx.Client(http2=True) as client:
            df_res = client.post(
                self.dataApiUrl + "/security_factors",
                json=dataBody,
                headers=requestsHeaders,
                timeout=600,
            )
        if df_res.status_code != 200:
            raise ValueError(df_res.text)

        df = None
        with pa.ipc.open_file(df_res.content) as reader:
            df = reader.read_pandas()

        df = df.pivot(
            index="dt", columns=["stock_code", "factor_identifier"], values="value"
        )
        return df

    def get_factors(self):
        requestsHeaders = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(http2=True) as client:
            df_res = client.get(
                self.dataApiUrl + "/factors",
                headers=requestsHeaders,
                timeout=600,
            )
        if df_res.status_code != 200:
            raise ValueError(df_res.text)

        df = None
        with pa.ipc.open_file(df_res.content) as reader:
            df = reader.read_pandas()
        return df

    def get_securities(self):
        requestsHeaders = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(http2=True) as client:
            df_res = client.get(
                self.dataApiUrl + "/securities",
                headers=requestsHeaders,
                timeout=600,
            )
        if df_res.status_code != 200:
            raise ValueError(df_res.text)

        df = None
        with pa.ipc.open_file(df_res.content) as reader:
            df = reader.read_pandas()
        return df

    def invalidate_cache(self, tickers):
        requestsHeaders = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        dataBody = {"tickers": tickers.tolist()}
        with httpx.Client(http2=True) as client:
            res = client.post(
                self.dataApiUrl + "/series/invalidateCache",
                headers=requestsHeaders,
                json=dataBody,
                timeout=600,
            )
            
            num_of_retries = 0
            while is_server_overload_error(res) and num_of_retries < 3:
                time.sleep(10)
                res = client.post(
                    self.dataApiUrl + "/series/invalidateCache",
                    json=dataBody,
                    headers=requestsHeaders,
                    timeout=600,
                )
                num_of_retries += 1
            
            if res.status_code != 200:
                raise ValueError(res.text)
    
    def run_lppl(self, dates: list[str], prices: list[int]):
        requestsHeaders = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data_api_request = {
            "format": "df",
            "index": dates,
            "price": prices,
        }

        with httpx.Client(http2=True) as client:
            df_res = client.post(
                self.dataApiUrl + "/model/lppl",
                json=data_api_request,
                headers=requestsHeaders,
                timeout=1200,
            )
        if df_res.status_code != 200:
            raise ValueError(df_res.text)
        
        df = None
        with pa.ipc.open_file(df_res.content) as reader:
            df = reader.read_pandas()
        return df
