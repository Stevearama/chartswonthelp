
# outage_utilization.py
import pandas as pd
import numpy as np



def ref_utilization(df_eia_runs: pd.DataFrame, df_available: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate utilization as EIA_RUNS / AVAILABLE_CAPACITY for each EIA date and region.

    - Only uses dates in df_eia_runs (actuals)
    - For each EIA row, finds the most recent available capacity (≤ EIA date, max 2-day gap)
    - Logs regions missing from available
    - Logs date mismatches > 2 days

    Returns:
        DataFrame with ['DATE', 'REGION', 'utilization', 'available_date']
    """
    import numpy as np

    df_eia = df_eia_runs.copy()
    df_avail = df_available.copy()

    df_eia['DATE'] = pd.to_datetime(df_eia['DATE'])
    df_avail['DATE'] = pd.to_datetime(df_avail['DATE'])

    required_eia_cols = {'DATE', 'REGION', 'VALUE'}
    required_avail_cols = {'DATE', 'REGION', 'available_capacity'}
    if not required_eia_cols.issubset(df_eia.columns):
        raise ValueError(f"df_eia_runs must contain columns: {required_eia_cols}")
    if not required_avail_cols.issubset(df_avail.columns):
        raise ValueError(f"df_available must contain columns: {required_avail_cols}")

    # Find regions in df_available not in df_eia_runs
    regions_eia = set(df_eia['REGION'].unique())
    regions_avail = set(df_avail['REGION'].unique())
    unmatched_regions = sorted(regions_avail - regions_eia)

    if unmatched_regions:
        print("⚠️ The following regions exist in df_available but not in df_eia_runs and will be skipped:")
        for region in unmatched_regions:
            print(f"  - {region}")

    # Drop those regions from df_available
    df_avail = df_avail[df_avail['REGION'].isin(regions_eia)]

    df_avail_sorted = df_avail.sort_values('DATE')

    aligned_rows = []
    mismatches = []

    for _, row in df_eia.iterrows():
        region = row['REGION']
        eia_date = row['DATE']

        candidates = df_avail_sorted[
            (df_avail_sorted['REGION'] == region) &
            (df_avail_sorted['DATE'] <= eia_date)
        ]

        if candidates.empty:
            raise ValueError(f"No available capacity found on or before {eia_date.date()} for region '{region}'")

        nearest = candidates.sort_values('DATE', ascending=False).iloc[0]
        gap_days = (eia_date - nearest['DATE']).days

        if gap_days > 2:
            mismatches.append((region, eia_date.date(), nearest['DATE'].date(), gap_days))

        aligned_rows.append({
            'DATE': eia_date,
            'REGION': region,
            'VALUE': row['VALUE'],
            'available_capacity': nearest['available_capacity'],
            'available_date': nearest['DATE']
        })

    if mismatches:
        print("⚠️ Date mismatches (gap > 2 days) between EIA actual and available capacity:")
        for region, eia_date, avail_date, gap in mismatches:
            print(f"  - REGION: {region}, EIA_DATE: {eia_date}, AVAILABLE_DATE_USED: {avail_date}, GAP_DAYS: {gap}")

    df_result = pd.DataFrame(aligned_rows)

    df_result['utilization'] = np.where(
        df_result['available_capacity'] > 0,
        df_result['VALUE'] / df_result['available_capacity'],
        np.nan
    )

    df_result['utilization'] = df_result['utilization'].clip(upper=2)

    return df_result[['DATE', 'REGION', 'utilization', 'available_date']]