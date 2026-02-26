# Prompting Techniques

This lab demonstrates different prompting techniques applied to the SAME software engineering task: i) debugging a buggy code, ii) debugging intermittent 502 errors.

## Files
- baseline_direct.py        : Single-shot direct prompt
- few_shot.py               : Few-shot prompting
- role_based.py             : Role-based (SRE) prompting
- hypothesis_driven.py      : Hypothesis-first debugging
- least_to_most.py          : Least-to-most decomposition (core)
- generate_then_verify.py   : Generate then critique

## Setup
1. Install Ollama and run it locally
2. Install dependencies:
   pip install -r requirements.txt

## Run
python baseline_direct.py

Compare outputs across scripts and analyze correctness, safety, and reasoning.
