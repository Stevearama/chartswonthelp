# prophet.py
import numpy as np
import pandas as pd
from prophet import Prophet

import logging
import warnings

# Suppress warnings
warnings.filterwarnings("ignore")

# Suppress all logging from Prophet and cmdstanpy
logging.getLogger("prophet").setLevel(logging.CRITICAL)
logging.getLogger("cmdstanpy").setLevel(logging.CRITICAL)
logging.getLogger("prophet").disabled = True
logging.getLogger("cmdstanpy").disabled = True

def forecast_planned_outages(
    df: pd.DataFrame,
    planned_split_date,
    forecast_end_date,
    growth_mode="linear",
    top_n_cap=None  # Pass N here for winsorization. None means don't cap.
):
    """
    For each region:
      - Fit Prophet up to planned_split_date
      - Forecast for the entire history plus out to forecast_end_date
      - Merge Knowns, Prophet forecast, and ALL decomposition columns into output df
      - Return (1) full combined DataFrame (with decompositions), (2) model_dict mapping region -> (Prophet model, forecast)
    """
    results = []
    model_dict = {}
    planned_split_date = pd.to_datetime(planned_split_date)
    forecast_end_date = pd.to_datetime(forecast_end_date)
    min_date = pd.to_datetime(df['DATE'].min())

    for region in df['REGION'].unique():
        df_region = df[df['REGION'] == region].copy()
        df_train = df_region[df_region['DATE'] <= planned_split_date].copy()
        prophet_df = df_train[['DATE', 'KBD']].rename(columns={'DATE': 'ds', 'KBD': 'y'})
        # Cap outliers (winsorization)
        if top_n_cap is not None:
            prophet_df = cap_top_n_values(prophet_df, value_col='y', n=top_n_cap)

        prophet_df['floor'] = 0
        if growth_mode == "logistic":
            prophet_df['cap'] = max(df_train['KBD'].max(), 1)

        m = Prophet(
            growth=growth_mode,
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False
        )
        # m.add_seasonality(name='semiannual', period=26, fourier_order=15)
        m.fit(prophet_df)


        # Build full date range
        all_dates = pd.date_range(min_date, forecast_end_date, freq='W-FRI')
        future = pd.DataFrame({'ds': all_dates})
        future['floor'] = 0
        if growth_mode == "logistic":
            future['cap'] = prophet_df['cap'].iloc[0]
        forecast = m.predict(future)
        cap_value = prophet_df['y'].max()
        for col in ['yhat', 'yhat_lower', 'yhat_upper']:
            forecast[col] = forecast[col].clip(lower=0, upper=cap_value)

        # Identify all decomposition columns for merging
        decomp_cols = ['ds', 'yhat', 'yhat_lower', 'yhat_upper', 'trend']
        # Add any additional seasonality columns Prophet generated
        seasonals = [c for c in forecast.columns if c not in decomp_cols and c not in ['additive_terms', 'multiplicative_terms', 'cap', 'floor']]
        wanted_cols = decomp_cols + seasonals

        # Merge Knowns and decompositions
        df_merge = pd.merge(
            forecast[wanted_cols],
            df_region[['DATE', 'KBD']],
            left_on='ds', right_on='DATE', how='left'
        )
        df_merge['REGION'] = region
        df_merge['DATE'] = df_merge['ds']
        df_merge['forecast_type'] = np.where(df_merge['KBD'].notna(), 'known', 'forecast')

        results.append(df_merge)
        model_dict[region] = (m, forecast)

    df_out = pd.concat(results, ignore_index=True)
    df_out = df_out[df_out['ds'] <= forecast_end_date].copy()
    df_out = df_out.drop(columns=['ds'])
    cols = ['DATE'] + [col for col in df_out.columns if col != 'DATE']
    df_out = df_out[cols]

    return df_out.sort_values(['REGION', 'DATE']), model_dict


