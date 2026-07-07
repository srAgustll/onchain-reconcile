#!/usr/bin/env python3
"""
onchain-reconcile
Reconcile publicly stated numbers against on-chain state and public APIs.

The idea is simple. Articles, dashboards and protocol announcements quote
numbers. The chain has the actual state. This tool takes a list of claims
and checks each one at the source, then prints a reconciliation table.

Zero dependencies. Python 3.9+.

Usage:
    python3 reconcile.py examples/mim.json
    python3 reconcile.py examples/mim.json --markdown > reports/mim.md
"""

import json
import sys
import urllib.request

RPC_ENDPOINTS = [
    "https://ethereum-rpc.publicnode.com",
    "https://eth.drpc.org",
    "https://eth.llamarpc.com",
]

# Common ERC-20 / ERC-4626 selectors
SELECTORS = {
    "totalSupply()": "0x18160ddd",
    "decimals()": "0x313ce567",
    "totalAssets()": "0x01e1d114",
}


def http_json(url, payload=None, timeout=20):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Content-Type": "application/json", "User-Agent": "onchain-reconcile"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def eth_call(to, data):
    """eth_call against public RPCs, with fallbacks. Returns int."""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
        "id": 1,
    }
    last_err = None
    for rpc in RPC_ENDPOINTS:
        try:
            res = http_json(rpc, payload)
            if "result" in res and res["result"] not in (None, "0x"):
                return int(res["result"], 16)
        except Exception as e:  # try next endpoint
            last_err = e
    raise RuntimeError(f"all RPCs failed: {last_err}")


def selector_for(sig):
    if sig in SELECTORS:
        return SELECTORS[sig]
    if sig.startswith("0x"):
        return sig
    raise ValueError(f"unknown signature {sig!r}; pass the 4-byte selector as 0x...")


def encode_address_arg(selector, address):
    return selector + address.lower().replace("0x", "").rjust(64, "0")


# ---- claim resolvers -------------------------------------------------------

def resolve_eth_call(c):
    """{'to': .., 'signature': 'totalSupply()' | '0x..', 'arg_address': optional,
        'decimals': 18}"""
    sel = selector_for(c["signature"])
    data = encode_address_arg(sel, c["arg_address"]) if c.get("arg_address") else sel
    raw = eth_call(c["to"], data)
    return raw / 10 ** c.get("decimals", 18)


def resolve_defillama_price(c):
    """{'token': 'ethereum:0x...'}"""
    res = http_json(f"https://coins.llama.fi/prices/current/{c['token']}")
    coins = res.get("coins", {})
    if not coins:
        raise RuntimeError("token not found on DefiLlama")
    return list(coins.values())[0]["price"]


def resolve_defillama_tvl(c):
    """{'protocol': 'abracadabra'}"""
    res = http_json(f"https://api.llama.fi/tvl/{c['protocol']}")
    return float(res)


RESOLVERS = {
    "eth_call": resolve_eth_call,
    "defillama_price": resolve_defillama_price,
    "defillama_tvl": resolve_defillama_tvl,
}

# ---- reconciliation --------------------------------------------------------

def reconcile(claims):
    rows = []
    for c in claims:
        try:
            actual = RESOLVERS[c["type"]](c)
            claimed = float(c["claimed"])
            tol = float(c.get("tolerance_pct", 5.0))
            if claimed == 0:
                delta_pct = float("inf") if actual != 0 else 0.0
            else:
                delta_pct = (actual - claimed) / abs(claimed) * 100
            verdict = "MATCH" if abs(delta_pct) <= tol else "MISMATCH"
            rows.append({**c, "actual": actual, "delta_pct": delta_pct, "verdict": verdict})
        except Exception as e:
            rows.append({**c, "actual": None, "delta_pct": None, "verdict": f"UNVERIFIED ({e})"})
    return rows


def fmt(x):
    if x is None:
        return "-"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    return f"{x:,.4f}".rstrip("0").rstrip(".")


def print_table(rows, markdown=False):
    if markdown:
        print("| Claim | Source says | Chain says | Delta | Verdict |")
        print("|---|---|---|---|---|")
        for r in rows:
            d = f"{r['delta_pct']:+.1f}%" if r["delta_pct"] is not None else "-"
            print(f"| {r['label']} | {fmt(float(r['claimed']))} | {fmt(r['actual'])} | {d} | {r['verdict']} |")
    else:
        w = max(len(r["label"]) for r in rows) + 2
        print(f"{'CLAIM':<{w}}{'SOURCE SAYS':>15}{'CHAIN SAYS':>15}{'DELTA':>9}  VERDICT")
        for r in rows:
            d = f"{r['delta_pct']:+.1f}%" if r["delta_pct"] is not None else "-"
            print(f"{r['label']:<{w}}{fmt(float(r['claimed'])):>15}{fmt(r['actual']):>15}{d:>9}  {r['verdict']}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)
    with open(args[0]) as f:
        spec = json.load(f)
    rows = reconcile(spec["claims"])
    md = "--markdown" in sys.argv
    if md:
        print(f"# Reconciliation: {spec.get('title', args[0])}\n")
        if spec.get("context"):
            print(spec["context"] + "\n")
    print_table(rows, markdown=md)
    mismatches = sum(1 for r in rows if r["verdict"] == "MISMATCH")
    unverified = sum(1 for r in rows if str(r["verdict"]).startswith("UNVERIFIED"))
    if md:
        print(f"\n{len(rows)} claims checked. {mismatches} mismatch(es), {unverified} unverified.")
    else:
        print(f"\n{len(rows)} claims checked. {mismatches} mismatch(es), {unverified} unverified.")


if __name__ == "__main__":
    main()
