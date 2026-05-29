#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${1:-"${ROOT_DIR}/build/lambda"}"
if [[ "${OUTPUT_DIR}" != /* ]]; then
  OUTPUT_DIR="${ROOT_DIR}/${OUTPUT_DIR}"
fi

mkdir -p "${OUTPUT_DIR}"

(cd "${ROOT_DIR}/lambdas/bronze/hackernews_ingest" && zip -qr "${OUTPUT_DIR}/hackernews_ingest.zip" .)
(cd "${ROOT_DIR}/lambdas/bronze/x_ingest" && zip -qr "${OUTPUT_DIR}/x_ingest.zip" .)

echo "Packaged Lambda artifacts in ${OUTPUT_DIR}"
