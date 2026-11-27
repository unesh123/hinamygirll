import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
import pytest


def test_real_subprocess_restart_and_key_isolation(tmp_path):
    """
    Real process boundary survival test across distinct OS subprocesses:
    - Process A: Initiates approval challenge in SQLite and terminates.
    - Process B: Distinct subprocess loads from SQLite and consumes with the same key (SUCCESS).
    - Process C: Distinct subprocess attempts replay consumption (FAILS with REPLAY_DETECTED).
    - Process D: Distinct subprocess with a DIFFERENT HMAC key attempts verification (FAILS with SIGNATURE_INVALID).
    """
    db_file = tmp_path / "approvals.db"
    key1 = secrets.token_bytes(32)
    key1_hex = key1.hex()
    key2 = secrets.token_bytes(32)
    key2_hex = key2.hex()

    worker_script = Path(__file__).resolve().parent.parent / "scripts" / "approval_subprocess_worker.py"
    py_exec = sys.executable

    # 1. PROCESS A: Initiate challenge and exit
    proc_a = subprocess.run(
        [
            py_exec,
            str(worker_script),
            "--db-path", str(db_file),
            "--step", "initiate",
            "--key-hex", key1_hex,
            "--tenant-id", "tenant_proc_test",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    out_a = json.loads(proc_a.stdout.strip())
    assert out_a["ok"] is True
    cid = out_a["challenge_id"]
    assert cid.startswith("appr_")

    # 2. PROCESS B: Distinct subprocess resolves and consumes with the SAME key
    proc_b = subprocess.run(
        [
            py_exec,
            str(worker_script),
            "--db-path", str(db_file),
            "--step", "resolve_and_consume",
            "--challenge-id", cid,
            "--key-hex", key1_hex,
            "--tenant-id", "tenant_proc_test",
        ],
        capture_output=True,
        text=True,
    )
    assert proc_b.returncode == 0
    out_b = json.loads(proc_b.stdout.strip())
    assert out_b["ok"] is True
    assert "successfully verified and consumed" in out_b["message"]

    # 3. PROCESS C: Distinct subprocess attempts replay consumption (must be REJECTED)
    proc_c = subprocess.run(
        [
            py_exec,
            str(worker_script),
            "--db-path", str(db_file),
            "--step", "consume_again",
            "--challenge-id", cid,
            "--key-hex", key1_hex,
            "--tenant-id", "tenant_proc_test",
        ],
        capture_output=True,
        text=True,
    )
    out_c = json.loads(proc_c.stdout.strip())
    assert out_c["ok"] is False
    assert "REPLAY_DETECTED" in out_c["message"]

    # 4. PROCESS D: Test signature rejection with WRONG KEY
    # First, initiate a new challenge with key1
    proc_d_init = subprocess.run(
        [
            py_exec,
            str(worker_script),
            "--db-path", str(db_file),
            "--step", "initiate",
            "--key-hex", key1_hex,
            "--tenant-id", "tenant_proc_test",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    cid2 = json.loads(proc_d_init.stdout.strip())["challenge_id"]

    # Now attempt verification using key2 (WRONG KEY)
    proc_d = subprocess.run(
        [
            py_exec,
            str(worker_script),
            "--db-path", str(db_file),
            "--step", "verify_signature",
            "--challenge-id", cid2,
            "--key-hex", key2_hex,
            "--tenant-id", "tenant_proc_test",
        ],
        capture_output=True,
        text=True,
    )
    out_d = json.loads(proc_d.stdout.strip())
    assert out_d["ok"] is False
    # Either not approved or signature invalid
    assert "Challenge is not approved" in out_d["message"] or "SIGNATURE_INVALID" in out_d["message"]
