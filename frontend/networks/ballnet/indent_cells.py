import re
from pathlib import Path

qmd_path = Path("inference.qmd")
with open(qmd_path, "r") as f:
    lines = f.readlines()

def indent_cell(cell_header):
    inside = False
    for i, line in enumerate(lines):
        if line.startswith(cell_header):
            # found the start of the cell
            
            # Look for the python code block
            for j in range(i+1, len(lines)):
                if lines[j].startswith("```{python}"):
                    # Insert the if statement
                    lines.insert(j+1, "if RUN_HISTORICAL_EVALUATION:\n")
                    
                    # Indent until ```
                    k = j + 2
                    while k < len(lines) and not lines[k].startswith("```"):
                        if lines[k].strip() != "":
                            lines[k] = "    " + lines[k]
                        k += 1
                    
                    # Add an else block at the end
                    lines.insert(k, "else:\n    print('Skipping historical evaluation...')\n")
                    return

headers_to_indent = [
    "## 4 · Season Ranges & Sliding Windows",
    "## 6 · Test Set Evaluation",
    "### 7a · Learning Curves",
    "### 7b · Model Benchmark Comparison",
    "### 7c · Predicted vs. Actual",
    "### 7d · Per-Statistic Error Bars",
    "## 8 · Case Study — Out-of-Sample Prop Pick'em",
    "## 9 · Summary Table",
    "## 14 · Conformal Calibration (Empirical Residuals)"
]

for header in headers_to_indent:
    indent_cell(header)

with open(qmd_path, "w") as f:
    f.writelines(lines)
print("Successfully indented cells.")
