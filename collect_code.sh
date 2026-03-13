#!/bin/bash
# Collect all code files into one txt
# Usage: ./collect_code.sh [output_file]

DIR="$(pwd)"
OUTPUT="${1:-raidio_full_code.txt}"

echo "📦 Collecting code from: $DIR"

# Clear output
: > "$OUTPUT"

# Header
{
    echo "================================================================"
    echo "  FULL CODE — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "  Source: $DIR"
    echo "================================================================"
    echo ""
} >> "$OUTPUT"

# Tree
echo "── STRUCTURE ──" >> "$OUTPUT"
find "$DIR" -not -path '*/__pycache__/*' -not -path '*/.git/*' \
    -not -name '*.wav' -not -name '*.mp3' -not -name '*.jpg' \
    -not -name '*.png' -not -name '*.pyc' \
    | sort >> "$OUTPUT"
echo "" >> "$OUTPUT"

# Collect text files
COUNT=0
find "$DIR" -type f \
    -not -path '*/__pycache__/*' \
    -not -path '*/.git/*' \
    \( -name '*.py' -o -name '*.html' -o -name '*.js' -o -name '*.css' \
       -o -name '*.json' -o -name '*.txt' -o -name '*.md' -o -name '*.sh' \
       -o -name '*.yml' -o -name '*.yaml' -o -name '*.toml' -o -name '*.cfg' \
       -o -name '*.env' -o -name '*.ini' \) \
    | sort | while read -r file; do

    # Skip output file
    [ "$(realpath "$file")" = "$(realpath "$OUTPUT")" ] 2>/dev/null && continue

    {
        echo "================================================================"
        echo "FILE: $file"
        echo "================================================================"
        echo ""
        cat "$file"
        echo ""
        echo ""
    } >> "$OUTPUT"

    echo "  ✅ $file"
done

LINES=$(wc -l < "$OUTPUT")
SIZE=$(du -h "$OUTPUT" | cut -f1)

echo ""
echo "✅ Done! Saved to: $OUTPUT"
echo "📊 Size: $SIZE, $LINES lines"
