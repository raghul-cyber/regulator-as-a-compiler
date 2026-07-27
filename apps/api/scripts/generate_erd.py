import os
import sys

# Ensure apps/api is in Python path when running this script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models import *  # Import all models to register mappers
from app.models.base import Base

def simplify_type(col_type):
    t_str = str(col_type).upper()
    if "UUID" in t_str: return "UUID"
    if "VECTOR" in t_str: return "Vector"
    if "INT" in t_str: return "Integer"
    if "FLOAT" in t_str or "NUMERIC" in t_str or "DECIMAL" in t_str: return "Float"
    if "BOOL" in t_str: return "Boolean"
    if "JSON" in t_str: return "JSONB"
    if "ARRAY" in t_str: return "Array"
    if "TIMESTAMP" in t_str or "DATE" in t_str or "TIME" in t_str: return "Timestamp"
    if "ENUM" in t_str: return "Enum"
    return "String"

def generate_mermaid_erd():
    mappers = sorted(Base.registry.mappers, key=lambda m: m.local_table.name)
    
    print("erDiagram")
    
    relationships = []
    
    for mapper in mappers:
        table = mapper.local_table
        table_name = table.name
        print(f"    {table_name} {{")
        for col in table.columns:
            col_name = col.name
            type_str = simplify_type(col.type)
            keys = []
            if col.primary_key:
                keys.append("PK")
            if col.foreign_keys:
                keys.append("FK")
            key_str = " ".join(keys)
            
            line = f"        {type_str} {col_name}"
            if key_str:
                line += f" {key_str}"
            print(line)
            
            for fk in col.foreign_keys:
                target_table = fk.column.table.name
                relationships.append((target_table, table_name, col_name))
                
        print("    }")
        
    print("")
    # Sort and deduplicate relationships
    seen = set()
    for target, source, col in sorted(relationships):
        rel_key = (target, source)
        if rel_key not in seen:
            seen.add(rel_key)
            print(f'    {target} ||--o{{ {source} : "references"')

if __name__ == "__main__":
    generate_mermaid_erd()
