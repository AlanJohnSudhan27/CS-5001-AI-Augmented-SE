# All Prompting Styles – Software Engineering Lab

Same task, multiple prompting styles.

Bug:
Order totals sometimes incorrect when discounts are applied.

Scripts:
01_direct_zero_shot.py      – baseline
02_few_shot.py              – few-shot
03_role_based.py            – role-based
04_hypothesis_driven.py     – hypothesis-first
05_constraint_first.py      – constraint-first
06_generate_then_verify.py  – generate + critique
07_least_to_most.py         – least-to-most (benchmark)

Run:
pip install -r requirements.txt
python 07_least_to_most.py
