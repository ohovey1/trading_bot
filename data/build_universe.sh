#!/usr/bin/env bash
# Build ticker universe from IWM holdings filtered to $300M–$2B market cap.
# Outputs data/tickers.json
#
# Usage: bash data/build_universe.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TICKERS_JSON="$SCRIPT_DIR/tickers.json"
TICKERS_BAK="$SCRIPT_DIR/tickers.json.bak"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

MARKET_CAP_MIN=300000000
MARKET_CAP_MAX=2000000000
TARGET_MAX=150

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
COOKIE_JAR="$TMP_DIR/yf_cookies.txt"

echo "=== Step 1: Backup current tickers.json ==="
cp "$TICKERS_JSON" "$TICKERS_BAK"

echo ""
echo "=== Step 2: Download IWM holdings ==="
IWM_CSV="$TMP_DIR/iwm_holdings.csv"
curl -s -L \
  -H "User-Agent: $UA" \
  -H "Referer: https://www.ishares.com/" \
  "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund" \
  -o "$IWM_CSV"

# Extract the header line index (first line containing "Ticker" as first field)
HEADER_LINE=$(grep -n 'Ticker' "$IWM_CSV" | grep -v 'iShares' | head -1 | cut -d: -f1 || true)
if [ -z "$HEADER_LINE" ]; then
  echo "ERROR: Could not find Ticker header in IWM CSV"
  exit 1
fi
echo "Header at line $HEADER_LINE"

# Extract pure-alpha tickers from first column (after header)
# CSV format: "TICKER","Name",...
TICKERS_FILE="$TMP_DIR/candidates.txt"
tail -n +"$((HEADER_LINE + 1))" "$IWM_CSV" | \
  awk -F',' '{gsub(/"/, "", $1); t=$1; gsub(/[[:space:]]/, "", t); print t}' | \
  grep -E '^[A-Z]+$' | \
  sort -u > "$TICKERS_FILE"

CANDIDATE_COUNT=$(wc -l < "$TICKERS_FILE" | tr -d ' ')
echo "Extracted $CANDIDATE_COUNT pure-alpha tickers from IWM"

echo ""
echo "=== Step 3: Get Yahoo Finance crumb ==="
curl -s -c "$COOKIE_JAR" -b "CrunchCSRF=1" \
  -H "User-Agent: $UA" \
  -H "Accept: text/html,application/xhtml+xml" \
  -L "https://finance.yahoo.com/" -o /dev/null

CRUMB=$(curl -s -b "$COOKIE_JAR" \
  -H "User-Agent: $UA" \
  "https://query2.finance.yahoo.com/v1/test/getcrumb")

if echo "$CRUMB" | grep -q '"error"'; then
  echo "ERROR: Failed to get crumb: $CRUMB"
  exit 1
fi
echo "Crumb: $CRUMB"

echo ""
echo "=== Step 4: Fetch market caps in batches ==="
CAPS_DIR="$TMP_DIR/caps"
mkdir -p "$CAPS_DIR"

BATCH_SIZE=100
BATCH_NUM=0
BATCH_FILE="$TMP_DIR/batch_$BATCH_NUM.txt"

# Split candidates into batches
while IFS= read -r ticker; do
  LINE_COUNT=$(wc -l < "$BATCH_FILE" 2>/dev/null || echo 0)
  if [ "$LINE_COUNT" -ge "$BATCH_SIZE" ]; then
    BATCH_NUM=$((BATCH_NUM + 1))
    BATCH_FILE="$TMP_DIR/batch_$BATCH_NUM.txt"
  fi
  echo "$ticker" >> "$BATCH_FILE"
done < "$TICKERS_FILE"

TOTAL_BATCHES=$((BATCH_NUM + 1))
echo "Processing $TOTAL_BATCHES batches..."

