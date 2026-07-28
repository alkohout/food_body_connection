#!/usr/bin/env bash
# Connect to the Food Body Connection server (Oracle Cloud).
# Uses the "fbc" alias from ~/.ssh/config; falls back to the literal host if absent.
if ssh -G fbc 2>/dev/null | grep -q "^hostname 159.13.61.101$"; then
    exec ssh fbc "$@"
else
    exec ssh ubuntu@159.13.61.101 "$@"
fi
