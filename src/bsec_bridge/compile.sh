#!/bin/bash
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)

BSEC_INC="$ROOT_DIR/bsec/algo/bsec_IAQ/inc"
BSEC_LIB="$ROOT_DIR/bsec/algo/bsec_IAQ/bin/RaspberryPi/PiFour_Armv8/libalgobsec.a"
SRC_DIR="$SCRIPT_DIR"
OUTPUT="$ROOT_DIR/src/libbsec_wrapper.so"

echo "Building BSEC bridge..."
echo "  BSEC include : $BSEC_INC"
echo "  BSEC lib     : $BSEC_LIB"
echo "  Output       : $OUTPUT"

gcc \
    -shared \
    -fPIC \
    -o "$OUTPUT" \
    "$SRC_DIR/bsec_wrapper.c" \
    -I"$BSEC_INC" \
    "$BSEC_LIB" \
    -lm

echo "Done: $OUTPUT"