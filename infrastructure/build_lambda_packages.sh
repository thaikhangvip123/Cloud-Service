#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="${ROOT}/build"
PACKAGES="${ROOT}/packages"

rm -rf "${BUILD}" "${PACKAGES}"
mkdir -p "${BUILD}/layer/python" "${PACKAGES}"
python3 -m pip install -r "${ROOT}/requirements.txt" -t "${BUILD}/layer/python"
cp -R "${ROOT}/shared" "${BUILD}/layer/python/shared"
(cd "${BUILD}/layer" && zip -qr "${PACKAGES}/dependencies-layer.zip" python)

for function in executor expiry email_approval; do
  mkdir -p "${BUILD}/${function}/lambda_functions/${function}"
  cp "${ROOT}/lambda_functions/__init__.py" "${BUILD}/${function}/lambda_functions/"
  cp "${ROOT}/lambda_functions/${function}/"*.py \
    "${BUILD}/${function}/lambda_functions/${function}/"
  (cd "${BUILD}/${function}" && zip -qr "${PACKAGES}/${function}.zip" .)
done

echo "Lambda packages written to ${PACKAGES}"
