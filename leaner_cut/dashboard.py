import os
import sqlite3
import webbrowser
from pathlib import Path

def generate_dashboard():
    db_path = str(Path(__file__).parent / "blackboard.db")
    if not os.path.exists(db_path):
        print(f"Error: Database '{db_path}' not found. Run main.py first to populate it.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, timestamp, agent_name, input, output FROM runs ORDER BY id DESC")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        print("Error: The 'runs' table does not exist. Run main.py first.")
        conn.close()
        return
    conn.close()

    # HTML template with premium, modern dark design
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Blackboard Dashboard</title>
    <style>
        :root {
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --card-border: #30363d;
            --text-main: #c9d1d9;
            --text-soft: #8b949e;
            --accent-color: #58a6ff;
            --success-color: #3fb950;
            --warning-color: #d29922;
            --header-gradient: linear-gradient(135deg, #1f6feb 0%, #8a4cdb 100%);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.6;
            padding: 40px 20px;
        }

        .container {
            max-width: 1100px;
            margin: 0 auto;
        }

        header {
            padding: 30px;
            border-radius: 12px;
            background: var(--header-gradient);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            margin-bottom: 40px;
            position: relative;
            overflow: hidden;
        }

        header::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, rgba(255, 255, 255, 0) 50%);
            pointer-events: none;
        }

        header h1 {
            font-size: 2.2rem;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 8px;
            letter-spacing: -0.02em;
        }

        header p {
            color: rgba(255, 255, 255, 0.8);
            font-size: 1rem;
            font-weight: 400;
        }

        .refresh-btn {
            position: absolute;
            right: 30px;
            top: 35px;
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            padding: 8px 16px;
            border-radius: 6px;
            color: white;
            font-weight: 500;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.2s ease;
        }

        .refresh-btn:hover {
            background: rgba(255, 255, 255, 0.3);
        }

        .grid {
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }

        .card:hover {
            border-color: var(--accent-color);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--card-border);
            padding-bottom: 12px;
            margin-bottom: 16px;
        }

        .agent-badge {
            font-family: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
            font-size: 0.85rem;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .agent-badge.extractor {
            background-color: rgba(88, 166, 255, 0.15);
            color: var(--accent-color);
            border: 1px solid rgba(88, 166, 255, 0.3);
        }

        .agent-badge.risk-analyst {
            background-color: rgba(210, 153, 34, 0.15);
            color: var(--warning-color);
            border: 1px solid rgba(210, 153, 34, 0.3);
        }

        .agent-badge.synthesizer {
            background-color: rgba(63, 185, 80, 0.15);
            color: var(--success-color);
            border: 1px solid rgba(63, 185, 80, 0.3);
        }

        .timestamp {
            font-size: 0.85rem;
            color: var(--text-soft);
            font-family: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
        }

        .section-title {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-soft);
            margin-bottom: 8px;
            font-weight: 600;
        }

        .io-block {
            margin-bottom: 16px;
        }

        .io-block:last-child {
            margin-bottom: 0;
        }

        pre {
            background-color: #090c10;
            border: 1px solid var(--card-border);
            padding: 14px;
            border-radius: 6px;
            font-family: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
            font-size: 0.9rem;
            overflow-x: auto;
            white-space: pre-wrap;
            color: #e6edf3;
        }

        .empty-state {
            text-align: center;
            padding: 50px;
            color: var(--text-soft);
            font-size: 1.1rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Agent Execution Trace</h1>
            <p>Blackboard state from sqlite3 database</p>
            <a href="javascript:location.reload()" class="refresh-btn">Refresh Dashboard</a>
        </header>

        <div class="grid">
"""

    if not rows:
        html_content += '<div class="empty-state">No execution runs found. Run main.py to start pipeline.</div>'
    else:
        for row in rows:
            run_id, timestamp, agent_name, inp, outp = row
            badge_class = agent_name.lower().replace(" ", "-")
            
            html_content += f"""
            <div class="card">
                <div class="card-header">
                    <span class="agent-badge {badge_class}">{agent_name}</span>
                    <span class="timestamp">{timestamp} (ID: #{run_id})</span>
                </div>
                <div class="io-block">
                    <div class="section-title">Input Context</div>
                    <pre>{inp}</pre>
                </div>
                <div class="io-block">
                    <div class="section-title">Output Response</div>
                    <pre>{outp}</pre>
                </div>
            </div>
            """

    html_content += """
        </div>
    </div>
</body>
</html>
"""

    dashboard_file = str(Path(__file__).parent / "dashboard.html")
    with open(dashboard_file, "w") as f:
        f.write(html_content)

    abs_path = os.path.abspath(dashboard_file)
    print(f"Dashboard successfully generated at: {abs_path}")
    webbrowser.open(f"file://{abs_path}")

if __name__ == "__main__":
    generate_dashboard()
