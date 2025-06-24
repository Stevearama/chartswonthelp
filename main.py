
import pandas as pd
import numpy as np
import logging
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
warnings.filterwarnings("ignore", category=UserWarning, module="prophet")
warnings.filterwarnings("ignore", category=UserWarning, module="prophet_forecast")
import os

from prophet import Prophet
from datetime import date, timedelta, datetime

# Steve files imports
import outage_utils
import prophet_forecast
import charts
import bberg
import utilization
import webpage
import eia


# Constraints
OUTPUT_DIR = 'output'
os.makedirs(OUTPUT_DIR, exist_ok=True)
DATA_START_DATE = '2022-01-01'
DATA_END_DATE = '2025-12-31'
FORECAST_END_DATE = '2026-12-31'
planned_split_date = date.today() + timedelta(days=45)
unplanned_split_date = date.today() + timedelta(days=5)

# Countries
countries = {
    "USA": ["PADD1", "PADD2", "PADD3", "PADD4", "PADD5"],
    "Canada": ["Western Canada", "Central Canada", "Eastern Canada"]
}

GROWTH_MODE = 'flat'                        #linear, logistic, flat

def main():
# # ----------------------------------------------------------------------------------------------------------------------#
#     # Import IIR Outages from file, and convert to a weekly timeseries
    MODEL_REGIONS = [
        'PADD1', 'PADD2', 'PADD3', 'PADD4', 'PADD5', 'USA',
        'Western Canada', 'Central Canada', 'Eastern Canada', 'Canada',
        'Mexico',
    ]
    units = ["Atmospheric Distillation", "Condensate Splitter"] #, "Other Unit Type"]

    df_outages = outage_utils.import_outages('NthAmericaOutage.xlsx', units)
    df_IIR_summary_TS = outage_utils.build_outage_timeseries(
        df_outages,
        DATA_START_DATE,
        FORECAST_END_DATE,
        countries,
        regions=MODEL_REGIONS,
    )
    df_IIR_summary_TS = outage_utils.daily_to_weekly(df_IIR_summary_TS)
    df_IIR_summary_TS = outage_utils.round_numeric(df_IIR_summary_TS, 1)
    df_IIR_summary_TS.to_excel(os.path.join(OUTPUT_DIR, "IIR_summary_TS.xlsx"), index=False)

# # ----------------------------------------------------------------------------------------------------------------------#
#     # Split to planned outages.  And split to actual historical outages based on the split date
    df_IIR_planned = df_IIR_summary_TS.query('EVENT_TYPE == "Planned"').copy()
    # Split planned outages here, so that the forecast_planned_outage function doesn't need to do it.  This means the prophet model only gets the data  to use for forecasting.
    df_IIR_planned_historic = df_IIR_planned[df_IIR_planned['DATE'] < pd.to_datetime(planned_split_date)]
    df_IIR_planned_future = df_IIR_planned[df_IIR_planned['DATE'] >= pd.to_datetime(planned_split_date)]

    # Model Planned outage Forecast
    df_planned_forecast, model_dict = prophet_forecast.forecast_planned_outages(
        df_IIR_planned_historic,
       # planned_split_date, # no longer needed
        FORECAST_END_DATE,
        growth_mode=GROWTH_MODE,
        top_n_cap=5  # Removes the highest outages from the forecast model.
    )
    df_planned_forecast = outage_utils.round_numeric(df_planned_forecast, 0)
    df_planned_forecast = # add the df_IIR_planned_future back in, so we can see the existing planned outages

    charts.plot_forecast(df_planned_forecast, output_dir=OUTPUT_DIR, chart_prefix="Planned")
    charts.plot_prophet_decomposition(df_planned_forecast, output_dir=OUTPUT_DIR, chart_prefix="Planned Decomp")

