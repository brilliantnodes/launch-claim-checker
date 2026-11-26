#!/usr/bin/env bash
# Run the v2 direct-mode tests on GenVM v0.6 against the packed Bradbury build.
#
#   pip install --pre genlayer-test==0.30.0rc2     # in a separate virtualenv
#   python3 tools/port_bradbury.py contracts/launch_claim_checker_v2.py bradbury/build/launch_claim_checker_v2.py --pack
#   tools/test_v6_v2.sh /path/to/that/venv
#
# Same test file as on Studio (GenVM v0.2); a scratch copy swaps in tests/conftest_v6.py.
set -euo pipefail
VENV="${1:?path to a virtualenv with genlayer-test 0.30.0rc2}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
(cd "$ROOT" && git ls-files -co --exclude-standard -- contracts tests tools bradbury gltest.config.yaml | tar -cf - -T -) | tar -xf - -C "$TMP"
cp "$TMP/tests/conftest_v6.py" "$TMP/tests/direct/conftest.py"
cd "$TMP"
GENVM_VERSION="${GENVM_VERSION:-v0.6.0-rc10}" LCC2_CONTRACT="${LCC2_BUILD:-bradbury/build/launch_claim_checker_v2.py}" PYTHONPATH=. \
  "$VENV/bin/python" -m pytest tests/direct/test_checker_v2.py tests/direct/test_checker_v2_review.py tests/direct/test_checker_v2_review3.py tests/direct/test_checker_v2_review4.py -q -p no:cacheprovider
