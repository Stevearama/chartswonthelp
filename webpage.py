
import os
from datetime import datetime

def make_webpage(chart_dict_tabs: dict, title: str, output_dir: str, output_filename: str):
    os.makedirs(output_dir, exist_ok=True)
    full_path = os.path.join(output_dir, output_filename)

    timestamp = datetime.now().strftime("%b %d, %Y. %H:%M")

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        f"<title>{title}</title>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "<style>",
        "body { font-family: 'Segoe UI', Roboto, sans-serif; margin: 0; background: #f4f6f8; color: #333; }",
        "header { background: #fff; padding: 12px 16px; font-size: 24px; font-weight: 600;",
        "         box-shadow: 0 2px 4px rgba(0,0,0,0.06); border-bottom: 1px solid #ddd; text-align: left; position: relative; }",
        "header span { font-size: 14px; font-weight: normal; float: right; color: #666; margin-top: 4px; }",

        "nav.tabs { display: flex; gap: 10px; padding: 10px 10px; background: #e9ecef; border-bottom: 1px solid #ccc; }",
        "nav.tabs button { padding: 8px 16px; background: #fff; border: 1px solid #ccc; border-radius: 4px;",
        "                  cursor: pointer; font-weight: 500; }",
        "nav.tabs button.active { background: #007bff; color: white; border-color: #007bff; }",

        "nav.subtabs { display: flex; gap: 10px; padding: 10px 10px; background: #f8f9fa; }",
        "nav.subtabs button { padding: 6px 12px; background: #fff; border: 1px solid #bbb; border-radius: 4px;",
        "                     cursor: pointer; font-size: 14px; }",
        "nav.subtabs button.active { background: #343a40; color: white; }",

        ".tab-content, .subtab-content { display: none; }",
        ".tab-content.active, .subtab-content.active { display: block; }",

        # Card layout: default aspect, hover, flexible scaling per row
        ".grid-row { display: grid; gap: 20px; padding: 10px; }",
        ".card { position: relative; aspect-ratio: 16 / 10;",
        "        background: #fff; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);",
        "        overflow: hidden; transition: transform 0.2s ease; width: 100%; }",
        ".card:hover { transform: translateY(-4px); }",
        ".card iframe { position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: none; }",
        "</style>",

        "<script>",
        "function showTab(tabId) {",
        "  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));",
        "  document.querySelectorAll('nav.tabs button').forEach(b => b.classList.remove('active'));",
        "  document.getElementById(tabId).classList.add('active');",
        "  document.getElementById('btn_' + tabId).classList.add('active');",
        "}",
        "function showSubtab(tabId, subtabId) {",
        "  document.querySelectorAll(`#${tabId} .subtab-content`).forEach(t => t.classList.remove('active'));",
        "  document.querySelectorAll(`#${tabId} nav.subtabs button`).forEach(b => b.classList.remove('active'));",
        "  document.getElementById(`${tabId}_${subtabId}`).classList.add('active');",
        "  document.getElementById(`btn_${tabId}_${subtabId}`).classList.add('active');",
        "}",
        "</script>",
        "</head>",
        "<body>",
        f"<header>{title}<span>{timestamp}</span></header>",
        "<nav class='tabs'>"
    ]

    # Top-level tabs
    for i, top_tab in enumerate(chart_dict_tabs):
        active_class = "active" if i == 0 else ""
        html_parts.append(f"<button id='btn_{top_tab}' class='{active_class}' onclick=\"showTab('{top_tab}')\">{top_tab}</button>")
    html_parts.append("</nav>")

    # Tab content
    for i, (top_tab, subtab_dict) in enumerate(chart_dict_tabs.items()):
        active_tab = "active" if i == 0 else ""
        html_parts.append(f"<div class='tab-content {active_tab}' id='{top_tab}'>")

        # Subtabs
        html_parts.append("<nav class='subtabs'>")
        for j, subtab in enumerate(subtab_dict):
            active_sub = "active" if j == 0 else ""
            html_parts.append(f"<button id='btn_{top_tab}_{subtab}' class='{active_sub}' onclick=\"showSubtab('{top_tab}', '{subtab}')\">{subtab}</button>")
        html_parts.append("</nav>")

        # Subtab content
        for j, (subtab, chart_rows) in enumerate(subtab_dict.items()):
            active_sub = "active" if j == 0 else ""
            html_parts.append(f"<div class='subtab-content {active_sub}' id='{top_tab}_{subtab}'>")

            for row in chart_rows:
                num_columns = len(row)  # total columns, including "EMPTY"
                html_parts.append(
                    f"<div class='grid-row' style='grid-template-columns: repeat({num_columns}, minmax(0, 1fr));'>")

                for chart in row:
                    if chart != "EMPTY":
                        html_parts.append(f"<div class='card'><iframe src='{chart}'></iframe></div>")
                    else:
                        html_parts.append("<div></div>")  # keep column space, render as empty
                html_parts.append("</div>")  # end row

            html_parts.append("</div>")  # end subtab content

        html_parts.append("</div>")  # end tab content

    html_parts.append("</body></html>")

    with open(full_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))

    print(f"Webpage with dynamic tabs and responsive layout created at: {full_path}")
