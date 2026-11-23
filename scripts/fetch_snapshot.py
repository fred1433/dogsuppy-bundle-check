"""Frozen snapshot of DogSuppy's public Shopify catalogues.

Light read: one GET /products.json?limit=250 per store (page 2 only if page 1 is full),
one GET /cart.js per store for the store currency, one GET of the ECB daily reference rates,
and one non-followed GET per domain that is not a store (to record the redirect or parking page).
Run once; the files under data/raw are the record the checks run on.
"""
import json, pathlib, time, subprocess, datetime

STORES = ["dogsuppy.com", "dogsuppy.de", "dogsuppy.dk", "dogsuppy.no",
          "dogsuppy.se", "dogsuppy.co.uk", "dogsuppy.pl", "dogsuppy.it"]
NOT_STORES = ["dogsuppy.nl", "dogsuppy.be", "dogsuppy.es"]
UA = {"User-Agent": "Mozilla/5.0 (catalogue snapshot, one request per store)", "Accept": "application/json"}
RAW = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"
ECB = RAW.parent / "ecb"

def get(url, opener=None):
    # curl rather than urllib: Shopify answers 429 to Python's TLS client on the first call.
    out = subprocess.run(["curl", "-s", "-D", "-", "--max-time", "30", "-A", UA["User-Agent"],
                          "-H", "Accept: " + UA["Accept"], url], capture_output=True, check=True).stdout
    head, _, body = out.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    code = int(lines[0].split()[1])
    headers = {k.strip().lower(): v.strip() for k, _, v in (l.partition(":") for l in lines[1:])}
    return code, headers, body

def main():
    log = {"read_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "requests": []}
    for s in STORES:
        products, page = [], 1
        while True:
            url = f"https://{s}/products.json?limit=250&page={page}"
            code, _, body = get(url)
            log["requests"].append({"url": url, "status": code})
            if code != 200:
                raise SystemExit(f"{url} answered {code}; stop and retry later")
            batch = json.loads(body)["products"]
            products += batch
            if len(batch) < 250:
                break
            page += 1
        (RAW / f"{s}.products.json").write_text(json.dumps({"products": products}, ensure_ascii=False, indent=1))
        code, _, body = get(f"https://{s}/cart.js")
        log["requests"].append({"url": f"https://{s}/cart.js", "status": code})
        (RAW / f"{s}.cart.json").write_bytes(body)
        time.sleep(1.5)
    opener = None
    for d in NOT_STORES:
        code, headers, body = get(f"https://{d}/", opener)
        log["requests"].append({"url": f"https://{d}/", "status": code, "location": headers.get("location")})
        (RAW / f"{d}.root.txt").write_bytes(body[:4000])
    code, _, body = get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml")
    log["requests"].append({"url": "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", "status": code})
    (ECB / "eurofxref-daily.xml").write_bytes(body)
    (RAW / "read_log.json").write_text(json.dumps(log, indent=1))
    print(json.dumps(log, indent=1))

if __name__ == "__main__":
    main()
