import csv
import os

BACKENDS = [
    ("h5", "10.0.0.5", 8001),
    ("h6", "10.0.0.6", 8002),
    ("h7", "10.0.0.7", 8003),
    ("h8", "10.0.0.8", 8004),
    ("h9", "10.0.0.9", 8005),
    ("h10", "10.0.0.10", 8006),
]

CSV_FILE = os.path.expanduser(
    "~/intelligent-load-balancer/results/server_metrics.csv"
)

CPU_WEIGHT = 0.40
CONNECTION_WEIGHT = 0.20
RESPONSE_WEIGHT = 0.25
NETWORK_WEIGHT = 0.15


def normalize(values):
    minimum = min(values)
    maximum = max(values)

    if maximum == minimum:
        return [0.0 for _ in values]

    return [
        (value - minimum) / (maximum - minimum)
        for value in values
    ]


def read_latest_metrics():
    if not os.path.exists(CSV_FILE):
        return []

    latest = {}

    with open(CSV_FILE, newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            latest[row["server"]] = row

    return list(latest.values())


def select_server():
    metrics = read_latest_metrics()

    if not metrics:
        print("No server metrics available.")
        return None

    valid = []

    for row in metrics:
        try:
            cpu = float(row["cpu_percent"])
            connections = float(row["active_connections"])
            response = float(row["response_time_ms"])
            network = float(row["network_bytes"])

            if response < 0:
                continue

            valid.append({
                "server": row["server"],
                "ip": row["ip"],
                "port": row["port"],
                "cpu": cpu,
                "connections": connections,
                "response": response,
                "network": network
            })

        except (ValueError, KeyError):
            continue

    if not valid:
        print("No valid server metrics available.")
        return None

    cpu_values = normalize([x["cpu"] for x in valid])
    connection_values = normalize(
        [x["connections"] for x in valid]
    )
    response_values = normalize(
        [x["response"] for x in valid]
    )
    network_values = normalize(
        [x["network"] for x in valid]
    )

    for i, server in enumerate(valid):

        server["score"] = (
            CPU_WEIGHT * cpu_values[i]
            + CONNECTION_WEIGHT * connection_values[i]
            + RESPONSE_WEIGHT * response_values[i]
            + NETWORK_WEIGHT * network_values[i]
        )

    valid.sort(key=lambda x: x["score"])

    print("\n" + "=" * 70)
    print("INTELLIGENT SERVER SELECTION")
    print("=" * 70)

    print(
        f"{'Server':<8}"
        f"{'CPU %':<12}"
        f"{'Conn':<10}"
        f"{'Response':<14}"
        f"{'Network':<15}"
        f"{'Score':<10}"
    )

    print("-" * 70)

    for server in valid:
        print(
            f"{server['server']:<8}"
            f"{server['cpu']:<12.2f}"
            f"{server['connections']:<10.0f}"
            f"{server['response']:<14.2f}"
            f"{server['network']:<15.0f}"
            f"{server['score']:<10.4f}"
        )

    selected = valid[0]

    print("-" * 70)
    print(
        f"SELECTED SERVER: "
        f"{selected['server']} "
        f"({selected['ip']}:{selected['port']})"
    )
    print(
        f"LOWEST SCORE: {selected['score']:.4f}"
    )
    print("=" * 70)

    return selected


if __name__ == "__main__":
    select_server()
