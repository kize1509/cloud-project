#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${1:-"${ROOT_DIR}/build/lambda"}"
if [[ "${OUTPUT_DIR}" != /* ]]; then
  OUTPUT_DIR="${ROOT_DIR}/${OUTPUT_DIR}"
fi

mkdir -p "${OUTPUT_DIR}"

package_lambda_with_common() {
  local source_dir="$1"
  local artifact_name="$2"
  local staging_dir
  staging_dir="$(mktemp -d)"

  cp "${source_dir}/app.py" "${staging_dir}/app.py"
  cp -r "${ROOT_DIR}/lambdas/silver/common" "${staging_dir}/common"
  (cd "${staging_dir}" && zip -qr "${OUTPUT_DIR}/${artifact_name}.zip" .)
  rm -rf "${staging_dir}"
}

package_lambda_with_gold_common() {
  local source_dir="$1"
  local artifact_name="$2"
  local staging_dir
  staging_dir="$(mktemp -d)"

  cp "${source_dir}/app.py" "${staging_dir}/app.py"
  cp -r "${ROOT_DIR}/lambdas/gold/common" "${staging_dir}/common"
  (cd "${staging_dir}" && zip -qr "${OUTPUT_DIR}/${artifact_name}.zip" .)
  rm -rf "${staging_dir}"
}

(cd "${ROOT_DIR}/lambdas/bronze/hackernews_ingest" && zip -qr "${OUTPUT_DIR}/hackernews_ingest.zip" .)
(cd "${ROOT_DIR}/lambdas/bronze/x_ingest" && zip -qr "${OUTPUT_DIR}/x_ingest.zip" .)

package_lambda_with_common "${ROOT_DIR}/lambdas/silver/hackernews_silver" "hackernews_silver"
package_lambda_with_common "${ROOT_DIR}/lambdas/silver/x_silver" "x_silver"
package_lambda_with_gold_common "${ROOT_DIR}/lambdas/gold/gold_transform" "gold_transform"

echo "Packaged Lambda artifacts in ${OUTPUT_DIR}"
