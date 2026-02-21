
filename = 'dashboard_dump_frame_2_frameHub.html'
keywords = ['Garantie', 'LCDV', 'Überprüfungsaktion', 'VF3EBRHD8BZ038648', 'Garantieende', 'Garantiebeginn']

try:
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    print(f"Analyzing {filename} ({len(lines)} lines)...")
    
    for i, line in enumerate(lines):
        for k in keywords:
            if k in line:
                print(f"MATCH [{k}] at line {i+1}:")
                # Print context (2 lines before and after)
                start = max(0, i-2)
                end = min(len(lines), i+3)
                for j in range(start, end):
                    print(f"  {j+1}: {lines[j].strip()}")
                print("-" * 40)

except Exception as e:
    print(f"Error: {e}")
