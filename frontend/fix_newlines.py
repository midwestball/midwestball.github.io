with open("networks/ballnet/inference_v2.qmd", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "print(f'── EV Strategy Comparison Dashboard ──" in line:
        if i + 1 < len(lines) and lines[i+1].startswith("'):"):
            pass # wait
    if "Dashboard ──\n" in line and not "print" in line:
        pass
        
import re
with open("networks/ballnet/inference_v2.qmd", "r") as f:
    text = f.read()

text = text.replace("print(f'── EV Strategy Comparison Dashboard ──\n')", "print(f'── EV Strategy Comparison Dashboard ──\\n')")
text = text.replace("print(f'Actual ROI:  {naive_roi*100:+.1f}%\n')", "print(f'Actual ROI:  {naive_roi*100:+.1f}%\\n')")
text = text.replace("print(f'Actual ROI:  {conf_roi*100:+.1f}%\n')", "print(f'Actual ROI:  {conf_roi*100:+.1f}%\\n')")

with open("networks/ballnet/inference_v2.qmd", "w") as f:
    f.write(text)
