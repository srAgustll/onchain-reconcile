# onchain-reconcile

Reconcile publicly stated numbers against on-chain state.

Articles, dashboards and protocol announcements quote numbers. The chain has
the actual state. This tool takes a list of claims and verifies each one at
the source, then prints a reconciliation table with a verdict per claim.

I built it because I kept doing this by hand for my research, and the gap
between what gets quoted and what the chain says is where most of the
interesting findings live.

## What it does

- Reads a JSON file of claims (a quoted price, a supply, a pool balance, a TVL)
- Fetches the actual value at the source
  - `eth_call` against public Ethereum RPCs (with fallbacks)
  - DefiLlama price and TVL APIs
- Compares claimed vs actual within a tolerance and prints MATCH / MISMATCH /
  UNVERIFIED per claim

Zero dependencies. Python 3.9+, standard library only.

## Quickstart

```
python3 reconcile.py examples/mim.json
python3 reconcile.py examples/usdg.json --markdown > reports/usdg.md
```

## Real output

From `examples/mim.json`, run on 2026-07-07. Headlines said MIM depegged ~50%.

```
CLAIM                                SOURCE SAYS     CHAIN SAYS    DELTA  VERDICT
MIM price (headline: ~0.50 USD)              0.5         0.1548   -69.0%  MISMATCH
MIM in Curve MIM/3CRV pool             4,014,452      4,018,699    +0.1%  MATCH
3CRV in Curve MIM/3CRV pool               12,574         11,974    -4.8%  MATCH
Abracadabra total TVL (USD)            4,400,000      4,435,946    +0.8%  MATCH
```

From `examples/usdg.json`. April articles cited SY-USDG holding $121M of USDG
as proof of DeFi traction. The chain in July:

```
CLAIM                                         SOURCE SAYS     CHAIN SAYS    DELTA  VERDICT
USDG total supply (April claim: 474M)         474,000,000    470,194,025    -0.8%  MATCH
USDG held by SY-USDG (April claim: 121M)      121,000,000     34,687,694   -71.3%  MISMATCH
USDG price                                              1         0.9997    -0.0%  MATCH
```

Both findings are documented in full on my X (@SrAugustII) and the queries
behind them on Dune (@sraugust).

## Why this matters for fund and vault operations

Tokenized funds and curated vaults run on the same problem at a bigger scale:
the numbers in the report have to match the numbers on the chain, every day,
automatically. This is the small, public version of that reconciliation loop.
The same pattern extends to NAV checks, redemption windows, oracle drift and
collateral composition.

## Method notes

- Every value is read at the source. No aggregator is trusted as final.
- Claims that cannot be verified are marked UNVERIFIED, never guessed.
- Development is AI-assisted; verification and judgment are not. Every number
  in my published research is re-checked at the source before it ships.

## Roadmap

- ERC-4626 steady-state check (flag `convertToAssets` drift on 1:1 wrappers)
- Scheduled runs with alerting on new MISMATCH
- Multi-chain RPC support
