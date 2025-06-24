# # # # charts.py
import os
import pandas as pd
from pyecharts import options as opts
from pyecharts.commons.utils import JsCode
import datetime
import calendar
from pyecharts.charts import Boxplot, Scatter, Line
import re


CHART_WIDTH = 800
CHART_HEIGHT = int(CHART_WIDTH * 10 / 16)
CHART_WIDTH_STR = f"{CHART_WIDTH}px"
CHART_HEIGHT_STR = f"{CHART_HEIGHT}px"
PYECHARTS_THEME = 'default'


def plot_forecast(df, output_dir="output", value_col="KBD", chart_prefix="Planned"):
    os.makedirs(output_dir, exist_ok=True)
    df['DATE'] = pd.to_datetime(df['DATE'])

    formatter_js = JsCode(
        "function(params){"
        "var out = params[0].name+'<br/>';"
        "params.forEach(function(item){"
        "if(item.seriesName==='Known'||item.seriesName==='Forecast'){"
        "out+=item.marker+item.seriesName+': '+item.value+'<br/>';}"
        "});"
        "return out;"
        "}"
    )
    empty_tooltip_js = JsCode("function(){return '';}")  # Not used, here for reference
    date_only_tooltip_js = JsCode("function(params){return params[0].name;}")

    today = pd.Timestamp(datetime.date.today())

    for region in df["REGION"].unique():
        df_r = df[df["REGION"] == region].copy()
        x_data = df_r["DATE"].dt.strftime("%Y-%m-%d").tolist()
        x_dates = pd.to_datetime(x_data)
        # Snap to latest Friday ≤ today, or earliest in series if today < all
        fridays_before_today = x_dates[x_dates <= today]
        if not fridays_before_today.empty:
            markline_date = fridays_before_today.max()
        else:
            markline_date = x_dates.min()
        markline_str = markline_date.strftime("%Y-%m-%d")

        # Known
        if "forecast_type" in df_r.columns:
            known = df_r[df_r["forecast_type"] == "known"]
            y_known = known.set_index("DATE")[value_col].reindex(df_r["DATE"]).tolist()
        else:
            y_known = [None] * len(x_data)

        # Prophet forecast and range
        yhat = df_r["yhat"].tolist()
        yhat_lower = df_r["yhat_lower"].tolist()
        yhat_upper = df_r["yhat_upper"].tolist()
        range_height = [u - l for u, l in zip(yhat_upper, yhat_lower)]

        # Mark line for (snapped) today's date
        markline = opts.MarkLineOpts(
            symbol=['none', 'none'],
            data=[opts.MarkLineItem(x=markline_str, name="Today")],
            linestyle_opts=opts.LineStyleOpts(
                color="#2ca02c",  # Green
                width=0.75,
                type_="dashed",
                opacity=1
            ),
            label_opts=opts.LabelOpts(
                formatter="{b}",
                position="insideTop"
            )
        )

        line = (
            Line(init_opts=opts.InitOpts(width=CHART_WIDTH_STR, height=CHART_HEIGHT_STR, renderer="svg", theme=PYECHARTS_THEME))
            .add_xaxis(x_data)
            .add_yaxis("Forecast", yhat, is_symbol_show=False, color="#1f77b4",
                       linestyle_opts=opts.LineStyleOpts(width=1.5))
            .add_yaxis("Known", y_known, is_symbol_show=False, color="#c0392b",
                       linestyle_opts=opts.LineStyleOpts(width=1.5))
            # Range Lower (not in legend)
            .add_yaxis("", yhat_lower, is_symbol_show=False, color="rgba(0,0,0,0)",
                       linestyle_opts=opts.LineStyleOpts(width=0),
                       stack="forecast_range", label_opts=opts.LabelOpts(is_show=False))
            # Forecast Range (not in legend)
            .add_yaxis("", range_height, is_symbol_show=False,
                       areastyle_opts=opts.AreaStyleOpts(opacity=0.2, color="#1f77b4"),
                       color="rgba(0,0,0,0)",
                       linestyle_opts=opts.LineStyleOpts(width=0),
                       stack="forecast_range", label_opts=opts.LabelOpts(is_show=False))
            .set_global_opts(
                title_opts=opts.TitleOpts(title=f"{chart_prefix} Outages - {region}"),
                legend_opts=opts.LegendOpts(pos_right="10%", pos_top="0%"),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="line",
                    formatter=date_only_tooltip_js
                ),
                yaxis_opts=opts.AxisOpts(
                    name=value_col,
                    splitline_opts=opts.SplitLineOpts(
                        is_show=True,
                        linestyle_opts=opts.LineStyleOpts(width=0.5, color="#ddd")
                    )
                ),
                xaxis_opts=opts.AxisOpts(
                    splitline_opts=opts.SplitLineOpts(
                        is_show=True,
                        linestyle_opts=opts.LineStyleOpts(width=0.5, color="#eee")
                    )
                ),
                datazoom_opts=[opts.DataZoomOpts(range_start=0, range_end=100)]
            )
            .set_series_opts(markline_opts=markline)
        )

        filename = f"{chart_prefix}_{region.replace(' ', '_')}.html"
        filepath = os.path.join(output_dir, filename)
        line.render(filepath)

