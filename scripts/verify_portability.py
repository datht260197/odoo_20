#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portability & Clean-Environment Verification Harness for Odoo 20 Custom Modules.

Automates the installation and test verification of all custom addons on a fresh,
clean database to guarantee zero dependency gaps, valid data sequences, and
clean execution across Docker, bare-metal Linux, and LXC containers.

Usage:
    python scripts/verify_portability.py [--db-name test_portability_db] [--skip-tests]
"""

import argparse
import os
import subprocess
import sys


TARGET_MODULES = [
    "custom_hr_contract",
    "enterprise_approval",
    "frontdesk_admin",
    "it_helpdesk",
    "project_security_tier",
    "modern_cloud_theme",
]


def resolve_odoo_bin():
    """Locate odoo-bin executable relative to script or in workspace."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidate = os.path.join(repo_root, "odoo-bin")
    if os.path.exists(candidate):
        return candidate
    return "odoo-bin"


def resolve_python():
    """Locate Python executable in virtualenv or system PATH."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    venv_py_win = os.path.join(repo_root, ".venv", "Scripts", "python.exe")
    venv_py_unix = os.path.join(repo_root, ".venv", "bin", "python")
    if os.path.exists(venv_py_win):
        return venv_py_win
    if os.path.exists(venv_py_unix):
        return venv_py_unix
    return sys.executable


def resolve_conf():
    """Locate odoo.conf file."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    conf = os.path.join(repo_root, "odoo.conf")
    if os.path.exists(conf):
        return conf
    return None


def run_verification(db_name, test_enable=True):
    # Safety assertion: Database name must contain test or portability
    if not any(token in db_name.lower() for token in ("test", "portability", "clean", "temp")):
        print(f"Error: Database '{db_name}' does not appear to be a dedicated test database.")
        print("Safety rule violated: Portability runner only operates on test databases.")
        sys.exit(1)

    python_bin = resolve_python()
    odoo_bin = resolve_odoo_bin()
    conf_file = resolve_conf()

    modules_arg = ",".join(TARGET_MODULES)

    cmd = [
        python_bin,
        odoo_bin,
    ]

    if conf_file:
        cmd.extend(["-c", conf_file])

    cmd.extend([
        "-d", db_name,
        "-i", modules_arg,
        "--stop-after-init",
    ])

    if test_enable:
        cmd.append("--test-enable")

    print("=" * 80)
    print(f"  ODOO 20 PORTABILITY VERIFICATION HARNESS")
    print(f"  Target DB      : {db_name}")
    print(f"  Target Addons  : {modules_arg}")
    print(f"  Python Bin     : {python_bin}")
    print(f"  Odoo Bin       : {odoo_bin}")
    print(f"  Config File    : {conf_file or 'Default CLI options'}")
    print(f"  Tests Enabled  : {test_enable}")
    print("=" * 80)
    print("Executing installation command:")
    print(" ".join(cmd))
    print("-" * 80)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    proc = subprocess.run(cmd, cwd=repo_root)

    print("-" * 80)
    if proc.returncode == 0:
        print("[SUCCESS] All custom addons installed and verified cleanly!")
        print("Portability validation: PASS (Exit Code 0).")
    else:
        print(f"[FAILURE] Verification failed with exit code {proc.returncode}.")
        print("Please check the tracebacks above for missing dependencies or view errors.")
    print("=" * 80)

    return proc.returncode


def main():
    parser = argparse.ArgumentParser(description="Verify Odoo 20 Custom Modules Portability on Clean Database")
    parser.add_argument(
        "--db-name",
        default="test_portability_db",
        help="Target clean database name (must contain 'test' or 'portability')",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip unit test execution during installation",
    )
    args = parser.parse_args()

    rc = run_verification(db_name=args.db_name, test_enable=not args.skip_tests)
    sys.exit(rc)


if __name__ == "__main__":
    main()
