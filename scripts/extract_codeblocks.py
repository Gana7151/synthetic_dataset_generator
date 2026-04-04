import re

def extract_python_blocks(markdown_text):
    # Find all python blocks
    # regex matches: ```python\n ... \n```
    blocks = re.findall(r'```python\n(.*?)\n```', markdown_text, flags=re.DOTALL)
    return blocks

with open(r"f:\combined\gana_combined\FIX_GUIDE_28PAGE_PDF.md", "r", encoding="utf-8") as f:
    guide1 = f.read()

with open(r"f:\combined\gana_combined\FIX_GUIDE_PAGES_12_14_15_17_SUPPLEMENT.md", "r", encoding="utf-8") as f:
    guide2 = f.read()

blocks1 = extract_python_blocks(guide1)
blocks2 = extract_python_blocks(guide2)

# Which blocks contain the functions we need?
# We can just iterate through all blocks. If a block starts with `def inject_` or `def compute_` we take it.
funcs = []

for b in blocks1 + blocks2:
    if b.startswith("def inject_") or b.startswith("def compute_") or b.startswith("def generate_vehicle_dep") or b.startswith("PREPARER_NAMES") or b.startswith("VEHICLE_POOL"):
        funcs.append(b)

injected_code = "\n\n".join(funcs)

with open(r"f:\combined\gana_combined\generate_tax_pdf.py", "r", encoding="utf-8") as f:
    code = f.read()

# We need to replace the old injected functions (which were truncated)
# We know where they start and end. They start at `def inject_ca540_nodes` and end before `def recompute_derived_fields`
start_marker = "def inject_ca540_nodes"
end_marker = "def recompute_derived_fields"

if start_marker in code and end_marker in code:
    pre = code.split(start_marker)[0]
    post = end_marker + code.split(end_marker, 1)[1]
    
    new_code = pre + injected_code + "\n\n" + post
    
    with open(r"f:\combined\gana_combined\generate_tax_pdf.py", "w", encoding="utf-8") as f:
        f.write(new_code)
    print("Re-injected functions successfully.")
else:
    print("Could not find markers.")
