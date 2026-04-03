#!/bin/bash
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)

BSEC_INC="$ROOT_DIR/bsec/algo/bsec_IAQ/inc"
BSEC_LIB="$ROOT_DIR/bsec/algo/bsec_IAQ/bin/RaspberryPi/PiFour_Armv8/libalgobsec.a"
SRC_DIR="$SCRIPT_DIR"
OUTPUT="$ROOT_DIR/src/libbsec_wrapper.so"
CONFIG_DIR="$ROOT_DIR/bsec/algo/bsec_IAQ/config/bme680/bme680_iaq_33v_3s_28d"
CONFIG_SRC="$CONFIG_DIR/bsec_iaq.c"


INCLUDE_PATHS="-I$BSEC_INC -I$CONFIG_DIR"

echo "Building BSEC bridge..."
echo "  BSEC include : $BSEC_INC"
echo "  BSEC lib     : $BSEC_LIB"
echo "  Output       : $OUTPUT"
echo "  Config       : $CONFIG_DIR"

gcc \
    -shared \
    -fPIC \
    -o "$OUTPUT" \
    "$SRC_DIR/bsec_bridge.c" \
    "$CONFIG_SRC" \
    $INCLUDE_PATHS \
    "$BSEC_LIB" \
    -lm

echo "Done: $OUTPUT"