def plot_prophet_decomposition(
    df, region_col="REGION", output_dir="output", chart_prefix="Decomp"
):
    """
    Plot Prophet trend, seasonality (yearly, weekly, semiannual), and residual for each region in the df.
    Assigns colors by name and deselects 'Actual' and 'Residual' in legend by default.
    """
    os.makedirs(output_dir, exist_ok=True)
    df['DATE'] = pd.to_datetime(df['DATE'])

    # Use only these expected seasonality terms, if present in df
    seasonality_terms = ["yearly", "weekly", "semiannual"]

    # Map for line colors
    color_map = {
        "Actual": "#c0392b",
        "Trend": "#1f77b4",
        "Yearly": "#9a60b4",
        "Weekly": "#4caf50",
        "Semiannual": "#666666",        #"#f7c143"
        "Residual": "#f7c143",
    }

    for region in df[region_col].unique():
        df_r = df[df[region_col] == region].sort_values("DATE")
        x_data = df_r["DATE"].dt.strftime("%Y-%m-%d").tolist()

        actual = df_r["KBD"].tolist()
        trend = df_r["trend"].tolist()

        # Build only the seasonality components present
        present_seasonalities = [s for s in seasonality_terms if s in df_r.columns]
        seasonality_vals = {s: df_r[s].tolist() for s in present_seasonalities}
        total_seasonality = sum([df_r[s] for s in present_seasonalities]) if present_seasonalities else 0
        residual = (df_r["KBD"] - df_r["trend"] - total_seasonality).tolist() if present_seasonalities else (df_r["KBD"] - df_r["trend"]).tolist()

        line = (
            Line(init_opts=opts.InitOpts(width=CHART_WIDTH_STR, height=CHART_HEIGHT_STR, renderer="svg"))
            .add_xaxis(x_data)
            .add_yaxis("Actual", actual, is_symbol_show=False, color=color_map["Actual"], linestyle_opts=opts.LineStyleOpts(width=1.5))
            .add_yaxis("Trend", trend, is_symbol_show=False, color=color_map["Trend"], linestyle_opts=opts.LineStyleOpts(width=1.5))
        )

        for s in present_seasonalities:
            line.add_yaxis(
                s.capitalize(), seasonality_vals[s], is_symbol_show=False,
                color=color_map[s.capitalize()],
                linestyle_opts=opts.LineStyleOpts(width=1.5)
            )

        line.add_yaxis("Residual", residual, is_symbol_show=False, color=color_map["Residual"], linestyle_opts=opts.LineStyleOpts(width=1.5))

        line.set_global_opts(
            title_opts=opts.TitleOpts(title=f"{chart_prefix} - {region}"),
            legend_opts=opts.LegendOpts(
                pos_right="10%", pos_top="0%",
                selected_map={"Actual": False, "Residual": False}
            ),
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            yaxis_opts=opts.AxisOpts(
                name="KBD",
                splitline_opts=opts.SplitLineOpts(
                    is_show=True,
                    linestyle_opts=opts.LineStyleOpts(width=0.5, color="#ddd")
                )
            ),
            xaxis_opts=opts.AxisOpts(
                splitline_opts=opts.SplitLineOpts(
                    is_show=True,
                    linestyle_opts=opts.LineStyleOpts(width=0.5, color="#eee")
                ),
            ),
            datazoom_opts=[opts.DataZoomOpts(range_start=0, range_end=100)]
        )

        filename = f"{chart_prefix}_{region.replace(' ', '_')}.html"
        filepath = os.path.join(output_dir, filename)
        line.render(filepath)