# # ----------------------------------------------------------------------------------------------------------------------#
#     # Split to unplanned outages.  And split to actual historical outages based on the split date
#     df_IIR_summary_TS_unplanned = df_IIR_summary_TS.query('EVENT_TYPE == "Unplanned"').copy()
#
#
#     # Model Unplanned outage Forecast
#     df_unplanned_forecast, model_dict = prophet_forecast.forecast_planned_outages(
#         df_IIR_summary_TS_unplanned,
#         unplanned_split_date,
#         FORECAST_END_DATE,
#         growth_mode=GROWTH_MODE,
#         top_n_cap=5  # None means do not filter outliers
#     )
#     df_unplanned_forecast = outage_utils.round_numeric(df_unplanned_forecast, 0)
#     df_unplanned_forecast.to_excel(os.path.join(OUTPUT_DIR, "unplanned_outage_TS.xlsx"), index=False)
#     charts.plot_forecast(df_unplanned_forecast, output_dir=OUTPUT_DIR, chart_prefix="Unplanned")
#     charts.plot_prophet_decomposition(df_unplanned_forecast, output_dir=OUTPUT_DIR, chart_prefix="Unplanned Decomp")
#
# # ----------------------------------------------------------------------------------------------------------------------#
#     # Create total outages.  Historical planned and unplanned plus Forecast planned and unplanned.
#     # Planned
#     split_date = pd.to_datetime(planned_split_date)
#     df_IIR_summary_TS_planned_historic = df_IIR_summary_TS_planned[df_IIR_summary_TS_planned['DATE'] < split_date]
#     df_IIR_summary_TS_planned_historic = outage_utils.round_numeric(df_IIR_summary_TS_planned_historic, 0)
#     df_IIR_summary_TS_planned_historic = df_IIR_summary_TS_planned_historic.drop("EVENT_TYPE", axis=1)
#
#     # UnPlanned
#     split_date = pd.to_datetime(unplanned_split_date)
#     df_IIR_summary_TS_unplanned_historic = df_IIR_summary_TS_unplanned[df_IIR_summary_TS_unplanned['DATE'] < split_date]
#     df_IIR_summary_TS_unplanned_historic = outage_utils.round_numeric(df_IIR_summary_TS_unplanned_historic, 0)
#     df_IIR_summary_TS_unplanned_historic = df_IIR_summary_TS_unplanned_historic.drop("EVENT_TYPE", axis=1)
#
#     df_combined_historic = pd.concat([df_IIR_summary_TS_planned_historic, df_IIR_summary_TS_unplanned_historic]).groupby(['REGION', 'DATE'], as_index=False)['KBD'].sum()
#     df_combined_historic.to_excel(os.path.join(OUTPUT_DIR, "combined_outage_historic.xlsx"), index=False)
#
#     # Download bberg runs & create utilization
#     eia_runs_tickers = {
#         "DOEPCRIN Index": "USA", "DOEPCRP1 Index": "PADD1",
#         "DOEPCRP2 Index": "PADD2", "DOEPCRP3 Index": "PADD3",
#         "DOEPCRP4 Index": "PADD4", "DOEPCRP5 Index": "PADD5",
#     }
#     df_eia_runs = bberg.download_bloomberg(eia_runs_tickers, DATA_START_DATE)
#
#     # Calcuate IIR Capacity Timeseries
#     # capacity_cols = ['PLANT_NAME', 'UNIT_TYPE', 'OPERATOR', 'UNIT_STATE', 'U_STATUS', 'REGION', 'U_CAPACITY', 'CAP_UOM', 'SHUTDOWN', 'STARTUP']
#     # df_capacity = outage_utils.import_outages('NthAmericaUnit.xlsx', units, capacity_cols)
#     # df_capacity_TS = outage_utils.build_capacity_timeseries(
#     #     df_capacity,
#     #     DATA_START_DATE,
#     #     FORECAST_END_DATE,
#     #     countries,
#     #     regions=MODEL_REGIONS,
#     # )
#     #
#     # df_capacity_TS = outage_utils.daily_to_weekly(df_capacity_TS)
#     # df_capacity_TS.to_excel(os.path.join(OUTPUT_DIR, "capacity.xlsx"), index=False)
#     #
#     # pd.concat([df_planned_combined_simple, df_unplanned_combined_simple]).groupby(['REGION', 'DATE'], as_index=False)[
#     # 'KBD'].sum()
#
#
#
#     df_planned_forecast_simple = df_planned_forecast[
#         [col for col in ['REGION', 'DATE', 'yhat'] if col in df_planned_forecast.columns]].copy()
#     df_planned_forecast_simple = outage_utils.round_numeric(df_planned_forecast_simple, 0)
#     df_planned_forecast_simple = df_planned_forecast_simple[df_planned_forecast_simple["DATE"] >= split_date]
#     df_planned_forecast_simple = df_planned_forecast_simple.rename(columns={"yhat": "KBD"})
#     df_planned_combined_simple = pd.concat([df_IIR_summary_TS_planned_historic, df_planned_forecast_simple],
#                                            ignore_index=True)
#     df_planned_combined_simple.to_excel(os.path.join(OUTPUT_DIR, "planned_simple.xlsx"), index=False)
#     print('planned')
#     print(df_planned_combined_simple.tail())
#
#
#     df_unplanned_forecast_simple = df_unplanned_forecast[
#         [col for col in ['REGION', 'DATE', 'yhat'] if col in df_unplanned_forecast.columns]].copy()
#     df_unplanned_forecast_simple = outage_utils.round_numeric(df_unplanned_forecast_simple, 0)
#     df_unplanned_forecast_simple = df_unplanned_forecast_simple[df_unplanned_forecast_simple["DATE"] >= split_date]
#     df_unplanned_forecast_simple = df_unplanned_forecast_simple.rename(columns={"yhat": "KBD"})
#     df_unplanned_combined_simple = pd.concat([df_IIR_summary_TS_unplanned_historic, df_unplanned_forecast_simple],
#                                              ignore_index=True)
#     df_unplanned_combined_simple.to_excel(os.path.join(OUTPUT_DIR, "unplanned_simple.xlsx"), index=False)
#     print('unplanned')
#     print(df_unplanned_combined_simple.tail())
#
#     # This is the simple df showing historical and forecast outages.
#     df_total_simple = \
#     pd.concat([df_planned_combined_simple, df_unplanned_combined_simple]).groupby(['REGION', 'DATE'], as_index=False)[
#         'KBD'].sum()
#
# #----------------------------------------------------------------------------------------------------------------------#
#     # Capacities from IIR
#
#     capacity_cols = ['PLANT_NAME', 'UNIT_TYPE', 'OPERATOR', 'UNIT_STATE', 'U_STATUS', 'REGION', 'U_CAPACITY', 'CAP_UOM', 'SHUTDOWN', 'STARTUP']
#
#     df_capacity = outage_utils.import_outages('NthAmericaUnit.xlsx', units, capacity_cols)
#     df_capacity.to_excel(os.path.join(OUTPUT_DIR, "capacity.xlsx"), index=False)
#     df_capacity_TS = outage_utils.build_capacity_timeseries(
#         df_capacity,
#         DATA_START_DATE,
#         FORECAST_END_DATE,
#         countries,
#         regions=MODEL_REGIONS,
#     )
#     df_capacity_TS.to_excel(os.path.join(OUTPUT_DIR, "capacity_TS.xlsx"), index=False)
#
# #----------------------------------------------------------------------------------------------------------------------#
#     # Available Capacity
#
#     #
#     # df_available = outage_utils.available_capacity(df_total_forecast, df_capacity_TS, DATA_START_DATE, FORECAST_END_DATE, planned_split_date)
#     # df_available.to_excel(os.path.join(OUTPUT_DIR, "avail_capacity_TS.xlsx"), index=False)
#
# #----------------------------------------------------------------------------------------------------------------------#
#     # Download bberg runs & create utilization
#     # eia_runs_tickers = {
#     #     "DOEPCRIN Index": "USA", "DOEPCRP1 Index": "PADD1",
#     #     "DOEPCRP2 Index": "PADD2", "DOEPCRP3 Index": "PADD3",
#     #     "DOEPCRP4 Index": "PADD4", "DOEPCRP5 Index": "PADD5",
#     # }
#     # df_eia_runs = bberg.download_bloomberg(eia_runs_tickers, DATA_START_DATE)
#     # print(df_eia_runs.columns)
#     # print(df_eia_runs.head())
#     # df_eia_runs.to_excel(os.path.join(OUTPUT_DIR, "eia_runs_TS.xlsx"), index=False)
#     # df_ref_utilization = utilization.ref_utilization(df_eia_runs, df_available)
#     # df_ref_utilization.to_excel(os.path.join(OUTPUT_DIR, "ref_utilization_TS.xlsx"), index=False)
#
#     # historical_weekly_outages =
#
#
# #----------------------------------------------------------------------------------------------------------------------#
#     # Download bberg ref margins
#     ref_margin_tickers = {
#         "NANM0054 Index": "USGC Bakken Cracking",
#         "NANM00A2 Index": "USGC LLS Cracking",
#         "NANM00CC Index": "USGC Mars Coking",
#         "NANM007E Index": "USGC EF Cracking",
#         "NANM00DE Index": "USGC Maya Coking",
#         "NANM0120 Index": "USGC WCS Coking",
#         "NANM013E Index": "USGC Agb Cracking",
#         "NANV004A Index": "USAC Saharan Cracking",
#         "NANV0026 Index": "USAC Bakken",
#         "NANK0023 Index": "Midcon Bakken Cracking",
#         "NANK0029 Index": "Midcon Syn Cracking",
#         "NANK0041 Index": "Midcon WTI Cracking",
#         "NANK002F Index": "Midcon WCS Coking",
#         "NANU004F Index": "USWC ANS Coking",
#         "NANU0031 Index": "USWC Maya Coking",
#         "NANU003D Index": "USWC Oriente Coking",
#         "PNT1CM25 Index": "USWC Arab Light Coking",
#         "NANU002B Index": "USWC Arab Medium Coking",
#         "NANU0055 Index": "USWC Basrah Heavy Coking",
#         "NANU0037 Index": "USWC Napo Coking",
#         "NANW0039 Index": "NWE Agbami Cracking",
#         "NANW0100 Index": "NWE CPC Cracking",
#         "NANW0043 Index": "NWE Forties Cracking",
#         "NANW0049 Index": "NWE Johan Sverdrup Cracking",
#         "NANW0079 Index": "NWE Sarahan Cracking",
#         "NANW0085 Index": "NWE WTIM Cracking",
#         "NANW0055 Index": "NWE Arab Light Cracking",
#         "NANQ002A Index": "Med Abgami Cracking",
#         "NANQ007E Index": "Med Sarahan Cracking",
#         "NANQ0100 Index": "Med CPC Cracking",
#         "NANQ0054 Index": "Med Forties Cracking",
#         "NANQ005A Index": "Med Johan Svendrup Cracking",
#         "NANQ0066 Index": "Med Arab Light Cracking",
#         "NANX0039 Index": "SG Agbami Cracking",
#         "NANX0087 Index": "SG Arab Light Cracking",
#         "NANX0051 Index": "SG Cabinda Cracking",
#         "NANX0081 Index": "SG Kimanis Cracking",
#         "NANX00D5 Index": "SG WTIM Cracking",
#         "NANX00A5 Index": "SG Mars Cracking",
#         "NANX00C3 Index": "SG Sarahan Cracking"
#     }
#
#
#     df_ref_margins = bberg.download_bloomberg(ref_margin_tickers, DATA_START_DATE)
#     df_ref_margins["REFINERY_REGION"] = df_ref_margins["REGION"].str.split().str[0]
#     df_ref_margins["REGION"] = df_ref_margins["REGION"].str.split(n=1).str[1].fillna("").str.strip()
#     df_ref_margins.to_excel(os.path.join(OUTPUT_DIR, "ref_margins_TS.xlsx"), index=False)
#     charts.plot_refinery_margins(df_ref_margins, output_dir=OUTPUT_DIR, chart_prefix="Margins")
#     charts.plot_boxplots(df_ref_margins, output_dir=OUTPUT_DIR, chart_prefix="Margin_boxplot")


    eia_crude_page_tickers = {
        "DOESCRUD Index": "US Crude Commercial Stocks. kb",
        "DOESCROK Index": "Cushing Stocks. kb",
        "DOESSPR Index": "SPR Crude Stocks. kb",
        "DOETCRUD Index": "US Crude Production. kbd",
        "DOEICISP Index": "US Crude Imports (inc SPR). kbd",
        "DEPWIMCA Index": "US Crude Imports From Canada. kbd",
        "DOEPCRIN Index": "US Refinery Crude Runs. kbd",
        "DOEBCEXP Index": "US Crude Export. kbd",
        "DOESUNCR Index": "US Crude Supply Adjustment",
        "DOESCRU2 Index": "P2 Crude Stocks. kb",
        "DOEPCRP2 Index": "P2 Refinery Crude Runs. kbd",
        "DOESCRU3 Index": "P3 Crude Stocks. kb",
        "DOEPCRP3 Index": "P3 Refinery Crude Runs. kbd",
        "DOESCRU5 Index": "P5 Crude Stocks. kb",
        "DOEPCRP5 Index": "P5 Refinery Crude Runs. kbd",
        "DOEINICR Index": "US Crude Net Imports. kbd",
        "DOESTCRD Index": "US Crude Stocks Inc SPR. kb",
        "DOETTRCO Index": "US NGL Transfers to Crude. kbd"
    }
    df_eia_crude_page = bberg.download_bloomberg(eia_crude_page_tickers, '2020-01-01')
    df_eia_crude_page = eia.add_eia_crude_calcs(df_eia_crude_page)
    df_eia_crude_page.to_excel(os.path.join(OUTPUT_DIR, "eia_crude_page.xlsx"), index=False)


    chart_dict_tabs = {
        "Margins": {
            "USGC": [
                ["Margins_USGC.html", "Margin_boxplot_USGC.html", "EMPTY"],
                ["Margins_USGC.html", "Margin_boxplot_USGC.html"]
                ],

            "US MidCon": [
                ["Margins_Midcon.html", "EMPTY", "Margin_boxplot_Midcon.html"]
                ],

            "USWC": [
                ["EMPTY", "Margins_USAC.html", "Margin_boxplot_USAC.html"]
                ],
        },
        "Outages": {
            "PADD 1": [
                ["Planned_PADD1.html", "Planned Decomp_PADD1.html", "EMPTY"],
                ["Unplanned_PADD1.html", "Unplanned Decomp_PADD1.html", "EMPTY"],
                ["Total_PADD1.html", "Total Decomp_PADD1.html", "EMPTY"]
                ],


            "PADD 2": [
                ["Planned_PADD2.html", "Planned Decomp_PADD2.html", "EMPTY"],
                ["Unplanned_PADD2.html", "Unplanned Decomp_PADD2.html", "EMPTY"],
                ["Total_PADD2.html", "EMPTY", "Total Decomp_PADD2.html"]
                ],
        },
        "Weekly Stats": {
            "Crude": [
                ["EIA_US_Crude_Commercial_Stocks.html", "EIA_Cushing_Stocks.html", "EIA_P2_Crude_Days_Cover.html", "EIA_US_Crude_Days_Cover.html"],
                ["EIA_US_Crude_Gross_Supply_-_Gross_Demand.html", "EIA_US_Crude_Net_Imports.html", "EIA_US_Crude_Stock_Build.html", "EIA_US_Crude_Balance_Error.html"],
                ["EIA_US_Crude_Production.html", "EIA_US_Crude_Imports_From_Canada.html", "EIA_US_Crude_Imports_From_Non-Canada.html", "US Crude Production PLUS Imports (Total Supply).html"],
                ["EIA_US_Refinery_Crude_Runs.html", "EIA_US_Crude_Export.html", "EIA_US_Crude_Net_Imports.html", "US Crude Runs PLUS Exports (Total Demand).html"],
            ],
        },
    }


    charts.chart_eia(df_eia_crude_page, output_dir=OUTPUT_DIR)
    webpage.make_webpage(chart_dict_tabs, "The Charts Wont Help", output_dir="output", output_filename="dashboard.html")


if __name__ == "__main__":
    main()
