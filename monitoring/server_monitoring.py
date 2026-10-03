import csv
import os
import time
from datetime import datetime

BACKENDS = [
    ("h5", "10.0.0.5", 8001),
    ("h6", "10.0.0.6", 8002),
    ("h7", "10.0.0.7", 8003),
    ("h8", "10.0.0.8", 8004),
    ("h9", "10.0.0.9", 8005),
    ("h10", "10.0.0.10", 8006),
]

RESULTS_DIR = os.path.expanduser(
    "~/intelligent-load-balancer/results"
)

CSV_FILE = os.path.join(
    RESULTS_DIR,
    "server_metrics.csv"
)

INTERVAL = 2


def get_cpu(host):
    command = (
        f"sudo mnexec -a $(pgrep -f 'mininet:{host}' | head -1) "
        "sh -c \"top -bn1 | grep 'Cpu(s)' | "
        "awk '{print 100 - \$8}'\""
    )

    output = os.popen(command).read().strip()

    try:
        return float(output)
    except ValueError:
        return 0.0


def get_connections(host, port):
    command = (
        f"sudo mnexec -a $(pgrep -f 'mininet:{host}' | head -1) "
        f"sh -c \"ss -tan 2>/dev/null | "
        f"grep ':\\?{port}' | wc -l\""
    )

    output = os.popen(command).read().strip()

    try:
        return int(output)
    except ValueError:
        return 0


def get_network_bytes(host):
    command = (
        f"sudo mnexec -a $(pgrep -f 'mininet:{host}' | head -1) "
        "sh -c \"cat /sys/class/net/*/statistics/rx_bytes "
        "/sys/class/net/*/statistics/tx_bytes 2>/dev/null\""
    )

    output = os.popen(command).read().split()

    try:
        values = [int(x) for x in output]
        return sum(values)
    except ValueError:
        return 0


def check_server(host, port):
    start = time.perf_counter()

    command = (
        f"sudo mnexec -a $(pgrep -f 'mininet:{host}' | head -1) "
        f"curl -s --max-time 2 "
        f"http://{host_ip(host)}:{port} >/dev/null"
    )

    result = os.system(command)

    elapsed = (time.perf_counter() - start) * 1000

    if result == 0:
        return round(elapsed, 2)

    return -1


def host_ip(host):
    for name, ip, port in BACKENDS:
        if name == host:
            return ip

    return "0.0.0.0"


def initialize_csv():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="") as file:
            writer = csv.writer(file)

            writer.writerow([
                "timestamp",
                "server",
                "ip",
                "port",
                "cpu_percent",
                "active_connections",
                "network_bytes",
                "response_time_ms"
            ])


def collect_metrics():
    initialize_csv()

    print("=" * 70)
    print("SDN INTELLIGENT LOAD BALANCER - SERVER MONITOR")
    print("=" * 70)
    print("Writing metrics to:")
    print(CSV_FILE)
    print("Press Ctrl+C to stop.")
    print()

    while True:
        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        rows = []

        for host, ip, port in BACKENDS:
            cpu = get_cpu(host)
            connections = get_connections(host, port)
            network = get_network_bytes(host)
            response = check_server(host, port)

            rows.append([
                timestamp,
                host,
                ip,
                port,
                round(cpu, 2),
                connections,
                network,
                response
            ])

            print(
                f"{host:<4} "
                f"CPU={cpu:6.2f}%  "
                f"CONN={connections:<4} "
                f"NET={network:<10} "
                f"RESP={response:7.2f} ms"
            )

        with open(CSV_FILE, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerows(rows)

        print("-" * 70)

        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        collect_metrics()

    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
