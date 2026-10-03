import subprocess
import time

H1_PID = "4625"
VIP = "10.0.0.100"
PORT = "8000"

success = 0
failed = 0

for i in range(10):
    result = subprocess.run(
        [
            "sudo", "mnexec", "-a", H1_PID,
            "curl", "-s", "--max-time", "5",
            f"http://{VIP}:{PORT}"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if result.returncode == 0:
        success += 1
        print(f"Request {i + 1}/10: SUCCESS")
    else:
        failed += 1
        print(f"Request {i + 1}/10: FAILED")

    time.sleep(0.5)

print("\n========== VIP TEST ==========")
print(f"Successful: {success}")
print(f"Failed:     {failed}")
