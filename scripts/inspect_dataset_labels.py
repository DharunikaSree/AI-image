"""
Inspect label coverage across deepfashion_catalog.csv, SQLite fashion.db, and deepfashion_metadata.json
"""
import json
import sqlite3
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def inspect():
    csv_path = PROJECT_ROOT / "data" / "deepfashion_catalog.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        print("=" * 75)
        print(f"data/deepfashion_catalog.csv: {len(df)} rows")
        print("=" * 75)
        for col in df.columns:
            non_null = df[col].notna().sum()
            nunique = df[col].nunique()
            top_vals = df[col].value_counts().head(5).to_dict()
            print(f"[{col}] Non-null: {non_null}/{len(df)} ({non_null/len(df)*100:.1f}%) | Unique: {nunique}")
            print(f"   Top-5: {top_vals}\n")

    db_path = PROJECT_ROOT / "backend" / "fashion.db"
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(products);")
        columns = [row[1] for row in cursor.fetchall()]
        print("=" * 75)
        print(f"SQLite products table: {len(columns)} columns")
        print("=" * 75)
        for col in ["category", "subcategory", "style", "color", "pattern", "gender", "season"]:
            if col in columns:
                cursor.execute(f"SELECT {col}, COUNT(*) FROM products GROUP BY {col} ORDER BY COUNT(*) DESC LIMIT 8;")
                rows = cursor.fetchall()
                print(f"Column '{col}' top values in SQLite:")
                for val, cnt in rows:
                    print(f"   - {val}: {cnt}")
                print()

    summary_path = PROJECT_ROOT / "data" / "deepfashion_summary.json"
    if summary_path.exists():
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
        print("=" * 75)
        print("deepfashion_summary.json:")
        print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    inspect()
