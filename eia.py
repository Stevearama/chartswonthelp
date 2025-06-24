import pandas as pd

def add_eia_crude_calcs(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Pivot to wide format for arithmetic
    df_wide = df.pivot(index="DATE", columns="REGION", values="VALUE")

    # --- Calculations (modular, extensible) ---
    df_wide["US Crude Imports From Non-Canada. kbd"] = (
        df_wide["US Crude Imports (inc SPR). kbd"] - df_wide["US Crude Imports From Canada. kbd"]
    )

    df_wide["US Gross Crude Supply. kbd"] = (
        df_wide["US Crude Production. kbd"] + df_wide["US Crude Imports (inc SPR). kbd"] + df_wide["US NGL Transfers to Crude. kbd"]
    )

    df_wide["US Gross Crude Demand. kbd"] = (
        df_wide["US Refinery Crude Runs. kbd"] + df_wide["US Crude Export. kbd"]
    )

    df_wide["US Crude Gross Supply - Gross Demand. kbd"] = (
        df_wide["US Gross Crude Supply. kbd"] - df_wide["US Gross Crude Demand. kbd"]
    )

    # US Crude Stock Build: Weekly change in stocks (use diff)
    df_wide["US Crude Stock Build. kb"] = df_wide["US Crude Stocks Inc SPR. kb"].diff()


    df_wide["US Crude Balance Error. kbd"] = (
        df_wide["US Gross Crude Supply. kbd"] - df_wide["US Gross Crude Demand. kbd"] - (df_wide["US Crude Stock Build. kb"] / 7)
    ).round(0)

    df_wide["US Crude Days Cover"] = (
        df_wide["US Crude Stocks Inc SPR. kb"] / df_wide["US Refinery Crude Runs. kbd"]
    ).round(1)

    df_wide["P2 Crude Days Cover"] = (
        df_wide["P2 Crude Stocks. kb"] / df_wide["P2 Refinery Crude Runs. kbd"]
    ).round(1)

    df_wide["P3 Crude Days Cover"] = (
        df_wide["P3 Crude Stocks. kb"] / df_wide["P3 Refinery Crude Runs. kbd"]
    ).round(1)

    df_wide["P5 Crude Days Cover"] = (
        df_wide["P5 Crude Stocks. kb"] / df_wide["P5 Refinery Crude Runs. kbd"]
    ).round(1)

    # List of derived columns to melt back
    derived_cols = [
        "US Crude Imports From Non-Canada. kbd",
        "US Gross Crude Supply. kbd",
        "US Gross Crude Demand. kbd",
        "US Crude Gross Supply - Gross Demand. kbd",
        "US Crude Stock Build. kb",
        "US Crude Balance Error. kbd",
        "US Crude Days Cover",
        "P2 Crude Days Cover",
        "P3 Crude Days Cover",
        "P5 Crude Days Cover",
    ]

    # Melt to long format
    df_new = df_wide[derived_cols].reset_index().melt(
        id_vars="DATE", var_name="REGION", value_name="VALUE"
    )

    # Combine with original and return
    df_combined = pd.concat([df.drop(columns=["Ticker"], errors="ignore"), df_new], ignore_index=True)
    return df_combined
