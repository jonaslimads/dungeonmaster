#!/usr/bin/env bash
set -euo pipefail

SOURCES_DIR="./data/rag/sources"

if [ ! -d "$SOURCES_DIR" ]; then
  echo "No sources directory found: $SOURCES_DIR"
  exit 0
fi

echo "RAG Clean Script"
echo "Keeps: data/pdfs/, data/rag/sources/*/original/source.pdf"
echo "Removes: pages/, assets/, extracted/, canonical/, chunks/, reports/"
echo ""

for source_dir in "$SOURCES_DIR"/*/; do
  [ -d "$source_dir" ] || continue
  source_id=$(basename "$source_dir")
  echo "Cleaning: $source_id"

  # Remove generated directories
  rm -rf "$source_dir/pages"
  rm -rf "$source_dir/assets"
  rm -rf "$source_dir/extracted"
  rm -rf "$source_dir/canonical"
  rm -rf "$source_dir/chunks"
  rm -rf "$source_dir/reports"

  echo "  ✓ Cleaned (original/source.pdf kept)"
done

echo ""
echo "Done."
