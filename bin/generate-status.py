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

Usage:
  ./generate_status.py --pds-path /pds --output status.html
"""
import os
import argparse
import sqlite3
import psutil # type: ignore
from datetime import datetime, timedelta
import html


def human_readable_size(size, decimal_places=1):
    """Convert a size in bytes to a human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0 or unit == 'PB':
            return f"{size:.{decimal_places}f} {unit}"
        size /= 1024.0
    return f"{size:.{decimal_places}f} PB"


def get_system_metrics():
    """Gather system load, CPU usage, root-disk stats, and network usage."""
    load1, load5, load15 = os.getloadavg()
    cpu_percent = psutil.cpu_percent(interval=1)
    usage = psutil.disk_usage('/')
    net = psutil.net_io_counters(pernic=True).get('eth0')
    net_sent = net.bytes_sent if net else 0
    net_recv = net.bytes_recv if net else 0
    uptime_seconds = int(psutil.boot_time())
    uptime = datetime.now() - datetime.fromtimestamp(uptime_seconds)
    return {
        'load1': load1,
        'load5': load5,
        'load15': load15,
        'cpu_percent': cpu_percent,
        'disk_total': usage.total,
        'disk_used': usage.used,
        'disk_percent': usage.percent,
        'net_sent': net_sent,
        'net_recv': net_recv,
        'uptime': str(timedelta(seconds=int(uptime.total_seconds())))
    }


def get_account_data(pds_path):
    account_db = os.path.join(pds_path, 'account.sqlite')
    uri = f'file:{account_db}?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM account')
    total_accounts = cur.fetchone()[0]
    cur.execute('SELECT did FROM account')
    dids = [row[0] for row in cur.fetchall()]
    conn.close()
    return total_accounts, dids


def find_store_db(pds_path, did):
    actors_root = os.path.join(pds_path, 'actors')
    for root, dirs, files in os.walk(actors_root):
        if os.path.basename(root) == did and 'store.sqlite' in files:
            return os.path.join(root, 'store.sqlite')
    return None


def get_store_data(pds_path, did):
    store_db = find_store_db(pds_path, did)
    if not store_db:
        raise FileNotFoundError(f"store.sqlite not found for DID {did}")
    uri = f'file:{store_db}?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM record')
    rec_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM blob')
    blob_count = cur.fetchone()[0]
    conn.close()
    return rec_count, blob_count


def get_directory_usage(path):
    total = 0
    for root, _, files in os.walk(path):
        for fn in files:
            fp = os.path.join(root, fn)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def generate_html(metrics, total_accounts, usage_list, pds_path):
    generated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    uptime = metrics['uptime']
    html_parts = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append("<html lang=\"en\">")
    html_parts.append("<head>")
    html_parts.append("<meta charset=\"UTF-8\"> <title>Server Status</title>")
    html_parts.append(
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">'
    )
    html_parts.append('<link href="https://cdn.jsdelivr.net/npm/bootstrap-dark-5@1.1.3/dist/css/bootstrap-dark.min.css" rel="stylesheet">')
    html_parts.append("<style>body{padding:20px;}</style>")
    html_parts.append("</head><body class=\"bg-dark text-light\"><div class=\"container\">")
    html_parts.append("<h1 class=\"my-4\">Server Status</h1>")
    html_parts.append(f"<p>Report generated: {generated} (uptime: {uptime})</p>")

    html_parts.append("<h2>System Metrics</h2>")
    html_parts.append("<table class=\"table table-dark table-bordered\"><tr>")
    html_parts.append("<th>Load (1m)</th><th>Load (5m)</th><th>Load (15m)</th><th>CPU %</th><th>Disk (/)</th><th>Net Sent</th><th>Net Received</th></tr>")
    html_parts.append(
        f"<tr>"
        f"<td>{metrics['load1']:.2f}</td>"
        f"<td>{metrics['load5']:.2f}</td>"
        f"<td>{metrics['load15']:.2f}</td>"
        f"<td>{metrics['cpu_percent']:.1f}%</td>"
        f"<td>{human_readable_size(metrics['disk_used'])} / {human_readable_size(metrics['disk_total'])} ({metrics['disk_percent']}%)</td>"
        f"<td>{human_readable_size(metrics['net_sent'])}</td>"
        f"<td>{human_readable_size(metrics['net_recv'])}</td>"
        f"</tr>"
    )
    html_parts.append("</table>")

    html_parts.append(f"<h2>Accounts in {html.escape(pds_path)}</h2>")
    html_parts.append(f"<p>Total accounts: {total_accounts}</p>")
    html_parts.append("<table class=\"table table-dark table-striped table-bordered\">")
    html_parts.append("<thead><tr><th>DID</th><th>Record Count</th><th>Blob Count</th><th>Blocks Dir Size</th></tr></thead><tbody>")
    for did, rec, blob, size in usage_list:
        html_parts.append(
            f"<tr><td>{html.escape(did)}</td><td>{rec}</td><td>{blob}</td><td>{human_readable_size(size)}</td></tr>"
        )
    html_parts.append("</tbody></table>")
    html_parts.append("</div></body></html>")
    return '\n'.join(html_parts)


def main():
    parser = argparse.ArgumentParser(description="Generate a server status HTML report.")
    parser.add_argument('--pds-path', default='/pds', help='Root path for PDS data')
    parser.add_argument('--output', default='status.html', help='Output HTML filename')
    args = parser.parse_args()

    metrics = get_system_metrics()
    total, dids = get_account_data(args.pds_path)
    usage_list = []
    for did in dids:
        try:
            rec_count, blob_count = get_store_data(args.pds_path, did)
        except Exception:
            rec_count, blob_count = 'Error', 'Error'
        block_dir = os.path.join(args.pds_path, 'blocks', did)
        size = get_directory_usage(block_dir) if os.path.isdir(block_dir) else 0
        usage_list.append((did, rec_count, blob_count, size))

    html_out = generate_html(metrics, total, usage_list, args.pds_path)
    with open(args.output, 'w') as f:
        f.write(html_out)
    print(f"Status page written to {args.output}")


if __name__ == '__main__':
    main()