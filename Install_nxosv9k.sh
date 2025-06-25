#!/bin/bash

# --- Configuration ---
IMAGE_VERSION="9.3.5"
IMAGE_NAME="nxosv-final.${IMAGE_VERSION}"
TARGET_DIR="/opt/unetlab/addons/qemu/nxosv9k-${IMAGE_VERSION}"

# --- Functions ---
function fail {
    echo "[ERROR] $1"
    exit 1
}

# --- Input Validation ---
if [[ -z "$1" ]]; then
    echo "Usage: $0 <path-to-image-file.qcow2|.vmdk|.ova>"
    exit 1
fi

INPUT_IMAGE="$1"
EXT="${INPUT_IMAGE##*.}"

echo "[*] Creating directory: $TARGET_DIR"
mkdir -p "$TARGET_DIR" || fail "Failed to create target directory"

cd "$TARGET_DIR" || fail "Could not change to target directory"

case "$EXT" in
  qcow2)
    echo "[*] Copying QCOW2 image"
    cp "$INPUT_IMAGE" virtioa.qcow2 || fail "Failed to copy QCOW2 image"
    ;;
  vmdk)
    echo "[*] Converting VMDK to QCOW2"
    qemu-img convert -f vmdk -O qcow2 "$INPUT_IMAGE" virtioa.qcow2 || fail "qemu-img failed"
    ;;
  ova)
    echo "[*] Extracting OVA"
    tar -xvf "$INPUT_IMAGE" || fail "Failed to extract OVA"
    VMDK_FILE=$(ls *.vmdk | head -1)
    [[ -f "$VMDK_FILE" ]] || fail "No VMDK found in OVA"
    echo "[*] Converting $VMDK_FILE to QCOW2"
    qemu-img convert -f vmdk -O qcow2 "$VMDK_FILE" virtioa.qcow2 || fail "qemu-img failed"
    ;;
  *)
    fail "Unsupported file extension: $EXT"
    ;;
esac

echo "[*] Fixing permissions"
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions

echo "[✓] NX-OSv9k $IMAGE_VERSION installed successfully at $TARGET_DIR"
