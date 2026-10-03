import subprocess
import time
import csv
import os

CLIENTS = {
    "h1": "4625",
    "h2": "4627",
    "h3": "4629",
    "h4": "4631",
}

VIP = "10.0.0.100"
PORT = 8000
REQUESTS = 60

RESULTS_DIR = os.path.expanduser(
    "~/intelligent-load-balancer/results"
)

CSV_FILE = os.path.join(
    RESULTS_DIR,
    "round_robin_results.csv"
)

os.makedirs(RESULTS_DIR, exist_ok=True)

success = 0
failed = 0
times = []
distribution = {
    "h1": 0,
    "h2": 0,
    "h3": 0,
    "h4": 0
}

with open(CSV_FILE, "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow([
        "request",
        "client",
        "status",
        "response_time_ms"
    ])

    for i in range(REQUESTS):
        client = list(CLIENTS.keys())[i % len(CLIENTS)]
        pid = CLIENTS[client]

        start = time.perf_counter()

        result = subprocess.run(
            [
                "sudo",
                "mnexec",
                "-a",
                pid,
                "curl",
                "-s",
                "--max-time",
                "5",
                f"http://{VIP}:{PORT}"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        elapsed = (time.perf_counter() - start) * 1000

        if result.returncode == 0:
            success += 1
            times.append(elapsed)
            distribution[client] += 1
            status = "SUCCESS"
        else:
            failed += 1
            status = "FAILED"

        writer.writerow([
            i + 1,
            client,
            status,
            round(elapsed, 2)
        ])

        print(
            f"Request {i + 1:02d}/60 | "
            f"{client} | {status} | "
            f"{elapsed:.2f} ms"
        )

        time.sleep(0.1)

average = (
    sum(times) / len(times)
    if times else 0
)

print("\n" + "=" * 60)
print("ROUND ROBIN BASELINE")
print("=" * 60)
print(f"Total requests : {REQUESTS}")
print(f"Successful     : {success}")
print(f"Failed         : {failed}")
print(f"Average time   : {average:.2f} ms")
print()
print("Client distribution:")

for client, count in distribution.items():
    print(f"{client}: {count}")

print()
print(f"Results saved to:")
print(CSV_FILE)
print("=" * 60)
