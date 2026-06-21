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

# All availability domains to try in rotation
AVAILABILITY_DOMAINS=(
    "Chlz:AP-SYDNEY-1-AD-1"
    "Chlz:AP-SYDNEY-1-AD-2"
    "Chlz:AP-SYDNEY-1-AD-3"
)

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
RETRY_INTERVAL=300   # seconds between attempts (5 minutes, rotating across ADs)

# -----------------------------------------------------------
# Polling loop — rotates through all availability domains
# -----------------------------------------------------------
echo "Polling for A1 capacity every ${RETRY_INTERVAL}s across ${#AVAILABILITY_DOMAINS[@]} ADs — Ctrl+C to stop."
echo ""

AD_INDEX=0
while true; do
    AD="${AVAILABILITY_DOMAINS[$AD_INDEX]}"
    echo "[$(date '+%H:%M:%S')] Trying $AD ..."

    RESULT=$(oci compute instance launch \
        --compartment-id "$COMPARTMENT_ID" \
        --availability-domain "$AD" \
        --shape "VM.Standard.A1.Flex" \
        --shape-config '{"ocpus": 1, "memoryInGBs": 6}' \
        --image-id "$IMAGE_ID" \
        --subnet-id "$SUBNET_ID" \
        --display-name "$INSTANCE_NAME" \
        --ssh-authorized-keys-file <(echo "$SSH_PUBLIC_KEY") \
        --assign-public-ip true \
        2>&1)

    if echo "$RESULT" | grep -q '"lifecycle-state": "PROVISIONING"'; then
        echo ""
        echo "SUCCESS — instance is provisioning in $AD!"
        echo "$RESULT" | grep '"id"' | head -1
        echo ""
        echo "Check progress: OCI console → Compute → Instances"
        echo "Once running, follow oracle_guide.sh to set it up."
        break
    else
        ERROR=$(echo "$RESULT" | grep -o '"message": "[^"]*"' | head -1)
        echo "  No capacity: $ERROR"
        AD_INDEX=$(( (AD_INDEX + 1) % ${#AVAILABILITY_DOMAINS[@]} ))
        echo "  Retrying in ${RETRY_INTERVAL}s..."
        sleep $RETRY_INTERVAL
    fi
done
