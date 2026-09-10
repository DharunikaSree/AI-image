"""
Check KaggleHub / dataset metadata for sleeve, neckline, and other detailed attributes.
"""
import json
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def check_detailed_attributes():
    json_path = PROJECT_ROOT / "data" / "deepfashion_metadata.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"deepfashion_metadata.json has {len(data)} items.")
        if isinstance(data, list) and data:
            print(f"Sample item (index 0):", json.dumps(data[0], indent=2))
        elif isinstance(data, dict) and data:
            sample_key = list(data.keys())[0]
            print(f"Sample item ({sample_key}):", json.dumps(data[sample_key], indent=2))

    # Check for keywords in names: sleeve, neck, pattern
    csv_path = PROJECT_ROOT / "data" / "deepfashion_catalog.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        has_sleeve = df['name'].fillna('').str.contains('sleeve|sleeveless', case=False).sum()
        has_neck = df['name'].fillna('').str.contains('neck|collar|v-neck|round neck', case=False).sum()
        print(f"Products with 'sleeve' in name: {has_sleeve}/{len(df)} ({has_sleeve/len(df)*100:.1f}%)")
        print(f"Products with 'neck' in name: {has_neck}/{len(df)} ({has_neck/len(df)*100:.1f}%)")

if __name__ == "__main__":
    check_detailed_attributes()
