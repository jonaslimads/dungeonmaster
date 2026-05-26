#!/usr/bin/env bash
set -euo pipefail

BASE="${RAG_BASE_URL:-http://localhost:8002}"
USE_VLM="${USE_VLM:-false}"
FORCE="${FORCE:-false}"

SOURCES=(
  "D.D.5E.-.Livro.do.Jogador.Fundo.Colorido.pdf|D&D 5E Player's Handbook|core_rulebook|dnd_5e|dnd_5e_players_handbook"
  "D.D.5E.-.Guia.do.Mestre.pdf|D&D 5E Dungeon Master's Guide|core_rulebook|dnd_5e|dnd_5e_dungeon_masters_guide"
  "D.D.5E.-.Manual.dos.Monstros.pdf|D&D 5E Monster Manual|monster_book|dnd_5e|dnd_5e_monster_manual"
)

wait_job() {
  local job_id="$1"
  local max_wait="${2:-3600}"
  local elapsed=0
  local interval=10

  while [ "$elapsed" -lt "$max_wait" ]; do
    status=$(curl -s "$BASE/extraction/jobs/$job_id" | jq -r '.status // "unknown"')
    if [ "$status" = "completed" ]; then
      echo "  ✓ Job $job_id completed"
      return 0
    elif [ "$status" = "failed" ]; then
      error=$(curl -s "$BASE/extraction/jobs/$job_id" | jq -r '.error // "unknown error"')
      echo "  ✗ Job $job_id failed: $error"
      return 1
    fi
    echo "  ⏳ $status (${elapsed}s / ${max_wait}s)"
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done
  echo "  ✗ Job $job_id timed out after ${max_wait}s"
  return 1
}

process_source() {
  local file_name="$1"
  local title="$2"
  local source_type="$3"
  local system="$4"
  local source_id="$5"

  echo "============================================"
  echo "Source: $source_id"
  echo "============================================"

  # Step 1: Register (skip if already exists)
  echo "[1/3] Registering..."
  exists=$(curl -s "$BASE/sources/$source_id" | jq -r '.id // ""')
  if [ "$exists" = "$source_id" ] && [ "$FORCE" = "false" ]; then
    echo "  ✓ Already registered, skipping"
  else
    curl -s -X POST "$BASE/sources/register-local" \
      -H "Content-Type: application/json" \
      -d "{
        \"file_name\": \"$file_name\",
        \"title\": \"$title\",
        \"source_type\": \"$source_type\",
        \"system\": \"$system\",
        \"source_id\": \"$source_id\"
      }" | jq -r '.id' > /dev/null
    echo "  ✓ Registered"
  fi

  # Step 2: Create job
  echo "[2/3] Creating extraction job (use_vlm=$USE_VLM, force=$FORCE)..."
  job_id=$(curl -s -X POST "$BASE/extraction/jobs" \
    -H "Content-Type: application/json" \
    -d "{
      \"source_id\": \"$source_id\",
      \"use_vlm\": $USE_VLM,
      \"force\": $FORCE
    }" | jq -r '.id')
  echo "  ✓ Job: $job_id"

  # Step 3: Run job
  echo "[3/3] Running job..."
  curl -s -X POST "$BASE/extraction/jobs/$job_id/run" > /dev/null

  # Wait for completion
  wait_job "$job_id"

  echo ""
}

echo "RAG Ingestion Script"
echo "Base URL: $BASE"
echo "Use VLM: $USE_VLM"
echo "Force: $FORCE"
echo ""

for source in "${SOURCES[@]}"; do
  IFS='|' read -r file_name title source_type system source_id <<< "$source"
  process_source "$file_name" "$title" "$source_type" "$system" "$source_id"
done

echo "============================================"
echo "Done. Check data/rag/sources/ for output."
echo "============================================"
