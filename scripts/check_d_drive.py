"""
Check directories and files on D drive.
"""
import os
from pathlib import Path

p = Path("D:/")
print("Top-level on D drive:", [str(x) for x in p.iterdir()])

cache_p = Path("D:/kagglehub_cache")
if cache_p.exists():
    for root, dirs, files in os.walk(cache_p):
        print(f"Directory: {root} -> {len(files)} files, {len(dirs)} subdirs")
        if files:
            print(f"  Sample files: {files[:5]}")
else:
    print("D:/kagglehub_cache does not exist.")
