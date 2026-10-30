# Fixed profiling script. It is executed INSIDE the sandbox (pandas is installed there, not in the backend).
# It prints exactly one JSON line at the end; the orchestrator parses that line.
import glob
import json
import os
import sys

import pandas as pd

# Discover all valid data files in /data
all_files = sorted(f for f in glob.glob("/data/*") if os.path.isfile(f) and not f.endswith(".json_profile"))
# If original named files exist alongside raw.* and clean.csv, prioritize the original named files so user sees original filenames
user_files = [f for f in all_files if not os.path.basename(f).startswith("raw.") and os.path.basename(f) != "clean.csv"]
non_raw_files = [f for f in all_files if not os.path.basename(f).startswith("raw.")]
paths = user_files if user_files else (non_raw_files if non_raw_files else all_files)

if not paths:
    print("no input file found in /data", file=sys.stderr)
    sys.exit(2)


def num(x):
    return None if pd.isna(x) else float(x)


def profile_single_file(path: str) -> dict | None:
    ext = os.path.splitext(path)[1].lower()
    df = None
    loaded_with = ""

    if ext in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(path)
            loaded_with = f"pd.read_excel('{path}')"
        except Exception as e:
            print(f"error reading {path}: {e}", file=sys.stderr)
    elif ext == ".json":
        try:
            df = pd.read_json(path)
            loaded_with = f"pd.read_json('{path}')"
        except ValueError:
            try:
                df = pd.read_json(path, lines=True)
                loaded_with = f"pd.read_json('{path}', lines=True)"
            except Exception:
                pass
    else:
        # Fast C engine first (optimal for files up to 100MB)
        for enc in ("utf-8-sig", "latin-1", "utf-8"):
            try:
                df = pd.read_csv(path, encoding=enc)
                loaded_with = f"pd.read_csv('{path}', encoding='{enc}')"
                break
            except Exception:
                pass
        if df is None:
            for enc in ("utf-8-sig", "latin-1", "utf-8"):
                try:
                    df = pd.read_csv(path, sep=None, engine="python", encoding=enc)
                    loaded_with = f"pd.read_csv('{path}', sep=None, engine='python', encoding='{enc}')"
                    break
                except (UnicodeDecodeError, Exception):
                    continue

    if df is None:
        return None

    columns = []
    for name in list(df.columns)[:80]:
        s = df[name]
        info = {
            "name": str(name),
            "dtype": str(s.dtype),
            "nulls": int(s.isna().sum()),
            "unique": int(s.nunique(dropna=True)),
            "samples": [str(v)[:60] for v in s.dropna().astype(str).unique()[:8]],
        }
        if pd.api.types.is_numeric_dtype(s):
            info.update(min=num(s.min()), max=num(s.max()), mean=num(s.mean()))
        elif info["unique"] <= 500:
            normalised = s.dropna().astype(str).str.strip().str.lower().nunique()
            info["unique_after_normalizing"] = int(normalised)
        columns.append(info)

    try:
        duplicates = int(df.duplicated().sum())
    except TypeError:
        duplicates = None

    return {
        "file": os.path.basename(path),
        "path": path,
        "loaded_with": loaded_with,
        "rows": int(len(df)),
        "columns_total": int(df.shape[1]),
        "duplicate_rows": duplicates,
        "columns": columns,
        "head": [{str(k): str(v)[:60] for k, v in rec.items()} for rec in df.head(5).to_dict("records")],
    }


file_profiles = []
for p in paths:
    prof = profile_single_file(p)
    if prof:
        file_profiles.append(prof)

if not file_profiles:
    print("could not parse any input file in /data", file=sys.stderr)
    sys.exit(3)

primary = file_profiles[0]
if len(file_profiles) > 1:
    combined = {
        "multi_file": True,
        "total_files": len(file_profiles),
        "files": [fp["file"] for fp in file_profiles],
        "file_profiles": file_profiles,
        # Primary file fields for backward compatibility:
        "file": primary["file"],
        "loaded_with": primary["loaded_with"],
        "rows": primary["rows"],
        "columns_total": primary["columns_total"],
        "columns": primary["columns"],
        "head": primary["head"],
        "duplicate_rows": primary["duplicate_rows"],
    }
    print(f"profiled {len(file_profiles)} datasets in /data: {', '.join(fp['file'] for fp in file_profiles)}")
    print(json.dumps(combined, ensure_ascii=False))
else:
    combined = dict(primary)
    combined["multi_file"] = False
    combined["total_files"] = 1
    combined["files"] = [primary["file"]]
    combined["file_profiles"] = [dict(primary)]
    print(f"profiled {primary['rows']} rows x {primary['columns_total']} columns")
    print(json.dumps(combined, ensure_ascii=False))
