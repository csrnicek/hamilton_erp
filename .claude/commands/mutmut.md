# Run mutation testing on lifecycle.py
# Usage: /mutmut
# Introduces small bugs into the code and checks if tests catch them.
# Any "surviving" mutant means your tests missed a bug.
# Install first: pip install mutmut --break-system-packages
# This is slow (~20 min) — run only at major checkpoints.

cd ~/hamilton_erp && mutmut run --paths-to-mutate hamilton_erp/lifecycle.py,hamilton_erp/locks.py && mutmut results
