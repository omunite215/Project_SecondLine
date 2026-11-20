"""Render trade facts into the agent-visible WorldBundle, then reconcile it (KG-03, §5, ADR-016, ADR-017).

Records come only from `TradeSim` facts: the bank's view (trades, cash journal, securities ledger) from the
booked fields, the outside view (broker confirm, CSD status, custodian and nostro statements) from the true ones.
Breaks are then *found* by reconciling those visible records, the way a recon engine would: a symptom, never a
cause. Nothing here reads a BreakPlan.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sl_factory.lifecycle import TradeSim, dec_str, gross, utc
from sl_factory.rng import IdMinter

JSON = dict[str, Any]


@dataclass
class RecordIds:
    """Which visible record ids belong to which trade (lets the oracle name required evidence)."""

    trade_entry: dict[str, str] = field(default_factory=dict)
    settle_entry: dict[str, str] = field(default_factory=dict)
    confirm: dict[str, str] = field(default_factory=dict)
    status: dict[str, str] = field(default_factory=dict)
    nostro: dict[str, str] = field(default_factory=dict)
    custodian: dict[str, str] = field(default_factory=dict)  # by ISIN


def _line(account: str, side: str, amount: Decimal, ccy: str) -> JSON:
    return {"account": account, "side": side, "amount": dec_str(amount), "currency": ccy}


def _mov(ids: IdMinter, at: str, t: TradeSim, account: str, side: str, q: int) -> JSON:
    return {
        "movement_id": ids.mint("mov"),
        "booked_at": at,
        "trade_id": t.trade_id,
        "account": f"{account}-{t.isin}",
        "isin": t.isin,
        "side": side,
        "quantity": str(q),
    }


def render(trades: list[TradeSim], ids: IdMinter, scenario_id: str, as_of: str) -> tuple[JSON, RecordIds]:
    rec = RecordIds()
    out_trades: list[JSON] = []
    journal: list[JSON] = []
    movements: list[JSON] = []
    evidence: list[JSON] = []
    for t in trades:
        ccy = t.currency
        booked_gross = gross(t.booked_quantity, t.booked_price, ccy)
        out_trades.append(
            {
                "trade_id": t.trade_id,
                "version": 1,
                "isin": t.isin,
                "side": "BUY",
                "quantity": str(t.booked_quantity),
                "price": dec_str(t.booked_price),
                "currency": ccy,
                "trade_date": t.trade_date,
                "settlement_date": t.value_date,
                "status": "SETTLED" if t.internally_settled else "BOOKED",
            }
        )
        # bank: trade date (ADR-016 buy pattern)
        at = utc(t.trade_date, 14, 30)
        rec.trade_entry[t.trade_id] = eid = ids.mint("jnl")
        journal.append(
            {
                "entry_id": eid,
                "booked_at": at,
                "trade_id": t.trade_id,
                "lines": [_line(f"1300-{ccy}", "DR", booked_gross, ccy), _line(f"1210-{ccy}", "CR", booked_gross, ccy)],
            }
        )
        movements += [
            _mov(ids, at, t, "S200", "DR", t.booked_quantity),
            _mov(ids, at, t, "S900", "CR", t.booked_quantity),
        ]
        # bank: settlement date, on the contractual-date assumption
        if t.internally_settled:
            at = utc(t.value_date, 12)
            rec.settle_entry[t.trade_id] = eid = ids.mint("jnl")
            journal.append(
                {
                    "entry_id": eid,
                    "booked_at": at,
                    "trade_id": t.trade_id,
                    "lines": [
                        _line(f"1210-{ccy}", "DR", booked_gross, ccy),
                        _line(f"1110-{ccy}", "CR", booked_gross, ccy),
                    ],
                }
            )
            movements += [
                _mov(ids, at, t, "S100", "DR", t.booked_quantity),
                _mov(ids, at, t, "S200", "CR", t.booked_quantity),
            ]
        # outside world: broker confirm (executed facts)
        confirm_gross = gross(t.quantity, t.confirm_price, ccy)
        rec.confirm[t.trade_id] = rid = ids.mint("evd")
        evidence.append(
            {
                "record_id": rid,
                "version": 1,
                "kind": "BROKER_CONFIRM",
                "source_system": "broker_sim",
                "received_at": utc(t.trade_date, 17),
                "fields": {
                    "trade_ref": t.trade_id,
                    "isin": t.isin,
                    "side": "BUY",
                    "quantity": str(t.quantity),
                    "price": dec_str(t.confirm_price),
                    "gross": dec_str(confirm_gross),
                    "currency": ccy,
                    "trade_date": t.trade_date,
                    "settle_date": t.value_date,
                    "counterparty": t.counterparty.name,
                },
                "text": f"{t.counterparty.name}: BUY {t.quantity} {t.isin} @ {dec_str(t.confirm_price)} {ccy}.",
            }
        )
        # CSD settlement status
        status_fields = {
            "trade_ref": t.trade_id,
            "status": t.ext_status,
            "value_date": t.value_date,
            "settle_date": t.status_settle_date,
            "currency": ccy,
            "quantity": str(t.settled_quantity if t.ext_status == "PARTIALLY_SETTLED" else t.quantity),
        }
        if t.cutoff_time:
            status_fields["cutoff_time"] = t.cutoff_time
        rec.status[t.trade_id] = rid = ids.mint("evd")
        evidence.append(
            {
                "record_id": rid,
                "version": 1,
                "kind": "SETTLEMENT_STATUS",
                "source_system": "csd_sim",
                "received_at": utc(as_of, 23),
                "fields": status_fields,
                "text": f"{t.trade_id}: {t.status_text}",
            }
        )
        # nostro: cash actually paid for what the custodian delivered
        if t.settled_quantity:
            paid = gross(t.settled_quantity, t.confirm_price, ccy)
            rec.nostro[t.trade_id] = rid = ids.mint("evd")
            evidence.append(
                {
                    "record_id": rid,
                    "version": 1,
                    "kind": "NOSTRO_STATEMENT",
                    "source_system": "nostro_sim",
                    "received_at": utc(as_of, 23, 10),
                    "fields": {
                        "account": f"1110-{ccy}",
                        "currency": ccy,
                        "debit_amount": dec_str(paid),
                        "value_date": t.status_settle_date,
                        "trade_ref": t.trade_id,
                    },
                    "text": f"Debit {dec_str(paid)} {ccy}, ref {t.trade_id}.",
                }
            )
    # custodian statement per ISIN: settled holdings as of the statement cutoff
    held: dict[str, int] = defaultdict(int)
    for t in trades:
        held[t.isin] += t.settled_quantity
    for isin in sorted(held):
        rec.custodian[isin] = rid = ids.mint("evd")
        evidence.append(
            {
                "record_id": rid,
                "version": 1,
                "kind": "CUSTODIAN_STATEMENT",
                "source_system": "custody_sim",
                "received_at": utc(as_of, 23, 10),
                "fields": {"account": f"S100-{isin}", "isin": isin, "quantity": str(held[isin]), "as_of": as_of},
                "text": f"Holding {held[isin]} {isin} as of {as_of}.",
            }
        )
    instruments = {t.isin: {"isin": t.isin, "currency": t.currency, "name": t.instrument.name} for t in trades}
    accounts = {ln["account"] for e in journal for ln in e["lines"]} | {m["account"] for m in movements}
    bundle: JSON = {
        "bundle_version": "1.0",
        "scenario_id": scenario_id,
        "as_of": as_of,
        "reference_snapshots": [],
        "instruments": [instruments[k] for k in sorted(instruments)],
        "accounts": [{"account": a, "kind": "security" if a.startswith("S") else "cash"} for a in sorted(accounts)],
        "fx_rates": [],
        "trades": sorted(out_trades, key=lambda r: r["trade_id"]),
        "journal_entries": sorted(journal, key=lambda r: (r["booked_at"], r["entry_id"])),
        "securities_movements": sorted(movements, key=lambda r: (r["booked_at"], r["movement_id"])),
        "evidence": sorted(evidence, key=lambda r: (r["received_at"], r["record_id"])),
        "breaks": [],
    }
    return bundle, rec


def reconcile(bundle: JSON, ids: IdMinter) -> list[JSON]:
    """Recon over visible records only: confirm vs booking, custody vs S100, nostro vs 1110. One break per
    currency for the trades that disagree (KG-03 scenarios carry one cause; KG-04 adds multi-break worlds)."""
    ev_by_ref: dict[str, dict[str, JSON]] = defaultdict(dict)
    custodian: dict[str, JSON] = {}
    for e in bundle["evidence"]:
        if "trade_ref" in e["fields"]:
            ev_by_ref[e["fields"]["trade_ref"]][e["kind"]] = e
        if e["kind"] == "CUSTODIAN_STATEMENT":
            custodian[e["fields"]["isin"]] = e
    booked_gross = {
        e["trade_id"]: Decimal(e["lines"][0]["amount"])
        for e in bundle["journal_entries"]
        if e["lines"][0]["account"].startswith("1300")
    }
    s100: dict[str, int] = defaultdict(int)
    for m in bundle["securities_movements"]:
        if m["account"].startswith("S100"):
            s100[m["isin"]] += int(m["quantity"]) * (1 if m["side"] == "DR" else -1)
    cash_1110: dict[str, Decimal] = defaultdict(Decimal)
    for e in bundle["journal_entries"]:
        for ln in e["lines"]:
            if ln["account"].startswith("1110"):
                cash_1110[ln["currency"]] += Decimal(ln["amount"]) * (1 if ln["side"] == "DR" else -1)
    nostro: dict[str, Decimal] = defaultdict(Decimal)
    for e in bundle["evidence"]:
        if e["kind"] == "NOSTRO_STATEMENT":
            nostro[e["fields"]["currency"]] -= Decimal(e["fields"]["debit_amount"])

    suspects: dict[str, list[JSON]] = defaultdict(list)
    gross_diff: dict[str, Decimal] = defaultdict(Decimal)
    for t in bundle["trades"]:
        refs = ev_by_ref[t["trade_id"]]
        confirm, status = refs["BROKER_CONFIRM"], refs["SETTLEMENT_STATUS"]["fields"]
        g = Decimal(confirm["fields"]["gross"]) - booked_gross[t["trade_id"]]
        q = int(confirm["fields"]["quantity"]) - int(t["quantity"])
        unsettled = t["status"] == "SETTLED" and not (
            status["status"] == "SETTLED" and status["quantity"] == t["quantity"]
        )
        if g or q or unsettled:
            suspects[t["currency"]].append(t)
            gross_diff[t["currency"]] += g
    breaks = []
    for ccy in sorted(suspects):
        ts = suspects[ccy]
        isins = sorted({t["isin"] for t in ts})
        qdiff = sum(int(custodian[i]["fields"]["quantity"]) - s100[i] if i in custodian else -s100[i] for i in isins)
        cdiff = gross_diff[ccy] if gross_diff[ccy] else nostro[ccy] - cash_1110[ccy]
        tids = sorted(t["trade_id"] for t in ts)
        evid = sorted(
            {e["record_id"] for tid in tids for e in ev_by_ref[tid].values()}
            | {custodian[i]["record_id"] for i in isins if i in custodian}
        )
        br: JSON = {
            "break_id": ids.mint("brk"),
            "opened_at": utc(bundle["as_of"], 23, 30),
            "symptom": "POSITION_DIFFERENCE" if qdiff else "CASH_DIFFERENCE",
            "currency": ccy,
            "trade_ids": tids,
            "evidence_ids": evid,
        }
        if len(isins) == 1:
            br["isin"] = isins[0]
        if cdiff:
            br["cash_difference"] = dec_str(cdiff)
        if qdiff:
            br["quantity_difference"] = str(qdiff)
        breaks.append(br)
    return breaks