def plot_refinery_margins(df, output_dir="output", chart_prefix="RefMargins"):
    """
    Plot time series for each REFINERY_REGION. Each chart shows all REGIONs under that REFINERY_REGION.

    Parameters:
        df: DataFrame with columns DATE, REGION, VALUE, and REFINERY_REGION.
        output_dir: Directory where HTML files will be saved.
        chart_prefix: Prefix for the chart filenames and titles.
    """


    os.makedirs(output_dir, exist_ok=True)
    df['DATE'] = pd.to_datetime(df['DATE'])

    for refinery_region in df["REFINERY_REGION"].unique():
        df_r = df[df["REFINERY_REGION"] == refinery_region]
        line = Line(init_opts=opts.InitOpts(width=CHART_WIDTH_STR, height=CHART_HEIGHT_STR, renderer="svg", theme=PYECHARTS_THEME))

        x_data = sorted(df_r["DATE"].unique())
        x_labels = [d.strftime("%Y-%m-%d") for d in x_data]
        line.add_xaxis(x_labels)

        for region in df_r["REGION"].unique():
            df_region = df_r[df_r["REGION"] == region]
            y_data = df_region.set_index("DATE").reindex(x_data)["VALUE"].astype(float).tolist()
            line.add_yaxis(region, y_data, is_symbol_show=False,
                           linestyle_opts=opts.LineStyleOpts(width=1.5))

        line.set_global_opts(
            title_opts=opts.TitleOpts(title=f"{chart_prefix} - {refinery_region}"),
            legend_opts=opts.LegendOpts(pos_right="0%", pos_top="0%",pos_left="35%"),
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            yaxis_opts=opts.AxisOpts(
                name="VALUE",
                splitline_opts=opts.SplitLineOpts(
                    is_show=True,
                    linestyle_opts=opts.LineStyleOpts(width=0.5, color="#ddd")
                )
            ),
            xaxis_opts=opts.AxisOpts(
                splitline_opts=opts.SplitLineOpts(
                    is_show=True,
                    linestyle_opts=opts.LineStyleOpts(width=0.5, color="#eee")
                )
            ),
            datazoom_opts=[opts.DataZoomOpts(range_start=80, range_end=100)]
        )

        filename = f"{chart_prefix}_{refinery_region.replace(' ', '_')}.html"
        filepath = os.path.join(output_dir, filename)
        line.render(filepath)


# # Helper to generate X-axis labels like "Jan - Agbami"
# def month_label(month, region):
#     return f"{calendar.month_abbr[month]} - {region}"


