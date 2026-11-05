import sys

print("SYNTHETIC_TEST_FAILURE", file=sys.stderr)
raise SystemExit(7)
