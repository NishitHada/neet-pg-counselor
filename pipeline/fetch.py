"""Download every source PDF listed in sources.json into pipeline/raw/ (skips files already present)."""
import json, pathlib, urllib.request

HERE = pathlib.Path(__file__).parent
RAW = HERE / "raw"


def raw_path(src):
    return RAW / f"{src['year']}_{src['round'].lower().replace(' ', '-')}.pdf"


def main():
    cfg = json.loads((HERE / "sources.json").read_text())
    RAW.mkdir(exist_ok=True)
    for src in cfg["sources"]:
        out = raw_path(src)
        if out.exists() and out.stat().st_size > 0:
            continue
        url = cfg["base"] + src["path"]
        print("fetch", out.name, url)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            out.write_bytes(r.read())


if __name__ == "__main__":
    main()
