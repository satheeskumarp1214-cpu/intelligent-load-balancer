import subprocess
import time
import csv
import os

VIP = "10.0.0.100"
PORT = 8000
REQUESTS = 60

RESULTS_DIR = os.path.expanduser(
    "~/intelligent-load-balancer/results"
)

CSV_FILE = os.path.join(
    RESULTS_DIR,
    "intelligent_reliable_results.csv"
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
        pid_result = subprocess.run(
            [
                "bash",
                "-c",
                "pgrep -f 'mininet:h1' | head -1"
            ],
            capture_output=True,
            text=True
        )

        pid = pid_result.stdout.strip()

        if not pid:
            print(f"Request {i + 1:02d}/{REQUESTS} | NO H1 PID")
            failed += 1
            writer.writerow([i + 1, "FAILED", 0])
            continue

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
print("RELIABLE INTELLIGENT TEST")
print("=" * 60)
print(f"Total requests : {REQUESTS}")
print(f"Successful     : {success}")
print(f"Failed         : {failed}")
print(f"Average time   : {average:.2f} ms")
print()
print("Results saved to:")
print(CSV_FILE)
print("=" * 60)
