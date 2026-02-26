
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatOllama(model="gpt-oss:120b-cloud", temperature=0.0)
system = SystemMessage(content="You are a senior backend engineer. Be precise and explicit. DONT Verbose.")

BUGGY_CODE = '''
def calculate_total(items, discount):
    total = 0
    for item in items:
        total += item["price"] * item["quantity"]
    if discount:
        total = total - discount
    return total
'''

prev = ""

steps = [
    "List all assumptions this code makes. No fixes.",
    "Which assumptions are unsafe in a real checkout system?",
    "Define correct behavior for flat vs percent discounts.",
    "Rewrite the function to satisfy the defined behavior."
]

for i, step in enumerate(steps, 1):
    prompt = f"""Step {i}: {step}

{BUGGY_CODE}

Previous output:
{prev}
"""
    resp = llm.invoke([system, HumanMessage(content=prompt)]).content
    print(f"\n=== STEP {i} ===\n{resp}")
    prev = resp