for i in $(seq 0 $BATCH_NUM); do
  BATCH_FILE="$TMP_DIR/batch_$i.txt"
  if [ ! -f "$BATCH_FILE" ]; then continue; fi

  SYMBOLS=$(paste -sd ',' "$BATCH_FILE")
  ENCODED_SYMBOLS=$(node -e "process.stdout.write(encodeURIComponent('$SYMBOLS'))" 2>/dev/null || \
                    python3 -c "import urllib.parse; print(urllib.parse.quote('$SYMBOLS'))" 2>/dev/null || \
                    echo "$SYMBOLS" | sed 's/,/%2C/g')

  echo -n "  batch $((i+1))/$TOTAL_BATCHES..."

  curl -s -b "$COOKIE_JAR" \
    -H "User-Agent: $UA" \
    "https://query2.finance.yahoo.com/v7/finance/quote?symbols=${ENCODED_SYMBOLS}&fields=marketCap,symbol&crumb=${CRUMB}" \
    -o "$CAPS_DIR/batch_$i.json" 2>/dev/null

  # Count how many have market caps
  GOT=$(node -e "
    const d = require('fs').readFileSync('$CAPS_DIR/batch_$i.json','utf8');
    try {
      const j = JSON.parse(d);
      const r = (j.quoteResponse||{}).result||[];
      console.log(r.filter(q=>q.marketCap!=null).length);
    } catch(e) { console.log(0); }
  " 2>/dev/null || echo 0)

  BATCH_SIZE_ACTUAL=$(wc -l < "$BATCH_FILE" | tr -d ' ')
  echo " $GOT/$BATCH_SIZE_ACTUAL have marketCap"

  if [ "$i" -lt "$BATCH_NUM" ]; then
    sleep 0.3
  fi
done

echo ""
echo "=== Step 5: Build filtered universe ==="
# Load current tickers for DB-priority logic
CURRENT_TICKERS=$(cat "$TICKERS_JSON")

node -e "
const fs = require('fs');
const path = require('path');

const MARKET_CAP_MIN = $MARKET_CAP_MIN;
const MARKET_CAP_MAX = $MARKET_CAP_MAX;
const TARGET_MAX = $TARGET_MAX;

// Load current tickers
const currentTickers = $CURRENT_TICKERS;
const currentSet = new Set(currentTickers);

// Load all candidates
const candidates = fs.readFileSync('$TICKERS_FILE', 'utf8')
  .split('\n').map(t=>t.trim()).filter(Boolean);

// Parse all market cap data
const caps = {};
const capsFiles = fs.readdirSync('$CAPS_DIR').filter(f=>f.endsWith('.json'));
for (const f of capsFiles) {
  try {
    const raw = fs.readFileSync(path.join('$CAPS_DIR', f), 'utf8');
    const j = JSON.parse(raw);
    for (const q of (j?.quoteResponse?.result || [])) {
      if (q.symbol && q.marketCap != null) {
        caps[q.symbol] = q.marketCap;
      }
    }
  } catch(e) {}
}

console.log('Market caps fetched: ' + Object.keys(caps).length + '/' + candidates.length);

// Filter to range
const inRange = candidates.filter(t =>
  caps[t] != null && caps[t] >= MARKET_CAP_MIN && caps[t] <= MARKET_CAP_MAX
);
console.log('In \$300M–\$2B range: ' + inRange.length);

// Prioritize existing tickers, then add new ones
const haveData = inRange.filter(t => currentSet.has(t));
const newTickers = inRange.filter(t => !currentSet.has(t));
console.log('Already in current universe: ' + haveData.length);
console.log('New tickers: ' + newTickers.length);

const universe = [...haveData];
const slots = TARGET_MAX - universe.length;
if (slots > 0) universe.push(...newTickers.slice(0, slots));
const sorted = [...new Set(universe)].sort();

console.log('Final universe: ' + sorted.length + ' tickers');

if (sorted.length === 0) {
  console.error('ERROR: universe is empty — aborting');
  process.exit(1);
}

// Stats
const ucaps = sorted.map(t=>caps[t]).filter(Boolean);
if (ucaps.length) {
  const lo = Math.min(...ucaps), hi = Math.max(...ucaps);
  console.log('Cap range: \$' + (lo/1e6).toFixed(0) + 'M – \$' + (hi/1e6).toFixed(0) + 'M');
}

// Changes vs current
const newAdded = sorted.filter(t => !currentSet.has(t));
const removed = currentTickers.filter(t => !new Set(sorted).has(t));
console.log('Added: ' + newAdded.length + (newAdded.length ? ' (' + newAdded.join(', ') + ')' : ''));
console.log('Removed: ' + removed.length + (removed.length ? ' (' + removed.join(', ') + ')' : ''));

fs.writeFileSync('$TICKERS_JSON', JSON.stringify(sorted, null, 2));
console.log('\nWrote ' + sorted.length + ' tickers to $TICKERS_JSON');
console.log('\nFinal universe:');
console.log(sorted.join(', '));
" 2>&1

echo ""
echo "=== Done ==="