def plot_boxplots(
    df: pd.DataFrame,
    output_dir: str = "output",
    chart_prefix: str = "RefMarginBox"
):


    os.makedirs(output_dir, exist_ok=True)

    df['DATE'] = pd.to_datetime(df['DATE'])
    df['VALUE'] = pd.to_numeric(df['VALUE'], errors='coerce')
    df['QUARTER'] = df['DATE'].dt.to_period('Q').astype(str)

    # Color palette
    palette = [
        "#5470c6", "#91cc75", "#fac858", "#ee6666",
        "#73c0de", "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc"
    ]

    # Get most recent datapoint per REFINERY_REGION + REGION
    latest_points = (
        df.sort_values("DATE")
          .groupby(["REFINERY_REGION", "REGION"])
          .tail(1)
          .copy()
    )
    latest_points["QUARTER"] = latest_points["DATE"].dt.to_period("Q").astype(str)

    for refinery_region in sorted(df["REFINERY_REGION"].dropna().unique()):
        df_r = df[df["REFINERY_REGION"] == refinery_region].copy()
        latest_r = latest_points[latest_points["REFINERY_REGION"] == refinery_region]

        regions = sorted(df_r["REGION"].dropna().unique())
        x_labels = []
        box_data = []
        item_colors = []
        markpoints = []

        # Generate boxplots and mapping for mark points
        for i, region in enumerate(regions):
            df_region = df_r[df_r["REGION"] == region]
            color = palette[i % len(palette)]

            for j, quarter in enumerate(["Q1", "Q2", "Q3", "Q4"]):
                qmask = df_region["QUARTER"].str.endswith(quarter)
                values = df_region[qmask]["VALUE"].dropna().tolist()
                if values:
                    box_data.append(values)
                    x_labels.append(quarter)
                    item_colors.append(color)

            # Place dot on latest quarter boxplot using x-axis index
            latest_row = latest_r[latest_r["REGION"] == region]
            if not latest_row.empty:
                latest_q = latest_row["QUARTER"].values[0][-2:]  # "Q2"
                quarter_index = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3}[latest_q]
                x_pos = i * 4 + quarter_index
                latest_val = float(latest_row["VALUE"])
                markpoints.append(
                    {
                        "xAxis": x_pos,
                        "yAxis": latest_val,
                        "value": latest_val,
                        "symbol": "circle",
                        "symbolSize": 12,
                        "itemStyle": {
                            "color": "#000"
                        },
                        "label": {
                            "show": False
                        }
                    }
                )

        chart = Boxplot(init_opts=opts.InitOpts(width=CHART_WIDTH_STR, height=CHART_HEIGHT_STR, renderer="svg"))
        chart.add_xaxis(x_labels)
        chart.add_yaxis(
            "",
            chart.prepare_data(box_data),
            itemstyle_opts=opts.ItemStyleOpts(border_width=1.5),
            markpoint_opts=opts.MarkPointOpts(data=markpoints)
        )

        chart.set_series_opts(
            itemstyle_opts=opts.ItemStyleOpts(color="auto", border_width=1.5)
        )

        chart.set_global_opts(
            title_opts=opts.TitleOpts(title=f"{chart_prefix} - {refinery_region}"),
            #tooltip_opts=opts.TooltipOpts(trigger="item"),
            yaxis_opts=opts.AxisOpts(
                name="",  # Removed y-axis label "VALUE"
                splitline_opts=opts.SplitLineOpts(
                    is_show=True,
                    linestyle_opts=opts.LineStyleOpts(width=0.5, color="#ddd")
                )
            ),
            xaxis_opts=opts.AxisOpts(
                axislabel_opts=opts.LabelOpts(rotate=45)
            )
        )

        # Set color and opacity for each box manually
        chart.options['series'][0]['itemStyle'] = {
            "color": None,
            "borderColor": None,
            "borderWidth": 1.5
        }
        chart.options['series'][0]['encode'] = {}

        chart.options['series'][0]['data'] = [
            {
                "value": box,
                "itemStyle": {
                    "color": item_colors[i],
                    "borderColor": item_colors[i],
                    "opacity": 0.75
                }
            } for i, box in enumerate(chart.options['series'][0]['data'])
        ]
        legend_graphics = []
        legend_per_row = 4  # how many items per row
        legend_spacing_x = 115
        legend_spacing_y = 20
        start_left = 335
        start_top = 10

        for i, region in enumerate(regions):
            color = palette[i % len(palette)]
            row = i // legend_per_row
            col = i % legend_per_row
            legend_graphics.append(
                {
                    "type": "group",
                    "left": f"{start_left + col * legend_spacing_x}px",
                    "top": f"{start_top + row * legend_spacing_y}px",
                    "children": [
                        {
                            "type": "rect",
                            "shape": {"width": 15, "height": 15},
                            "style": {"fill": color}
                        },
                        {
                            "type": "text",
                            "left": 20,
                            "top": 0,
                            "style": {
                                "text": region,
                                "font": "12px sans-serif",
                                "fill": "#000"
                            }
                        }
                    ]
                }
            )
        chart.options["graphic"] = legend_graphics

        filename = f"{chart_prefix}_{refinery_region.replace(' ', '_')}.html"
        chart.render(os.path.join(output_dir, filename))



