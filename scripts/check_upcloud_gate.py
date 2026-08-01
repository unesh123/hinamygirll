#!/usr/bin/env python3
"""Refuse UpCloud provisioning unless explicit owner confirmation is present."""

from __future__ import annotations

import os
import sys

CONFIRM = "I_AUTHORIZE_STAGING_RESOURCES"


def main() -> int:
    if os.environ.get("HINAA_ALLOW_UPCLOUD_PROVISIONING") != "1":
        print("Refusing: set HINAA_ALLOW_UPCLOUD_PROVISIONING=1")
        return 2
    if os.environ.get("HINAA_UPCLOUD_PROVISIONING_CONFIRM") != CONFIRM:
        print(f"Refusing: set HINAA_UPCLOUD_PROVISIONING_CONFIRM={CONFIRM}")
        return 2
    print("Gates present. Review docs/36-upcloud-deployment-runbook.md before creating resources.")
    print("This script does not provision anything by itself.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
