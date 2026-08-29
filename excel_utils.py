"""
excel_utils.py

Lightweight, pandas-free Excel reader shared by the MOE dictionary plugins.
Ships alongside base_plugin.py — needs the same PyInstaller treatment
(--add-data "excel_utils.py:.") and the same copy-into-user-plugins-folder
handling that base_plugin.py already gets, so dynamically loaded plugins
can `from excel_utils import read_excel_as_dicts` at runtime.

Mimics the exact behavior the plugins relied on from pandas:
    pd.read_excel(path, dtype=str, engine="openpyxl").fillna("")
    df.columns = [c.strip() for c in df.columns]
    for _, row in df.iterrows():
        row.get("colname", "")

...but returns a plain list[dict[str, str]] instead of a DataFrame, so
every existing `row.get(...)` call in the plugins keeps working unchanged.
"""

from openpyxl import load_workbook


def _cell_to_str(value):
    """Normalize a raw openpyxl cell value the way pandas' dtype=str does:
    whole-number floats/ints render without a trailing '.0', None becomes
    an empty string (matching .fillna("")), everything else is str()'d
    and stripped."""
    if value is None:
        return ""
    if isinstance(value, bool):
        # bool is a subclass of int - check before the int/float branch
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if isinstance(value, int):
        return str(value)
    return str(value).strip()


def read_excel_as_dicts(path, sheet_name=None):
    """Reads an .xlsx file and returns a list of dict rows keyed by the
    (stripped) header row, with every cell normalized to a string.

    Drop-in replacement for the pandas pattern used across the MOE
    dictionary plugins - each returned dict supports the same
    `row.get("column_name", default)` calls as a pandas Series did.
    """
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet_name] if sheet_name else wb.active
        rows_iter = ws.iter_rows(values_only=True)

        try:
            raw_headers = next(rows_iter)
        except StopIteration:
            return []

        headers = [
            str(h).strip() if h is not None else f"col_{i}"
            for i, h in enumerate(raw_headers)
        ]

        results = []
        for raw_row in rows_iter:
            # Skip fully blank rows (openpyxl can yield trailing empties)
            if raw_row is None or all(v is None for v in raw_row):
                continue
            row = {}
            for i, header in enumerate(headers):
                value = raw_row[i] if i < len(raw_row) else None
                row[header] = _cell_to_str(value)
            results.append(row)
        return results
    finally:
        wb.close()