def forecast_utilization_by_region(
    df: pd.DataFrame,
    forecast_end_date,
    growth_mode="flat",
    top_n_cap=None
):
    """
    Forecast utilization (%) by region using Prophet.

    Parameters:
        df (pd.DataFrame): Must contain 'DATE', 'REGION', 'utilization'.
        forecast_end_date (str or pd.Timestamp): Final forecast date.
        growth_mode (str): Prophet growth type ('linear' or 'logistic').
        top_n_cap (int or None): Cap top N values (winsorization).

    Returns:
        df_out (pd.DataFrame): Forecast results with Prophet components.
        model_dict (dict): Region -> (Prophet model, forecast DataFrame)
    """
    df = df.copy()
    df['DATE'] = pd.to_datetime(df['DATE'])
    forecast_end_date = pd.to_datetime(forecast_end_date)
    min_date = df['DATE'].min()

    results = []
    model_dict = {}

    for region in df['REGION'].unique():
        df_region = df[df['REGION'] == region].copy()
        prophet_df = df_region[['DATE', 'utilization']].rename(columns={'DATE': 'ds', 'utilization': 'y'})

        if top_n_cap is not None:
            prophet_df = cap_top_n_values(prophet_df, value_col='y', n=top_n_cap)

        prophet_df['floor'] = 0
        if growth_mode == "logistic":
            prophet_df['cap'] = max(prophet_df['y'].max(), 1)

        m = Prophet(
            growth=growth_mode,
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False
        )
        m.add_seasonality(name='semiannual', period=26, fourier_order=10)
        m.fit(prophet_df)

        future_dates = pd.date_range(min_date, forecast_end_date, freq='W-FRI')
        future = pd.DataFrame({'ds': future_dates})
        future['floor'] = 0
        if growth_mode == "logistic":
            future['cap'] = prophet_df['cap'].iloc[0]

        forecast = m.predict(future)
        cap_value = prophet_df['y'].max()
        for col in ['yhat', 'yhat_lower', 'yhat_upper']:
            forecast[col] = forecast[col].clip(lower=0, upper=cap_value)

        decomp_cols = ['ds', 'yhat', 'yhat_lower', 'yhat_upper', 'trend']
        seasonals = [
            c for c in forecast.columns
            if c not in decomp_cols and c not in ['additive_terms', 'multiplicative_terms', 'cap', 'floor']
        ]
        wanted_cols = decomp_cols + seasonals

        df_merge = pd.merge(
            forecast[wanted_cols],
            df_region[['DATE', 'utilization']],
            left_on='ds', right_on='DATE', how='left'
        )
        df_merge['REGION'] = region
        df_merge['DATE'] = df_merge['ds']
        df_merge['forecast_type'] = np.where(df_merge['utilization'].notna(), 'known', 'forecast')

        results.append(df_merge)
        model_dict[region] = (m, forecast)

    df_out = pd.concat(results, ignore_index=True)
    df_out = df_out[df_out['ds'] <= forecast_end_date].copy()
    df_out.drop(columns=['ds'], inplace=True)
    df_out = df_out[['DATE'] + [col for col in df_out.columns if col != 'DATE']]
    return df_out.sort_values(['REGION', 'DATE']), model_dict

def cap_top_n_values(df, value_col='KBD', n=3):
    """
    Cap (winsorize) the highest n values in value_col to the (n+1)th highest value.
    Does not remove rows, just caps.
    """
    s = df[value_col].copy()
    # Find the (n+1)th highest value (unique values)
    s_sorted = s.sort_values(ascending=False)
    unique_sorted = s_sorted.unique()
    if len(unique_sorted) > n:
        cap_value = unique_sorted[n]
    else:
        # If fewer than n+1 unique values, use the lowest as cap (no capping needed)
        cap_value = unique_sorted[-1]
    capped = s.copy()
    capped[s > cap_value] = cap_value
    df_capped = df.copy()
    df_capped[value_col] = capped
    return df_capped
