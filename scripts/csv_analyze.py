"""
csv_analyze.py - CSV データ分析スクリプト

入力: JSON (stdin)
  {
    "csv_content": "name,age,score\nAlice,25,88\nBob,30,72",
    "column": "score"          // 省略可
  }

出力: JSON (stdout)
  {
    "shape": {"rows": 2, "columns": 3},
    "columns": ["name", "age", "score"],
    "dtypes": {...},
    "missing_values": {...},
    "summary": {...},
    "column_detail": {...}    // column 指定時のみ
  }
"""

import io
import json
import sys


def main(params: dict) -> dict:
    import pandas as pd

    csv_content: str = params["csv_content"]
    column: str | None = params.get("column")

    df = pd.read_csv(io.StringIO(csv_content))

    result: dict = {
        "shape": {"rows": int(len(df)), "columns": int(len(df.columns))},
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": {col: int(df[col].isna().sum()) for col in df.columns},
        "summary": json.loads(df.describe(include="all").fillna("").to_json()),
    }

    if column:
        if column not in df.columns:
            result["error"] = f"Column '{column}' not found. Available: {list(df.columns)}"
        else:
            col_data = df[column]
            result["column_detail"] = {
                "name": column,
                "dtype": str(col_data.dtype),
                "unique_count": int(col_data.nunique()),
                "null_count": int(col_data.isna().sum()),
                "sample_values": col_data.dropna().head(10).tolist(),
            }
            # 数値列の場合は追加統計
            if pd.api.types.is_numeric_dtype(col_data):
                result["column_detail"].update({
                    "min": float(col_data.min()),
                    "max": float(col_data.max()),
                    "mean": float(col_data.mean()),
                    "median": float(col_data.median()),
                    "std": float(col_data.std()),
                })

    return result


if __name__ == "__main__":
    params = json.load(sys.stdin)
    result = main(params)
    print(json.dumps(result, ensure_ascii=False))