# Redefine chart_eia using fixed styling and improved visibility for seasonal spaghetti plots
def chart_eia(df: pd.DataFrame, output_dir: str = "output", chart_prefix: str = "EIA"):
    """
    Generates seasonal spaghetti plots (x-axis = Jan 1 to Dec 31, lines = years)
    for each REGION in the df. Each REGION gets one chart.
    """

    eia_width = 605
    eia_height = int(eia_width * 9.75 / 16)
    eia_width_str = f"{eia_width}px"
    eia_height_str = f"{eia_height}px"

    selected_map = {str(year): False for year in [2020, 2021, 2022]}

    os.makedirs(output_dir, exist_ok=True)
    df = df.copy()
    df["DATE"] = pd.to_datetime(df["DATE"])
    df["DOY"] = df["DATE"].dt.strftime("%m-%d")  # MM-DD for x-axis
    df["YEAR"] = df["DATE"].dt.year

    for region in df["REGION"].unique():
        df_r = df[df["REGION"] == region].copy()
        x_data = sorted(df_r["DOY"].unique())  # MM-DD labels for x-axis

        line = Line(init_opts=opts.InitOpts(width=eia_width_str, height=eia_height_str, renderer="svg", theme=PYECHARTS_THEME))
        line.add_xaxis(x_data)

        tab10_colors = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
        ]
        color_map = {}
        current_year = pd.Timestamp.today().year
        years = sorted(df_r["YEAR"].unique(), reverse=False)
        for i, year in enumerate(years):
            df_year = df_r[df_r["YEAR"] == year].copy()
            y_data = df_year.set_index("DOY").reindex(x_data)["VALUE"].tolist()

            if year == current_year:
                line.add_yaxis(
                    series_name=str(year),
                    y_axis=y_data,
                    is_symbol_show=False,
                    is_connect_nones=True,
                    linestyle_opts=opts.LineStyleOpts(width=1.75, color="#0c1061"),            #"#ff4c4c"
                    itemstyle_opts=opts.ItemStyleOpts(color="#0c1061")
                )
            else:
                color = tab10_colors[i % len(tab10_colors)]
                line.add_yaxis(
                    series_name=str(year),
                    y_axis=y_data,
                    is_symbol_show=False,
                    is_connect_nones=True,
                    linestyle_opts=opts.LineStyleOpts(width=1, color=color),
                    itemstyle_opts=opts.ItemStyleOpts(color=color)
                )

        line.set_global_opts(
            title_opts=opts.TitleOpts(title=f"{region}"),
          #  tooltip_opts=opts.TooltipOpts(trigger="axis"),
 #           legend_opts=opts.LegendOpts(pos_top="95%", pos_right="5%", type_="scroll"),
            legend_opts=opts.LegendOpts(
                pos_top="bottom",  # Places it at the bottom
                pos_left="center",  # Centers it horizontally
                orient="horizontal",  # Ensures it's laid out left-to-right
                selected_map = selected_map  # Hide these by default
            ),
            xaxis_opts=opts.AxisOpts(name="", axislabel_opts=opts.LabelOpts(rotate=45), splitline_opts=opts.SplitLineOpts(is_show=True,linestyle_opts=opts.LineStyleOpts(color="rgba(180,180,180,0.3)", width=0.5))),
         #   yaxis_opts=opts.AxisOpts(name="", splitline_opts=opts.SplitLineOpts(is_show=True))
            yaxis_opts=opts.AxisOpts(
                name="",
                min_="dataMin",  # Auto-scale based on data
                splitline_opts=opts.SplitLineOpts(
                    is_show=True,
                    linestyle_opts=opts.LineStyleOpts(
                        color="rgba(180,180,180,0.3)",  # light gray, semi-transparent
                        width=0.5
                    )
                )
            )
        )

        clean_region = re.sub(r'\.?\s?kbd?$', '', region, flags=re.IGNORECASE)
        file_name = f"{chart_prefix}_{clean_region.replace(' ', '_')}.html"
        file_path = os.path.join(output_dir, file_name)
        line.render(file_path)




