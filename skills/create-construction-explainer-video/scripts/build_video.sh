#!/usr/bin/env bash
# Build vertical and landscape HyperFrames review videos.

set -euo pipefail

usage() {
  echo "Usage: $0 <project-dir> [--draft] [--profile vertical|landscape|all]"
  exit 2
}

[[ $# -lt 1 ]] && usage

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_DIR=$(cd "$1" && pwd)
shift
QUALITY="standard"
PROFILE_FILTER="all"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --draft) QUALITY="draft"; shift ;;
    --profile) PROFILE_FILTER="${2:-all}"; shift 2 ;;
    *) usage ;;
  esac
done
case "$PROFILE_FILTER" in vertical|landscape|all) ;; *) usage ;; esac

command -v ffmpeg >/dev/null || { echo "ERROR: ffmpeg is required"; exit 1; }
command -v ffprobe >/dev/null || { echo "ERROR: ffprobe is required"; exit 1; }

python3 "$SCRIPT_DIR/validate_project.py" "$PROJECT_DIR" --stage content
python3 "$SCRIPT_DIR/build_compositions.py" "$PROJECT_DIR" --profile "$PROFILE_FILTER"
mkdir -p "$PROJECT_DIR/renders" "$PROJECT_DIR/preview"

FRAME_DIR=$(mktemp -d)
trap 'rm -rf "$FRAME_DIR"' EXIT

PROFILES="vertical landscape"
[[ "$PROFILE_FILTER" != "all" ]] && PROFILES="$PROFILE_FILTER"

for PROFILE in $PROFILES; do
  COMPOSITION_DIR="$PROJECT_DIR/composition/$PROFILE"
  OUTPUT="$PROJECT_DIR/renders/final-$PROFILE-review.mp4"
  echo "==> $PROFILE: check"
  (cd "$COMPOSITION_DIR" && npx --yes hyperframes check)
  echo "==> $PROFILE: render ($QUALITY)"
  (cd "$COMPOSITION_DIR" && npx --yes hyperframes render --quality "$QUALITY" --output "$OUTPUT")
  [[ -f "$OUTPUT" ]] || { echo "ERROR: missing render $OUTPUT"; exit 1; }

  # Scene midpoints for the montage; 20%/55%/90% points for the motion sheet.
  MID_TIMES=$(python3 - "$PROJECT_DIR" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
path = root / "audio" / "durations.json"
if path.exists():
    segments = json.loads(path.read_text())["segments"]
else:
    sb = json.loads((root / "content" / "storyboard.json").read_text())
    segments = [{"start": 4 + i * 8, "duration": 8} for i in range(len(sb["segments"]))]
print(" ".join(f"{s['start'] + s['duration'] / 2:.3f}" for s in segments))
PY
  )

  rm -f "$FRAME_DIR"/*.png
  INDEX=1
  for T in $MID_TIMES; do
    ffmpeg -y -loglevel error -ss "$T" -i "$OUTPUT" -frames:v 1 "$FRAME_DIR/f-$INDEX.png"
    INDEX=$((INDEX + 1))
  done
  FRAME_COUNT=$((INDEX - 1))
  GRID="3x3"
  if [[ $FRAME_COUNT -le 6 ]]; then GRID="3x2"; fi
  ffmpeg -y -loglevel error -framerate 1 -i "$FRAME_DIR/f-%d.png" \
    -vf "scale=360:-1,tile=$GRID:padding=12:margin=12:color=#F3F0E8" \
    -frames:v 1 -update 1 "$PROJECT_DIR/preview/montage-$PROFILE.png"

  # Motion sheet: one row per scene, 3 frames (20% / 55% / 90%) — used to verify
  # that graphics actually progress inside each scene (dynamic-cases acceptance step 2).
  MOTION_TIMES=$(python3 - "$PROJECT_DIR" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
path = root / "audio" / "durations.json"
if path.exists():
    segments = json.loads(path.read_text())["segments"]
else:
    sb = json.loads((root / "content" / "storyboard.json").read_text())
    segments = [{"start": 4 + i * 8, "duration": 8} for i in range(len(sb["segments"]))]
fractions = (0.2, 0.55, 0.9)
print(" ".join(f"{s['start'] + s['duration'] * f:.3f}" for s in segments for f in fractions))
PY
  )
  rm -f "$FRAME_DIR"/*.png
  INDEX=1
  for T in $MOTION_TIMES; do
    ffmpeg -y -loglevel error -ss "$T" -i "$OUTPUT" -frames:v 1 "$FRAME_DIR/f-$INDEX.png"
    INDEX=$((INDEX + 1))
  done
  ROWS=$(( (INDEX - 1) / 3 ))
  ffmpeg -y -loglevel error -framerate 1 -i "$FRAME_DIR/f-%d.png" \
    -vf "scale=300:-1,tile=3x$ROWS:padding=10:margin=10:color=#F3F0E8" \
    -frames:v 1 -update 1 "$PROJECT_DIR/preview/motion-$PROFILE.png"
done

if [[ "$PROFILE_FILTER" == "all" ]]; then
  python3 "$SCRIPT_DIR/verify_output.py" "$PROJECT_DIR"
fi
echo "Built review videos in $PROJECT_DIR/renders"
