import subprocess
import time
import csv
import os

CLIENT_PID = "4625"
VIP = "10.0.0.100"
PORT = 8000
REQUESTS = 10

RESULTS_DIR = os.path.expanduser(
    "~/intelligent-load-balancer/results"
)

CSV_FILE = os.path.join(
    RESULTS_DIR,
    "intelligent_light_results.csv"
)

os.makedirs(RESULTS_DIR, exist_ok=True)

success = 0
failed = 0
times = []

with open(CSV_FILE, "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow([
        "request",
        "status",
        "response_time_ms"
    ])

    for i in range(REQUESTS):
        start = time.perf_counter()

        result = subprocess.run(
            [
                "sudo",
                "mnexec",
                "-a",
                CLIENT_PID,
                "curl",
                "-s",
                "--max-time",
                "5",
                "-H",
                "Connection: close",
                f"http://{VIP}:{PORT}/"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        elapsed = (time.perf_counter() - start) * 1000

        if result.returncode == 0:
            success += 1
            times.append(elapsed)
            status = "SUCCESS"
        else:
            failed += 1
            status = "FAILED"

        writer.writerow([
            i + 1,
            status,
            round(elapsed, 2)
        ])

        print(
            f"Request {i + 1:02d}/{REQUESTS} | "
            f"{status} | {elapsed:.2f} ms"
        )

        time.sleep(0.5)

average = sum(times) / len(times) if times else 0

print("\n" + "=" * 60)
print("LIGHT INTELLIGENT LOAD BALANCER TEST")
print("=" * 60)
print(f"Total requests : {REQUESTS}")
print(f"Successful     : {success}")
print(f"Failed         : {failed}")
print(f"Average time   : {average:.2f} ms")
print()
print("Results saved to:")
print(CSV_FILE)
print("=" * 60)
