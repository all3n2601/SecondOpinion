"""Optional AI layer: turns a report sentence into a query plan that our own code validates and runs.

The AI never states a number, never sets a verdict and never answers from memory. It only chooses
among the whitelisted operations in `plan.py`; `executor.py` runs the plan with pandas on the real
release, and `verdict.py` judges the result. Off unless configured (see `config.py`).
"""
