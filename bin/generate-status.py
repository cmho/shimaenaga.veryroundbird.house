#!/usr/bin/env python3

"""
Generate a simple, attractive HTML status page showing:
- System load, CPU %, root-disk usage, network usage
- Number of accounts and each account's DID
- Per-account store record/blob counts (from read-only SQLite)
- Disk usage for each blocks directory by DID

Requires:
- Python 3.6+
- psutil (`pip install psutil`)
- jinja2 (`pip install jinja2`)

Usage:
./generate_status.py --pds-path /pds --output status.html
"""

import os
import argparse
import sqlite3
import psutil  # type: ignore
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader, select_autoescape  # type: ignore


def human_readable_size(size, decimal_places=1):
    """Convert a size in bytes to a human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if size < 1024.0 or unit == "PB":
            return f"{size:.{decimal_places}f} {unit}"
        size /= 1024.0
    return f"{size:.{decimal_places}f} PB"


def get_system_metrics():
    """Gather system load, CPU usage, root-disk stats, and network usage."""
    load1, load5, load15 = os.getloadavg()
    cpu_percent = psutil.cpu_percent(interval=1)
    usage = psutil.disk_usage("/")
    net = psutil.net_io_counters(pernic=True).get("eth0")
    net_sent = net.bytes_sent if net else 0
    net_recv = net.bytes_recv if net else 0
    uptime_seconds = int(psutil.boot_time())
    uptime = datetime.now() - datetime.fromtimestamp(uptime_seconds)

    return {
        "load1": load1,
        "load5": load5,
        "load15": load15,
        "cpu_percent": cpu_percent,
        "disk_total": usage.total,
        "disk_used": usage.used,
        "disk_percent": usage.percent,
        "net_sent": net_sent,
        "net_recv": net_recv,
        "uptime": str(timedelta(seconds=int(uptime.total_seconds()))),
    }


def get_account_data(pds_path):
    """Get total account count and list of DIDs from the account database."""
    account_db = os.path.join(pds_path, "account.sqlite")
    uri = f"file:{account_db}?mode=ro"

    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM account")
    total_accounts = cur.fetchone()[0]

    cur.execute("SELECT did FROM account")
    dids = [row[0] for row in cur.fetchall()]

    conn.close()
    return total_accounts, dids


def find_store_db(pds_path, did):
    """Find the store.sqlite file for a given DID."""
    actors_root = os.path.join(pds_path, "actors")
    for root, dirs, files in os.walk(actors_root):
        if os.path.basename(root) == did and "store.sqlite" in files:
            return os.path.join(root, "store.sqlite")
    return None


def get_store_data(pds_path, did):
    """Get record and blob counts from a store database."""
    store_db = find_store_db(pds_path, did)
    if not store_db:
        raise FileNotFoundError(f"store.sqlite not found for DID {did}")

    uri = f"file:{store_db}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM record")
    rec_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM blob")
    blob_count = cur.fetchone()[0]

    conn.close()
    return rec_count, blob_count


def get_directory_usage(path):
    """Calculate total disk usage of a directory."""
    total = 0
    for root, _, files in os.walk(path):
        for fn in files:
            fp = os.path.join(root, fn)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def create_template_env():
    """Create a Jinja2 template environment with the template string."""
    template_str = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Server Status</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-dark-5@1.1.3/dist/css/bootstrap-dark.min.css" rel="stylesheet">
    <style>
        body {
            padding: 20px;
        }
    </style>
</head>
<body class="bg-dark text-light">
    <div class="container">
        <h1 class="my-4">Server Status</h1>
        <p>Report generated: {{ generated }} (uptime: {{ metrics.uptime }})</p>

        <h2>System Metrics</h2>
        <table class="table table-dark table-bordered">
            <tr>
                <th>Load (1m)</th>
                <th>Load (5m)</th>
                <th>Load (15m)</th>
                <th>CPU %</th>
                <th>Disk (/)</th>
                <th>Net Sent</th>
                <th>Net Received</th>
            </tr>
            <tr>
                <td>{{ "%.2f"|format(metrics.load1) }}</td>
                <td>{{ "%.2f"|format(metrics.load5) }}</td>
                <td>{{ "%.2f"|format(metrics.load15) }}</td>
                <td>{{ "%.1f"|format(metrics.cpu_percent) }}%</td>
                <td>{{ human_size(metrics.disk_used) }} / {{ human_size(metrics.disk_total) }} ({{ metrics.disk_percent }}%)</td>
                <td>{{ human_size(metrics.net_sent) }}</td>
                <td>{{ human_size(metrics.net_recv) }}</td>
            </tr>
        </table>

        <h2>Accounts in {{ pds_path }}</h2>
        <p>Total accounts: {{ total_accounts }}</p>
        <table class="table table-dark table-striped table-bordered">
            <thead>
                <tr>
                    <th>DID</th>
                    <th>Record Count</th>
                    <th>Blob Count</th>
                    <th>Blocks Dir Size</th>
                </tr>
            </thead>
            <tbody>
                {% for did, rec, blob, size in usage_list %}
                <tr>
                    <td>{{ did }}</td>
                    <td>{{ rec }}</td>
                    <td>{{ blob }}</td>
                    <td>{{ human_size(size) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    env = Environment(
        loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__))),
        autoescape=select_autoescape(["html", "xml"]),
    )

    # Add the template string directly to the environment with a name
    env.from_string = template_str

    # Register the human_readable_size function for templates
    env.filters["human_size"] = human_readable_size

    return env


def main():
    parser = argparse.ArgumentParser(
        description="Generate a server status HTML report."
    )
    parser.add_argument("--pds-path", default="/pds", help="Root path for PDS data")
    parser.add_argument("--output", default="status.html", help="Output HTML filename")
    args = parser.parse_args()

    # Gather all data
    metrics = get_system_metrics()
    total_accounts, dids = get_account_data(args.pds_path)
    usage_list = []

    for did in dids:
        try:
            rec_count, blob_count = get_store_data(args.pds_path, did)
        except Exception:
            rec_count, blob_count = "Error", "Error"

        block_dir = os.path.join(args.pds_path, "blocks", did)
        size = get_directory_usage(block_dir) if os.path.isdir(block_dir) else 0
        usage_list.append((did, rec_count, blob_count, size))

    # Setup Jinja2 environment and render template
    env = create_template_env()
    template = env.from_string

    # Create a template from the string
    jinja_template = Environment().from_string(template)

    # Render the template with our data
    rendered_html = jinja_template.render(
        metrics=metrics,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_accounts=total_accounts,
        usage_list=usage_list,
        pds_path=args.pds_path,
        human_size=human_readable_size,
    )

    # Write output to file
    with open(args.output, "w") as f:
        f.write(rendered_html)

    print(f"Status page written to {args.output}")


if __name__ == "__main__":
    main()
