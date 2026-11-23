"""Run the check views (sql/*.sql) on DuckDB, locally, on the snapshot or on test fixtures.

Usage: python scripts/checks.py [tables_dir]     prints every row of checks_all
"""
import csv, pathlib, sys
import duckdb

ROOT = pathlib.Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
TABLES = ("listing", "bundle_line", "store")

def sql_files(sql_dir=SQL_DIR):
    return sorted(pathlib.Path(sql_dir).glob("*.sql"))

def connect(tables, sql_text=None):
    """tables: {name: [dict rows]}; sql_text: {filename: text} to run instead of the files (mutation tests)."""
    con = duckdb.connect()
    files = sql_text or {p.name: p.read_text(encoding="utf-8") for p in sql_files()}
    con.execute(files["00_tables.sql"])
    for name in TABLES:
        rows = tables.get(name, [])
        if not rows:
            continue
        cols = [c[0] for c in con.execute(f"DESCRIBE {name}").fetchall()]
        con.executemany(f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                        [[None if r.get(c, "") == "" else r[c] for c in cols] for r in rows])
    for fname in sorted(files):
        if fname != "00_tables.sql":
            con.execute(files[fname])
    return con

def load_csv(tables_dir):
    d = pathlib.Path(tables_dir)
    return {n: list(csv.DictReader(open(d / f"{n}.csv", encoding="utf-8"))) for n in TABLES if (d / f"{n}.csv").exists()}

def rows(con, view):
    cur = con.execute(f"SELECT * FROM {view} ORDER BY store, key")
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

if __name__ == "__main__":
    tables_dir = sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "tables"
    if not (pathlib.Path(tables_dir) / "listing.csv").exists():
        sys.exit(f"no listing.csv in {tables_dir}: run scripts/flatten.py first")
    con = connect(load_csv(tables_dir))
    found = rows(con, "checks_all")
    for r in found:
        print(f"{r['check_name']:28} {r['severity']:11} {r['store']:15} {r['key']:30} expected {r['expected']} actual {r['actual']} delta {r['delta']}")
    print(f"{len(found)} rows in checks_all" + (" (PASS)" if not found else ""))
