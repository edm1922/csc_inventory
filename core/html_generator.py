import os
from datetime import datetime

def generate_html_report(report_title, table_headers, table_data, filename="report.html", status_col_idx=None, metadata=None):
    """
    Generates a premium, web-viewable HTML report with signature blocks and optional metadata.
    
    Args:
        report_title (str): Title of the report.
        table_headers (list): List of column headers.
        table_data (list): List of rows (tuples/lists).
        filename (str): Output filename.
        status_col_idx (int, optional): Index of the status column for color coding.
        metadata (dict, optional): Dict of key-value pairs to show under the title.
    """
    now = datetime.now().strftime("%B %d, %Y %I:%M %p")
    
    metadata_html = ""
    if metadata:
        metadata_html = '<div class="metadata-grid">'
        for k, v in metadata.items():
            metadata_html += f'<div class="meta-item"><strong>{k}:</strong> {v}</div>'
        metadata_html += '</div>'
    
    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #2d3436;
            margin: 0;
            padding: 40px;
            background-color: #f8f9fa;
        }}
        
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            border-top: 8px solid #0984e3;
            border-radius: 8px;
        }}
        
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 40px;
            border-bottom: 2px solid #f1f2f6;
            padding-bottom: 20px;
        }}
        
        .company-info h1 {{
            margin: 0;
            color: #2d3436;
            font-size: 24px;
            letter-spacing: -0.5px;
        }}
        
        .company-info p {{
            margin: 5px 0 0;
            color: #636e72;
            font-size: 14px;
        }}
        
        .report-metadata {{
            text-align: right;
        }}
        
        .report-metadata .date {{
            color: #636e72;
            font-size: 14px;
        }}

        .metadata-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
            font-size: 13px;
        }}

        .meta-item strong {{
            color: #2d3436;
        }}
        
        .report-title {{
            font-size: 20px;
            font-weight: 700;
            color: #0984e3;
            text-transform: uppercase;
            margin: 20px 0;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }}
        
        th {{
            background-color: #f1f2f6;
            color: #2d3436;
            font-weight: 600;
            text-align: left;
            padding: 12px 15px;
            border-bottom: 2px solid #dfe6e9;
        }}
        
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #f1f2f6;
        }}
        
        tr:hover {{
            background-color: #fdfdfd;
        }}
        
        .status-badge {{
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .status-low {{ background-color: #fff3cd; color: #856404; }}
        .status-restock {{ background-color: #f8d7da; color: #721c24; }}
        .status-healthy {{ background-color: #d4edda; color: #155724; }}
        
        .signature-section {{
            margin-top: 60px;
            display: flex;
            justify-content: space-between;
            page-break-inside: avoid;
        }}
        
        .sig-box {{
            width: 45%;
        }}
        
        .sig-line {{
            border-bottom: 1px solid #2d3436;
            margin-bottom: 5px;
            height: 40px;
        }}
        
        .sig-label {{
            font-size: 14px;
            font-weight: 600;
            color: #2d3436;
        }}
        
        .sig-sublabel {{
            font-size: 12px;
            color: #636e72;
        }}
        
        @media print {{
            @page {{ size: portrait; margin: 10mm; }}
            body {{ background-color: white; padding: 0; }}
            .container {{ box-shadow: none; border: none; width: 100%; max-width: none; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="company-info">
                <h1>CENTRO SERVICES COOPERATIVE</h1>
                <p>Inventory Management & Logistics Analytics</p>
            </div>
            <div class="report-metadata">
                <div class="date">Generated: {now}</div>
            </div>
        </div>
        
        <div class="report-title">{report_title}</div>
        
        {metadata_html}
        
        <table>
            <thead>
                <tr>
                    {"".join(f"<th>{h}</th>" for h in table_headers)}
                </tr>
            </thead>
            <tbody>
                {"".join(_generate_rows(table_data, status_col_idx))}
            </tbody>
        </table>
        
        <div class="signature-section">
            <div class="sig-box">
                <div class="sig-line"></div>
                <div class="sig-label">Requested By:</div>
                <div class="sig-sublabel">Signature over Printed Name / Date</div>
            </div>
            <div class="sig-box">
                <div class="sig-line"></div>
                <div class="sig-label">Approved By:</div>
                <div class="sig-sublabel">Signature over Printed Name / Date</div>
            </div>
        </div>
    </div>
</body>
</html>
    """
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_template)
    
    return os.path.abspath(filename)

def _generate_rows(data, status_col_idx):
    rows = []
    for row in data:
        tr = "<tr>"
        for i, val in enumerate(row):
            if i == status_col_idx:
                status_class = ""
                status_val = str(val).upper()
                if "LOW" in status_val: status_class = "status-low"
                elif "RESTOCK" in status_val: status_class = "status-restock"
                elif any(x in status_val for x in ["HEALTHY", "OK", "SUFFICIENT"]): status_class = "status-healthy"
                
                tr += f'<td><span class="status-badge {status_class}">{val}</span></td>'
            else:
                tr += f"<td>{val}</td>"
        tr += "</tr>"
        rows.append(tr)
    return rows

# Inject methods into a dummy class for internal usage template if needed, 
# but direct functions are better for core utilities.
    
