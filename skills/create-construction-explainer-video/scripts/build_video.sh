#!/usr/bin/env bash
# Build vertical and landscape HyperFrames review videos.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <project-dir> [--draft]"
  exit 2
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(cd "$1" && pwd)
shift
QUALITY="standard"
if [[ "${1:-}" == "--draft" ]]; then
  QUALITY="draft"
fi

command -v ffmpeg >/dev/null || { echo "ERROR: ffmpeg is required"; exit 1; }
command -v ffprobe >/dev/null || { echo "ERROR: ffprobe is required"; exit 1; }

python3 "$SCRIPT_DIR/validate_project.py" "$PROJECT_DIR" --stage content
python3 "$SCRIPT_DIR/build_compositions.py" "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/renders" "$PROJECT_DIR/preview"

for PROFILE in vertical landscape; do
  COMPOSITION_DIR="$PROJECT_DIR/composition/$PROFILE"
  OUTPUT="$PROJECT_DIR/renders/final-$PROFILE-review.mp4"
  echo "==> $PROFILE: check"
  (cd "$COMPOSITION_DIR" && npx --yes hyperframes check)
  echo "==> $PROFILE: render ($QUALITY)"
  (cd "$COMPOSITION_DIR" && npx --yes hyperframes render --quality "$QUALITY" --output "$OUTPUT")
  [[ -f "$OUTPUT" ]] || { echo "ERROR: missing render $OUTPUT"; exit 1; }

  FRAME_DIR=$(mktemp -d)
  trap 'rm -rf "$FRAME_DIR"' EXIT
  TIMES=$(python3 - "$PROJECT_DIR" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
path = root / "audio" / "durations.json"
if path.exists():
    data = json.loads(path.read_text())
    print(" ".join(f"{s['start'] + s['duration'] / 2:.3f}" for s in data["segments"]))
else:
    sb = json.loads((root / "content" / "storyboard.json").read_text())
    n = len(sb["segments"])
    print(" ".join(str(4 + i * 8) for i in range(n)))
PY
  )
  INDEX=1
  for T in $TIMES; do
    ffmpeg -y -loglevel error -ss "$T" -i "$OUTPUT" -frames:v 1 "$FRAME_DIR/f-$INDEX.png"
    INDEX=$((INDEX + 1))
  done
  FRAME_COUNT=$((INDEX - 1))
  GRID="3x3"
  if [[ $FRAME_COUNT -le 6 ]]; then GRID="3x2"; fi
  ffmpeg -y -loglevel error -framerate 1 -i "$FRAME_DIR/f-%d.png" \
    -vf "scale=360:-1,tile=$GRID:padding=12:margin=12:color=#F3F0E8" \
    -frames:v 1 -update 1 "$PROJECT_DIR/preview/montage-$PROFILE.png"
  rm -rf "$FRAME_DIR"
  trap - EXIT
done

python3 "$SCRIPT_DIR/verify_output.py" "$PROJECT_DIR"
echo "Built review videos in $PROJECT_DIR/renders"
