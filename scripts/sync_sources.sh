#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
RAW_DIR="${ROOT_DIR}/sources/raw"
EXTRACTED_DIR="${ROOT_DIR}/sources/extracted"

mkdir -p "${RAW_DIR}" "${EXTRACTED_DIR}"

copy_source() {
  local src="$1"
  local dest_name="$2"
  cp -f "${src}" "${RAW_DIR}/${dest_name}"
}

extract_pdf() {
  local pdf_name="$1"
  local txt_name="$2"
  pdftotext -layout "${RAW_DIR}/${pdf_name}" "${EXTRACTED_DIR}/${txt_name}"
}

copy_markdown_extract() {
  local src="$1"
  local dest_name="$2"
  cp -f "${src}" "${RAW_DIR}/${dest_name}"
  cp -f "${src}" "${EXTRACTED_DIR}/${dest_name}"
}

copy_source "/home/ajn/Desktop/ STM_Core_Whitepaper.pdf" "01_STM_Core_Whitepaper.pdf"
extract_pdf "01_STM_Core_Whitepaper.pdf" "01_STM_Core_Whitepaper.txt"

copy_source "/home/ajn/Desktop/reliability_gated_recurrence_polished.pdf" \
  "02_reliability_gated_recurrence_polished.pdf"
extract_pdf "02_reliability_gated_recurrence_polished.pdf" \
  "02_reliability_gated_recurrence_polished.txt"

copy_source "/home/ajn/Desktop/STM_Structural_Manifold_Whitepaper.pdf" \
  "03_STM_Structural_Manifold_Whitepaper.pdf"
extract_pdf "03_STM_Structural_Manifold_Whitepaper.pdf" \
  "03_STM_Structural_Manifold_Whitepaper.txt"

copy_source "/home/ajn/Desktop/QFH_Manifold_Foundation.pdf" "04_QFH_Manifold_Foundation.pdf"
extract_pdf "04_QFH_Manifold_Foundation.pdf" "04_QFH_Manifold_Foundation.txt"

copy_source "/home/ajn/Desktop/sep_signal_regime_whitepaper.pdf" \
  "05_sep_signal_regime_whitepaper.pdf"
extract_pdf "05_sep_signal_regime_whitepaper.pdf" "05_sep_signal_regime_whitepaper.txt"

copy_markdown_extract "/home/ajn/Desktop/iron_dome_methodology_2025.md" \
  "06_iron_dome_methodology_2025.md"

copy_source "/home/ajn/Desktop/sep_signal_regime_whitepaper_2.pdf" \
  "07_sep_signal_regime_whitepaper_2.pdf"
extract_pdf "07_sep_signal_regime_whitepaper_2.pdf" "07_sep_signal_regime_whitepaper_2.txt"

copy_source "/home/ajn/Desktop/global_manifold_v2.pdf" "08_global_manifold_v2.pdf"
extract_pdf "08_global_manifold_v2.pdf" "08_global_manifold_v2.txt"

copy_markdown_extract "/home/ajn/Desktop/unified_strategy_live.md" "09_unified_strategy_live.md"

copy_source "/home/ajn/Desktop/reliability_gate_case_study.pdf" \
  "10_reliability_gate_case_study.pdf"
extract_pdf "10_reliability_gate_case_study.pdf" "10_reliability_gate_case_study.txt"

printf 'Synced Evidence Gate sources into %s and %s\n' "${RAW_DIR}" "${EXTRACTED_DIR}"
