import os
import re

def main():
    with open('README.md', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Validate Mermaid blocks
    mermaid_blocks = re.findall(r'```mermaid\n(.*?)```', content, re.DOTALL)
    print(f"Found {len(mermaid_blocks)} Mermaid diagram blocks:")
    for i, block in enumerate(mermaid_blocks, 1):
        lines = [l.strip() for l in block.strip().split('\n') if l.strip() and not l.strip().startswith('%%')]
        header = lines[0]
        print(f"  Diagram {i} ({header}): {len(lines)} lines -> OK")
        # Check basic syntax
        if 'erDiagram' in header:
            for line in lines[1:]:
                if '||--o{' not in line and '{' not in line and '}' not in line and not re.match(r'^\w+\s+\w+', line):
                    print(f"    WARNING: possible syntax issue in ERD line: {line}")
        elif 'graph' in header:
            for line in lines[1:]:
                if '-->' not in line and '---' not in line and '<-->' not in line:
                    print(f"    WARNING: possible syntax issue in graph line: {line}")

    # 2. Check internal file references
    links = re.findall(r'\]\(([^http#][^\)]+)\)|src=[\"\'](\./[^\"\']+)[\"\']', content)
    print("\nChecking internal file references:")
    for link_tuple in links:
        target = link_tuple[0] or link_tuple[1]
        target_path = target.lstrip('./').split('#')[0]
        exists = os.path.exists(target_path)
        print(f"  Target '{target}' -> Exists: {exists}")
        if not exists and not target.startswith('http'):
            print(f"    NOTE: Target file {target_path} is missing, let's ensure it exists!")

if __name__ == '__main__':
    main()
