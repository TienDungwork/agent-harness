#!/bin/bash
echo "Testing offline test suite..."
python3 -m pytest -q tests/test_readonly.py

echo -e "\nTesting run.py with offline mock..."
PYTEST_CURRENT_TEST=1 python3 eval/run.py --judge > /dev/null

echo -e "\nChecking golden-30.md..."
head -n 12 eval/results/golden-30.md
