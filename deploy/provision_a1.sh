#!/bin/bash
# =============================================================
# provision_a1.sh — poll for A1 Ampere capacity and create
# instance as soon as a slot is available.
#
# Prerequisites:
#   brew install oci-cli
#   oci setup config
#
# Fill in the variables below before running.
# Run on your Mac: chmod +x provision_a1.sh && ./provision_a1.sh
# =============================================================

# -----------------------------------------------------------
# CONFIGURE THESE before running
# -----------------------------------------------------------

# Your compartment OCID — OCI console → Identity → Compartments
# (root compartment OCID = your tenancy OCID)
COMPARTMENT_ID="ocid1.tenancy.oc1..aaaaaaaac2zj6u6ozs4pllbnlvuhjs2itcbaavedfgwxfmbiu34ugevowuta"

# Availability domain to try — find with:
#   oci iam availability-domain list --compartment-id <tenancy_ocid>
# Try each AD until one works: e.g. AD-1, AD-2, AD-3
AVAILABILITY_DOMAIN="Chlz:AP-SYDNEY-1-AD-1"   # e.g. "XgSu:AP-SYDNEY-1-AD-1"

# Subnet OCID — Networking → VCNs → your VCN → Subnets → Public Subnet
SUBNET_ID="ocid1.subnet.oc1.ap-sydney-1.aaaaaaaawutzmyzryzwfvgjwv7pimifdlmbvdcqxhe7eqchhq7z2cxivb2ya"

# Your SSH public key (the one you downloaded from OCI)
SSH_PUBLIC_KEY="$(cat ~/.ssh/oracle_fbc.key.pub)"

# Ubuntu 22.04 aarch64 image OCID for your region — find with:
#   oci compute image list --compartment-id <compartment> \
#     --operating-system "Canonical Ubuntu" \
#     --operating-system-version "22.04" \
#     --shape "VM.Standard.A1.Flex" \
#     --query 'data[0].id' --raw-output
IMAGE_ID="ocid1.image.oc1.ap-sydney-1.aaaaaaaalfohw3huhurr4z755x7r5kjwnjn2u3z7widkatzxlfzxgg5n6zda"

INSTANCE_NAME="foodbodyconnection"
RETRY_INTERVAL=900   # seconds between attempts (15 minutes)

# -----------------------------------------------------------
# Polling loop
# -----------------------------------------------------------
echo "Polling for A1 capacity every ${RETRY_INTERVAL}s — Ctrl+C to stop."
echo ""

while true; do
    echo "[$(date '+%H:%M:%S')] Attempting to create instance..."

    RESULT=$(oci compute instance launch \
        --compartment-id "$COMPARTMENT_ID" \
        --availability-domain "$AVAILABILITY_DOMAIN" \
        --shape "VM.Standard.A1.Flex" \
        --shape-config '{"ocpus": 2, "memoryInGBs": 12}' \
        --image-id "$IMAGE_ID" \
        --subnet-id "$SUBNET_ID" \
        --display-name "$INSTANCE_NAME" \
        --ssh-authorized-keys-file <(echo "$SSH_PUBLIC_KEY") \
        --assign-public-ip true \
        2>&1)

    if echo "$RESULT" | grep -q '"lifecycle-state": "PROVISIONING"'; then
        echo ""
        echo "SUCCESS — instance is provisioning!"
        echo "$RESULT" | grep '"id"' | head -1
        echo ""
        echo "Check progress: OCI console → Compute → Instances"
        echo "Once running, follow oracle_guide.sh to set it up."
        break
    else
        ERROR=$(echo "$RESULT" | grep -o '"message": "[^"]*"' | head -1)
        echo "  No capacity yet: $ERROR"
        echo "  Retrying in ${RETRY_INTERVAL}s..."
        sleep $RETRY_INTERVAL
    fi
done
