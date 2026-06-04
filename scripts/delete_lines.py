from pathlib import Path

boot = Path("scripts/bootstrap.py")
lines = boot.read_text().split("\n")

# Delete line 545
lines[545-1] = ""
# Delete line 605
lines[605-1] = ""
# Delete line 1684 (but maybe c_y is inside a multiple assignment. I'll just blank it)
lines[1684-1] = lines[1684-1].replace(" c_y =", "")
# Delete 1879
lines[1879-1] = ""
# Delete 1897
lines[1897-1] = ""

boot.write_text("\n".join(lines))
print("Deleted lines.")
