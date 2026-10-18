#!/bin/bash
set -eo pipefail

# ==============================================================================
# Odoo 20 Portability & Clean-Environment Verification Harness (Bash / Linux / CI)
# ==============================================================================

DB_NAME="${1:-test_portability_db}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Safety check
if [[ ! "$DB_NAME" =~ (test|portability|clean|temp) ]]; then
    echo "ERROR: Target database '$DB_NAME' does not match safety filter (must contain test/portability/clean/temp)."
    exit 1
fi

PYTHON_BIN="python3"
if [ -f "$REPO_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$REPO_DIR/.venv/bin/python"
fi

ODOO_BIN="$REPO_DIR/odoo-bin"
CONF_FILE="$REPO_DIR/odoo.conf"
MODULES="custom_hr_contract,enterprise_approval,frontdesk_admin,it_helpdesk,project_security_tier,modern_cloud_theme"

echo "=============================================================================="
echo "  ODOO 20 PORTABILITY VERIFICATION HARNESS (Linux / Docker / CI)"
echo "  Target Database : $DB_NAME"
echo "  Modules         : $MODULES"
echo "  Python          : $PYTHON_BIN"
echo "  Odoo Bin        : $ODOO_BIN"
echo "  Config File     : $CONF_FILE"
echo "=============================================================================="

CMD=("$PYTHON_BIN" "$ODOO_BIN")
if [ -f "$CONF_FILE" ]; then
    CMD+=("-c" "$CONF_FILE")
fi
CMD+=("-d" "$DB_NAME" "-i" "$MODULES" "--stop-after-init" "--test-enable")

echo "Running: ${CMD[*]}"
"${CMD[@]}"

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "=============================================================================="
    echo " [SUCCESS] All custom addons cleanly installed and tested on fresh database!"
    echo "=============================================================================="
else
    echo "=============================================================================="
    echo " [FAILURE] Installation or tests failed with exit code $EXIT_CODE"
    echo "=============================================================================="
fi

exit $EXIT_CODE
