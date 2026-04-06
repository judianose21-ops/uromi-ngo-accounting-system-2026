#!/usr/bin/env python3
# Fix the main.py file by removing corrupted lines and adding proper startup code

with open('main.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Find where the corruption starts (look for lines with spaces between chars)
clean_lines = []
for i, line in enumerate(lines):
    # Stop before the corrupted section (should be around line 2330)
    if i >= 2329:
        break
    clean_lines.append(line)

# Ensure the last line ends with proper content
if clean_lines and not clean_lines[-1].endswith('\n'):
    clean_lines[-1] += '\n'

# Add the proper startup code
startup_code = '''
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''

# Write the fixed file
with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(clean_lines)
    f.write(startup_code)

print("✓ Fixed main.py")
