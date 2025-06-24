# outage_utils.py
import pandas as pd
import numpy as np
import logging


def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize legacy column names."""
    rename_map = {
        "UTYPE_DESC": "UNIT_TYPE",
        "PADD_REG": "REGION",
        "PAD_DIST": "REGION"
    }
    return df.rename(columns=rename_map)

def standardize_region_names(df: pd.DataFrame) -> pd.DataFrame:
    """Rename roman numeral PADDs to PADD1, PADD2, etc."""
    rename_map = {
        "I": "PADD1", "II": "PADD2", "III": "PADD3", "IV": "PADD4", "V": "PADD5"
    }
    df = df.copy()
    df["REGION"] = df["REGION"].apply(lambda x: rename_map.get(x, x))
    return df

def convert_to_kbd(df: pd.DataFrame) -> pd.DataFrame:
    """Convert capacity columns to KBD using recognized units."""
    df = df.copy()
    # df["CAP_UOM"] = (
    #     df["CAP_UOM"]
    #     .astype(str)
    #     .str.strip()
    #     .str.upper()
    #     .str.replace(r"\s+", "", regex=True)
    # )
    df["CAP_UOM"] = (
        df["CAP_UOM"]
        .astype(str)
        .str.upper()
        .str.replace(r"[^A-Z/]", "", regex=True)  # Clean up stray characters
        .str.strip()
    )
    cap_col = None
    if "U_CAPACITY" in df.columns:
        cap_col = "U_CAPACITY"
    elif "CAP_OFFLINE" in df.columns:
        cap_col = "CAP_OFFLINE"
    else:
        raise ValueError("No recognized capacity column (U_CAPACITY or CAP_OFFLINE) found.")
    df["KBD"] = np.nan
    df.loc[df["CAP_UOM"] == "BBL/D", "KBD"] = df[cap_col] / 1000
    df.loc[df["CAP_UOM"] == "T/D", "KBD"] = df[cap_col] * 7.2
    # unknown_units = df.loc[df["KBD"].isna(), "CAP_UOM"].unique().tolist()
    # # if df["KBD"].isna().any():
    # #     logging.warning(f"Some KBD values could not be calculated. Unknown CAP_UOM types: {unknown_units}")
    # if df["KBD"].isna().any():
    #     problem_rows = df[df["KBD"].isna()][["UNIT_TYPE", "CAP_UOM"]].drop_duplicates()
    #     logging.warning(f"⚠️ Could not convert some KBD values due to unknown CAP_UOMs:\n{problem_rows}")

    return df

def filter_columns(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """Return only columns that exist in the DataFrame."""
    cols_in_df = [col for col in columns if col in df.columns]
    return df[cols_in_df]

def filter_units(df: pd.DataFrame, units: list) -> pd.DataFrame:
    """Return only selected units."""
    return df[df["UNIT_TYPE"].isin(units)]

def create_country_totals(
    df: pd.DataFrame,
    value_cols: list,
    countries: dict
) -> pd.DataFrame:
    """
    Appends a total row for each country in 'countries' as the sum of specified regions.

    Parameters:
        df: DataFrame with at least columns ["DATE", "REGION", ...] and value_cols
        value_cols: list of column names to sum, e.g. ["KBD"]
        countries: dict like {'USA': [list of regions], ...}

    Returns:
        DataFrame with appended country total rows.
    """
    if countries is None:
        raise ValueError("You must provide a countries dictionary.")

    df = df.copy()
    group_cols = ["DATE"]
    if "EVENT_TYPE" in df.columns:
        group_cols.append("EVENT_TYPE")

    total_rows = []
    for country, region_list in countries.items():
        df_subset = df[df["REGION"].isin(region_list)]
        if df_subset.empty:
            continue  # skip if no data for these regions
        total = df_subset.groupby(group_cols)[value_cols].sum().reset_index()
        total["REGION"] = country
        total_rows.append(total)

    # Concatenate original df and all country totals
    if total_rows:
        df_total = pd.concat([df] + total_rows, ignore_index=True)
    else:
        df_total = df

    return df_total

def import_outages(
    file: str,
    units: list,
    cols: list = None
) -> pd.DataFrame:
    """
    Imports and standardizes an outage Excel file.

    Parameters:
        file: path to Excel file.
        units: list of unit types to keep (e.g., ["Atmospheric Distillation", ...])
        cols: columns to keep. Default uses standard outage columns.

    Returns:
        Cleaned DataFrame ready for timeseries expansion.
    """
    if cols is None:
        cols = [
            "EVENT_ID", "UNIT_NAME", "UNIT_TYPE", "UNIT_ID", "PLANT_ID", "PLANT_NAME", "REGION",
            "U_STATUS", "CAP_OFFLINE", "CAP_UOM", "START_DATE", "END_DATE", "EVENT_TYPE"
        ]

    df = pd.read_excel(file)
    df = standardize_column_names(df)
    df = filter_units(df, units)
    df = filter_columns(df, cols)
    df = convert_to_kbd(df)
    df = standardize_region_names(df)
    return df


def build_capacity_timeseries(
    df: pd.DataFrame,
    data_start_date: str,
    #data_end_date: str,
    forecast_end_date: str,
    countries: dict,
    regions: list = None
) -> pd.DataFrame:
    """
    Builds daily capacity timeseries by REGION.

    - 'Operational' units are included from STARTUP (or DATA_START_DATE).
    - 'Mothballed', 'Closed', 'Removed', 'Shuttered' units are included until SHUTDOWN (or DATA_START_DATE).
    - 'On Hold' and 'Cancelled' units are excluded.

    Parameters:
        df: Input DataFrame with standardized and converted capacity data.
        data_start_date: Earliest date for the time series.
        data_end_date: Latest date for the time series.
        countries: Dict of country totals to add.
        regions: Optional list of regions to filter.

    Returns:
        DataFrame with ['DATE', 'REGION', 'KBD']
    """
    start = pd.to_datetime(data_start_date)
    #end = pd.to_datetime(data_end_date)
    end = pd.to_datetime(forecast_end_date)
    df = df.copy()

    if regions is not None:
        df = df[df["REGION"].isin(regions)]

    # Standardize date fields
    df["STARTUP"] = pd.to_datetime(df["STARTUP"], errors="coerce")
    df["SHUTDOWN"] = pd.to_datetime(df["SHUTDOWN"], errors="coerce")

    valid_statuses = {
        "Operational": "start",
        "Mothballed": "end",
        "Closed": "end",
        "Removed": "end",
        "Shuttered": "end",
    }

    records = []

    for _, row in df.iterrows():
        status = row["U_STATUS"]
        if status not in valid_statuses:
            continue

        kbd = row["KBD"]
        region = row["REGION"]

        if valid_statuses[status] == "start":
            s = row["STARTUP"] if pd.notna(row["STARTUP"]) else start
            s = max(s, start)
            e = end
        else:
            s = start
            e = row["SHUTDOWN"] if pd.notna(row["SHUTDOWN"]) else start
            e = min(e, end)

        if s > e:
            continue

        for date in pd.date_range(s, e, freq="D"):
            records.append({
                "DATE": date,
                "REGION": region,
                "KBD": kbd
            })

    df_timeseries = pd.DataFrame(records)

    # Group daily capacity by REGION
    df_grouped = (
        df_timeseries
        .groupby(["DATE", "REGION"])["KBD"]
        .sum()
        .reset_index()
    )

    # Fill out full grid
    all_dates = pd.date_range(start=start, end=end, freq="D")
    all_regions = df["REGION"].dropna().unique()
    full_index = pd.MultiIndex.from_product([all_dates, all_regions], names=["DATE", "REGION"])
    df_full = pd.DataFrame(index=full_index).reset_index()

    df_merged = pd.merge(df_full, df_grouped, on=["DATE", "REGION"], how="left")
    df_merged["KBD"] = df_merged["KBD"].fillna(0)

    # Append country-level totals
    df_merged = create_country_totals(df_merged, value_cols=["KBD"], countries=countries)

    return df_merged.sort_values(["REGION", "DATE"])

def build_outage_timeseries(
    outages: pd.DataFrame,
    data_start_date: str,
    #data_end_date: str,
    forecast_end_date: str,
    countries: dict,
    regions: list = None,  # <--- add this!
) -> pd.DataFrame:
    """
    Expands outage records to a daily timeseries, fills missing dates/regions/types with zeros,
    and appends country-level totals.

    Parameters:
        outages: The raw outages DataFrame.
        data_start_date: Start date for timeseries, e.g. '2022-01-01'.
        data_end_date: End date for timeseries, e.g. '2025-12-31'.
        countries: Dict mapping country names to lists of region names.

    Returns:
        Complete daily timeseries DataFrame including country totals.
    """
    # Ensure date columns are datetime
    start = pd.to_datetime(data_start_date)
    #end = pd.to_datetime(data_end_date)
    end = pd.to_datetime(forecast_end_date)
    df = outages.copy()
    if regions is not None:
        df = df[df["REGION"].isin(regions)]
    df["START_DATE"] = pd.to_datetime(df["START_DATE"], errors="coerce")
    df["END_DATE"] = pd.to_datetime(df["END_DATE"], errors="coerce")

    # Expand each outage to all dates it covers
    records = []
    for _, row in df.iterrows():
        s = row["START_DATE"]
        e = row["END_DATE"]
        if pd.isna(s) or s > end:
            continue
        if pd.isna(e):
            e = end
        s = max(s, start)
        e = min(e, end)
        if s > e:
            continue
        for date in pd.date_range(s, e, freq="D"):
            records.append({
                "DATE": date,
                "REGION": row["REGION"],
                "KBD": row["KBD"],
                "EVENT_TYPE": row["EVENT_TYPE"]
            })
    df_timeseries = pd.DataFrame(records)

    # Group by date/region/event type, sum KBD
    df_grouped = (
        df_timeseries
        .groupby(["DATE", "REGION", "EVENT_TYPE"])["KBD"]
        .sum()
        .reset_index()
    )

    # Create complete index for all date/region/event type combinations
    all_dates = pd.date_range(start=start, end=end, freq="D")
    all_regions = df["REGION"].dropna().unique()
    all_types = df["EVENT_TYPE"].dropna().unique()
    full_index = pd.MultiIndex.from_product(
        [all_dates, all_regions, all_types],
        names=["DATE", "REGION", "EVENT_TYPE"]
    )
    df_full = pd.DataFrame(index=full_index).reset_index()

    # Left join actual data, fill missing with 0
    df_merged = pd.merge(
        df_full, df_grouped,
        on=["DATE", "REGION", "EVENT_TYPE"],
        how="left"
    )
    df_merged["KBD"] = df_merged["KBD"].fillna(0)

    # Append country-level totals
    df_merged = create_country_totals(df_merged, value_cols=["KBD"], countries=countries)

    # Sort for readability
    return df_merged.sort_values(["REGION", "DATE", "EVENT_TYPE"])

def daily_to_weekly(df):
    """
    Aggregates a daily DataFrame to weekly, using mean KBD for each week.
    Groups by all columns except 'KBD' and 'DATE', plus the week-ending Friday.
    """
    df = df.copy()
    df['DATE'] = pd.to_datetime(df['DATE'])

    # Always drop WEEK if it exists before creating it
    if 'WEEK' in df.columns:
        df = df.drop(columns=['WEEK'])

    # Add new WEEK column
    df['WEEK'] = df['DATE'] + pd.offsets.Week(weekday=4)

    # Make sure you group by 'WEEK', not 'WEEK' string or other variants
    cols_to_group = [c for c in df.columns if c not in ['KBD', 'DATE']]
    # Remove duplicates in grouping columns (just in case)
    cols_to_group = list(dict.fromkeys(cols_to_group))
    # Ensure 'WEEK' is only present once
    if 'WEEK' not in cols_to_group:
        cols_to_group.append('WEEK')

    df_weekly = (
        df.groupby(cols_to_group, as_index=False)
          .agg({'KBD': 'mean'})
    )
    # Rename WEEK to DATE (for output)
    if 'WEEK' in df_weekly.columns:
        df_weekly = df_weekly.rename(columns={'WEEK': 'DATE'})
    return df_weekly

def round_numeric(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """
    Returns a copy of df with all numeric columns rounded to n decimal places.
    Non-numeric columns are unchanged.

    Parameters:
        df (pd.DataFrame): Input DataFrame.
        n (int): Number of decimal places.

    Returns:
        pd.DataFrame: DataFrame with numeric columns rounded.
    """
    df_rounded = df.copy()
    numeric_cols = df_rounded.select_dtypes(include="number").columns
    df_rounded[numeric_cols] = df_rounded[numeric_cols].round(n)
    return df_rounded

def calculate_total_outages(
    df_planned: pd.DataFrame,
    df_unplanned: pd.DataFrame,
    unplanned_split_date,
    planned_split_date,
    region_col='REGION'
) -> pd.DataFrame:
    """
    Calculate total outages by region, using split logic for KBD and summing other numeric columns.

    Args:
        df_planned: DataFrame with ['DATE', region_col, ...]
        df_unplanned: DataFrame with ['DATE', region_col, ...]
        unplanned_split_date: pd.Timestamp or str
        planned_split_date: pd.Timestamp or str
        region_col: str, column name for the region/group (default 'REGION')

    Returns:
        DataFrame with ['DATE', region_col, ...] where all numeric columns except KBD are summed,
        and KBD follows the split logic.
    """

    # Prepare DataFrames
    df_planned = df_planned.copy()
    df_unplanned = df_unplanned.copy()
    df_planned['DATE'] = pd.to_datetime(df_planned['DATE'])
    df_unplanned['DATE'] = pd.to_datetime(df_unplanned['DATE'])
    df_planned[region_col] = df_planned[region_col].astype(str)
    df_unplanned[region_col] = df_unplanned[region_col].astype(str)

    # Find all numeric columns except KBD
    numeric_cols = list(set(df_planned.select_dtypes(include='number').columns)
                        | set(df_unplanned.select_dtypes(include='number').columns))
    if 'KBD' in numeric_cols:
        numeric_cols.remove('KBD')

    # Merge
    df = pd.merge(
        df_planned, df_unplanned,
        on=['DATE', region_col], how='outer',
        suffixes=('_planned', '_unplanned')
    )

    # Fill NaNs with zero for all relevant columns
    for col in ['KBD_planned', 'KBD_unplanned', 'yhat_planned', 'yhat_unplanned']:
        if col not in df:
            df[col] = 0
        df[col] = df[col].fillna(0)
    for col in numeric_cols:
        for which in ['_planned', '_unplanned']:
            name = col + which
            if name not in df:
                df[name] = 0
            df[name] = df[name].fillna(0)

    # Split date handling
    unplanned_split = pd.to_datetime(unplanned_split_date)
    planned_split = pd.to_datetime(planned_split_date)

    # Calculate total KBD
    def calc_kbd(row):
        if row['DATE'] < unplanned_split:
            return row['KBD_planned'] + row['KBD_unplanned']
        elif row['DATE'] < planned_split:
            return row['KBD_planned'] + row['yhat_unplanned']
        else:
            return max(row['KBD_planned'], row['yhat_planned']) + row['yhat_unplanned']

    result = pd.DataFrame()
    result['DATE'] = df['DATE']
    result[region_col] = df[region_col]
    result['KBD1'] = df.apply(calc_kbd, axis=1)

    # For all other numeric columns, sum planned + unplanned
    for col in numeric_cols:
        planned_col = col + '_planned'
        unplanned_col = col + '_unplanned'
        result[col] = df[planned_col] + df[unplanned_col]

    # Optional: sort
    result = result.sort_values([region_col, 'DATE']).reset_index(drop=True)
    return result

def sum_outage_forecasts(df_planned, df_unplanned, region_col="REGION"):
    """
    REDO THIS FUNCTION
    For each DATE/REGION, sum all numeric forecast columns from planned and unplanned DataFrames.
    - If either forecast_type is 'known', output 'known', else 'forecast'.
    - Output columns: DATE, REGION, [summed columns], forecast_type
    """
    # Drop non-numeric columns except for key ones
    key_cols = ['DATE', region_col, 'forecast_type']
    # Get numeric columns to sum
    num_cols = df_planned.select_dtypes(include='number').columns.union(
        df_unplanned.select_dtypes(include='number').columns
    )
    # Always include key columns
    df1 = df_planned[key_cols + [col for col in num_cols if col in df_planned.columns]].copy()
    df2 = df_unplanned[key_cols + [col for col in num_cols if col in df_unplanned.columns]].copy()
    df1['DATE'] = pd.to_datetime(df1['DATE'])
    df2['DATE'] = pd.to_datetime(df2['DATE'])

    merged = pd.merge(
        df1, df2,
        on=['DATE', region_col],
        how='outer',
        suffixes=('_planned', '_unplanned')
    )

    # Sum all numeric columns
    out = merged[['DATE', region_col]].copy()
    for col in num_cols:
        p_col = f"{col}_planned"
        u_col = f"{col}_unplanned"
        out[col] = merged.get(p_col, 0).fillna(0) + merged.get(u_col, 0).fillna(0)

    # Forecast type logic
    def choose_type(row):
        if (row.get('forecast_type_planned') == 'known') or (row.get('forecast_type_unplanned') == 'known'):
            return 'known'
        return 'forecast'

    out['forecast_type'] = merged.apply(choose_type, axis=1)
    out = out.sort_values([region_col, 'DATE']).reset_index(drop=True)
    return out


def available_capacity(
        df_total_forecast: pd.DataFrame,
        df_capacity_TS: pd.DataFrame,
        data_start_date: str,
        forecast_end_date: str,
        planned_split_date
) -> pd.DataFrame:
    """
    Calculate available capacity per region as:
      - capacity KBD - total outage KBD (before planned_split_date)
      - capacity KBD - max(total KBD, yhat) (after planned_split_date)

    Parameters:
        df_total_forecast: DataFrame with ['DATE', 'REGION', 'KBD', 'yhat'] columns
        df_capacity_TS: DataFrame with ['DATE', 'REGION', 'KBD'] representing capacity
        data_start_date: str start date (e.g., '2022-01-01')
        forecast_end_date: str end date
        planned_split_date: date after which yhat is considered

    Returns:
        DataFrame with ['DATE', 'REGION', 'available_capacity']
    """
    df_total = df_total_forecast.copy()
    df_capacity = df_capacity_TS.copy()

    df_total['DATE'] = pd.to_datetime(df_total['DATE'])
    df_capacity['DATE'] = pd.to_datetime(df_capacity['DATE'])
    planned_split_date = pd.to_datetime(planned_split_date)

    # Merge the two
    merged = pd.merge(
        df_capacity,
        df_total[['DATE', 'REGION', 'KBD', 'yhat']],
        on=['DATE', 'REGION'],
        how='left',
        suffixes=('_capacity', '_outage')
    )

    # Replace missing KBD or yhat with 0
    merged['KBD_outage'] = merged['KBD_outage'].fillna(0)
    merged['yhat'] = merged['yhat'].fillna(0)

    # Calculate available capacity
    merged['available_capacity'] = np.where(
        merged['DATE'] <= planned_split_date,
        merged['KBD_capacity'] - merged['KBD_outage'],
        merged['KBD_capacity'] - merged[['KBD_outage', 'yhat']].max(axis=1)
    )

    # Clip to zero (no negative available capacity)
    merged['available_capacity'] = merged['available_capacity'].clip(lower=0)

    return merged[['DATE', 'REGION', 'available_capacity']]



