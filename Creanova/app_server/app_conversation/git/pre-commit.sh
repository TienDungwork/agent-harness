#!/bin/bash
# This hook was installed by Creanova
# It calls the pre-commit script in the .Creanova directory

if [ -x ".Creanova/pre-commit.sh" ]; then
    source ".Creanova/pre-commit.sh"
    exit $?
else
    echo "Warning: .Creanova/pre-commit.sh not found or not executable"
    exit 0
fi
