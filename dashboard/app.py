from flask import Flask, jsonify, send_from_directory
import csv
import os
import re
from collections import defaultdict

app = Flask(__name__)

BASE_DIR = os.path.expanduser("~/intelligent-load-balancer")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
RYU_LOG = os.path.join(RESULTS_DIR, "ryu_events.log")

BACKENDS = [
    ("h5", "10.0.0.5", 8001),
    ("h6", "10.0.0.6", 8002),
    ("h7", "10.0.0.7", 8003),
    ("h8", "10.0.0.8", 8004),
    ("h9", "10.0.0.9", 8005),
    ("h10", "10.0.0.10", 8006),
]

WEIGHTS = {
    "cpu": 0.40,
    "connections": 0.20,
    "response": 0.25,
    "network": 0.15,
}

SELECTION_PATTERN = re.compile(
    r"INTELLIGENT BACKEND SELECTED:\s+"
    r"(10\.0\.0\.\d+):(\d+)\s+\|\s+SCORE=([0-9.]+)"
)


def read_csv(filename):
    path = os.path.join(RESULTS_DIR, filename)

    if not os.path.exists(path):
        return []

    try:
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def latest_metrics():
    rows = read_csv("server_metrics.csv")
    latest = {}

    for row in rows:
        latest[row["server"]] = row

    return latest


def calculate_scores(latest):
    valid = []

    for name, ip, port in BACKENDS:
        row = latest.get(name)

        if not row:
            continue

        try:
            valid.append({
                "server": name,
                "ip": ip,
                "port": port,
                "cpu": float(row["cpu_percent"]),
                "connections": float(row["active_connections"]),
                "response": float(row["response_time_ms"]),
                "network": float(row["network_bytes"]),
            })
        except (ValueError, TypeError):
            continue

    if not valid:
        return {}

    def normalize(value, values):
        minimum = min(values)
        maximum = max(values)

        if maximum == minimum:
            return 0.0

        return (value - minimum) / (maximum - minimum)

    cpu_values = [x["cpu"] for x in valid]
    conn_values = [x["connections"] for x in valid]
    response_values = [x["response"] for x in valid]
    network_values = [x["network"] for x in valid]

    scores = {}

    for item in valid:
        score = (
            WEIGHTS["cpu"] * normalize(item["cpu"], cpu_values)
            + WEIGHTS["connections"] * normalize(
                item["connections"], conn_values
            )
            + WEIGHTS["response"] * normalize(
                item["response"], response_values
            )
            + WEIGHTS["network"] * normalize(
                item["network"], network_values
            )
        )

        scores[item["server"]] = round(score, 4)

    return scores


def read_ryu_selections():
    selections = []

    if not os.path.exists(RYU_LOG):
        return selections

    try:
        with open(RYU_LOG, "r", errors="replace") as f:
            for line in f:
                match = SELECTION_PATTERN.search(line)

                if not match:
                    continue

                ip = match.group(1)
                port = int(match.group(2))
                score = float(match.group(3))

                server = next(
                    (
                        name
                        for name, backend_ip, backend_port
                        in BACKENDS
                        if backend_ip == ip and backend_port == port
                    ),
                    None
                )

                if server:
                    selections.append({
                        "server": server,
                        "ip": ip,
                        "port": port,
                        "score": score,
                    })

    except Exception:
        return []

    return selections


@app.route("/")
def index():
    return send_from_directory(DASHBOARD_DIR, "index.html")


@app.route("/api/live")
def live():
    latest = latest_metrics()
    scores = calculate_scores(latest)
    selections = read_ryu_selections()

    servers = []

    for name, ip, port in BACKENDS:
        row = latest.get(name)

        if not row:
            continue

        servers.append({
            "server": name,
            "ip": ip,
            "port": port,
            "timestamp": row["timestamp"],
            "cpu_percent": float(row["cpu_percent"]),
            "active_connections": int(row["active_connections"]),
            "network_bytes": int(row["network_bytes"]),
            "response_time_ms": float(row["response_time_ms"]),
            "score": scores.get(name),
        })

    actual_selected = None
    actual_selected_score = None

    if selections:
        latest_selection = selections[-1]
        actual_selected = latest_selection["server"]
        actual_selected_score = latest_selection["score"]

    selection_counts = {
        name: 0
        for name, _, _ in BACKENDS
    }

    for selection in selections:
        selection_counts[selection["server"]] += 1

    recent_selections = selections[-10:][::-1]

    return jsonify({
        "servers": servers,

        "selected_backend": actual_selected,
        "selected_score": actual_selected_score,

        "selection_counts": selection_counts,
        "recent_selections": recent_selections,
        "total_selections": len(selections),

        "timestamp": (
            servers[-1]["timestamp"]
            if servers
            else None
        )
    })


@app.route("/api/history")
def history():
    rows = read_csv("server_metrics.csv")

    history = defaultdict(list)

    for row in rows[-300:]:
        try:
            history[row["server"]].append({
                "timestamp": row["timestamp"],
                "cpu": float(row["cpu_percent"]),
                "connections": int(row["active_connections"]),
                "network": int(row["network_bytes"]),
                "response": float(row["response_time_ms"]),
            })
        except (ValueError, TypeError):
            continue

    return jsonify(history)


@app.route("/api/results")
def results():
    intelligent = read_csv("intelligent_reliable_results.csv")
    multi = read_csv("multi_client_results.csv")

    intelligent_success = sum(
        1 for row in intelligent
        if row.get("status") == "SUCCESS"
    )

    multi_success = sum(
        1 for row in multi
        if row.get("status") == "SUCCESS"
    )

    intelligent_avg = 0

    if intelligent:
        values = []

        for row in intelligent:
            try:
                values.append(float(row["response_time_ms"]))
            except (ValueError, TypeError):
                pass

        if values:
            intelligent_avg = round(
                sum(values) / len(values),
                2
            )

    return jsonify({
        "intelligent": {
            "total": len(intelligent),
            "successful": intelligent_success,
            "failed": len(intelligent) - intelligent_success,
            "success_rate": round(
                intelligent_success / len(intelligent) * 100,
                2
            ) if intelligent else 0,
            "average_response_ms": intelligent_avg,
        },
        "multi_client": {
            "total": len(multi),
            "successful": multi_success,
            "failed": len(multi) - multi_success,
            "success_rate": round(
                multi_success / len(multi) * 100,
                2
            ) if multi else 0,
        }
    })


@app.route("/api/status")
def status():
    latest = latest_metrics()
    selections = read_ryu_selections()

    return jsonify({
        "monitoring": len(latest) == 6,
        "backends_online": len(latest),
        "expected_backends": 6,
        "ryu_selection_logging": os.path.exists(RYU_LOG),
        "total_selections": len(selections),
        "dashboard": "online"
    })


if __name__ == "__main__":
    print("=" * 60)
    print("SDN INTELLIGENT LOAD BALANCER DASHBOARD")
    print("=" * 60)
    print("Dashboard : http://127.0.0.1:8080")
    print("Live API  : http://127.0.0.1:8080/api/live")
    print("History   : http://127.0.0.1:8080/api/history")
    print("Ryu Log   : " + RYU_LOG)
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False
    )
