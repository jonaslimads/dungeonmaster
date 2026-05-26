#!/usr/bin/env bash
set -euo pipefail

BASE="${RAG_BASE_URL:-http://localhost:8002}"

QUERIES=(
  "fireball"
  "grapple"
  "goblin"
  "orc"
  "action surge"
  "short rest"
  "advantage and disadvantage"
  "saving throw"
  "magic item rarity"
  "creating encounters"
  "challenge rating"
  "stealth"
  "perception check"
  "initiative"
  "spell slots"
  "mountain giant"
  "darkvision"
  "death saving throws"
  "critical hit"
  "spell attack bonus"
)

echo "RAG Retrieval Test"
echo "Base URL: $BASE"
echo ""

for query in "${QUERIES[@]}"; do
  echo "--- Query: $query ---"
  curl -s -X POST "$BASE/retrieval/search" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$query\", \"top_k\": 3}" | \
    jq -r '.results[] | "  [\(.score)] \(.title) (\(.chunk_type)) p.\(.page_start) - \(.text[:120])"'
  echo ""
done
