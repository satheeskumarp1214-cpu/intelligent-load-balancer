import subprocess
import time
import csv
import os

CLIENTS = ["h1", "h2", "h3", "h4"]
REQUESTS_PER_CLIENT = 10
VIP = "10.0.0.100"
PORT = 8000

RESULTS_DIR = os.path.expanduser("~/intelligent-load-balancer/results")
CSV_FILE = os.path.join(RESULTS_DIR, "multi_client_results.csv")

os.makedirs(RESULTS_DIR, exist_ok=True)

success = 0
failed = 0

with open(CSV_FILE, "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["client", "request", "status", "response_time_ms"])

    for client in CLIENTS:
        pid_result = subprocess.run(
            ["bash", "-c", f"pgrep -f 'mininet:{client}' | head -1"],
            capture_output=True,
            text=True
        )

        pid = pid_result.stdout.strip()

        if not pid:
            print(f"{client}: Mininet PID not found")
            failed += REQUESTS_PER_CLIENT
            continue

        for i in range(REQUESTS_PER_CLIENT):
            start = time.perf_counter()

            result = subprocess.run(
                [
                    "sudo", "mnexec", "-a", pid,
                    "curl", "-s", "--max-time", "5",
                    f"http://{VIP}:{PORT}/"
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            elapsed = (time.perf_counter() - start) * 1000

            if result.returncode == 0:
                status = "SUCCESS"
                success += 1
            else:
                status = "FAILED"
                failed += 1

            writer.writerow([
                client, i + 1, status, round(elapsed, 2)
            ])

            print(
                f"{client} Request {i + 1:02d}/{REQUESTS_PER_CLIENT} | "
                f"{status} | {elapsed:.2f} ms"
            )

            time.sleep(0.2)

total = success + failed
rate = (success / total * 100) if total else 0

print("\n" + "=" * 60)
print("MULTI-CLIENT TEST")
print("=" * 60)
print(f"Total requests : {total}")
print(f"Successful     : {success}")
print(f"Failed         : {failed}")
print(f"Success rate   : {rate:.2f}%")
print()
print("Results saved to:")
print(CSV_FILE)
print("=" * 60)
