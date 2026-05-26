#!/usr/bin/env bash
set -euo pipefail

BASE="${RAG_BASE_URL:-http://localhost:8002}"
FORCE="${FORCE:-false}"

SOURCES=(
  "dnd_5e_players_handbook"
  "dnd_5e_dungeon_masters_guide"
  "dnd_5e_monster_manual"
)

echo "RAG Chunking Script"
echo "Base URL: $BASE"
echo "Force: $FORCE"
echo ""

for source_id in "${SOURCES[@]}"; do
  echo "============================================"
  echo "Source: $source_id"
  echo "============================================"

  curl -s -X POST "$BASE/chunking/sources/$source_id" \
    -H "Content-Type: application/json" \
    -d "{\"force\": $FORCE}" | jq .

  echo ""
done

echo "============================================"
echo "Done. Check data/rag/sources/*/chunks/"
echo "============================================"
