"""Phase 01 - BlueStacks and ADB System Verification."""
import subprocess
import json
import os
import sys

ADB_PATH = "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe"

def run_cmd(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return proc.returncode, proc.stdout.strip() or proc.stderr.strip()
    except Exception as e:
        return -1, str(e)

def verify_bluestacks():
    results = {}
    print("=" * 60)
    print("BLUESTACKS & ADB VERIFICATION")
    print("=" * 60)
    
    # 1. Check BlueStacks exe
    player_exe = "C:\\Program Files\\BlueStacks_nxt\\HD-Player.exe"
    exists = os.path.exists(player_exe)
    print(f"1. BlueStacks 5 Player Exists: {exists} ({player_exe})")
    results["player_installed"] = exists
    
    # 2. Check HD-Adb.exe
    adb_exists = os.path.exists(ADB_PATH)
    print(f"2. HD-Adb Exists: {adb_exists} ({ADB_PATH})")
    results["adb_installed"] = adb_exists
    
    # 3. Check ADB version
    rc, out = run_cmd([ADB_PATH, "version"])
    print(f"3. ADB Version:\n   {out.splitlines()[0] if out else 'Error'}")
    results["adb_version"] = out
    
    # 4. Check connected devices
    rc, out = run_cmd([ADB_PATH, "devices"])
    print(f"4. ADB Devices:\n   {out}")
    devices = [line.split()[0] for line in out.splitlines()[1:] if line.strip() and "device" in line]
    results["connected_devices"] = devices
    
    # 5. Check emulator properties if connected
    if devices:
        target = devices[0]
        rc, model = run_cmd([ADB_PATH, "-s", target, "shell", "getprop", "ro.product.model"])
        rc, android_ver = run_cmd([ADB_PATH, "-s", target, "shell", "getprop", "ro.build.version.release"])
        print(f"5. Device Info [{target}]:")
        print(f"   Model: {model}")
        print(f"   Android Version: {android_ver}")
        results["device_details"] = {
            "serial": target,
            "model": model,
            "android_version": android_ver
        }
    else:
        print("5. No active devices connected to ADB.")
        results["device_details"] = None

    out_file = "docs/evolution/bluestacks_adb_verification.json"
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nVerification saved to {out_file}")

if __name__ == "__main__":
    verify_bluestacks()
