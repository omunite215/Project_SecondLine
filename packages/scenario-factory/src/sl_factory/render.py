"""Render facts into the agent-visible WorldBundle, then reconcile it (KG-03/KG-04, §5, ADR-016, ADR-017).

Records come only from facts: the bank's view (trades, cash journal, securities ledger) from the booked fields,
the outside view (broker confirm, CSD status, custodian and nostro statements, notices) from the true ones.
Breaks are then *found* by reconciling those visible records the way a recon engine would: a symptom, never a
cause. Nothing here reads a BreakPlan; generators that need records beyond trades (FX revaluation, corporate
actions, SSIs) add an `Extra`, which renders its own facts.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from sl_factory.lifecycle import TradeSim, dec_str, gross, money, utc
from sl_factory.rng import IdMinter

JSON = dict[str, Any]
DESIGNATED_FX_SOURCE = "ecb"  # agent-visible policy (ADR-017 B4 row): revalue only with ECB reference rates
FX_BASE = "USD"  # the bank's reporting currency for FX revaluation (KG-04 K1: EUR position valued in USD)


@dataclass
class RecordIds:
    """Which visible record ids belong to which fact (lets the oracle name required evidence)."""

    trade_entry: dict[str, str] = field(default_factory=dict)
    settle_entry: dict[str, str] = field(default_factory=dict)
    confirm: dict[str, str] = field(default_factory=dict)
    status: dict[str, str] = field(default_factory=dict)
    nostro: dict[str, str] = field(default_factory=dict)
    custodian: dict[str, str] = field(default_factory=dict)  # by ISIN
    named: dict[str, str] = field(default_factory=dict)  # records an Extra names, e.g. "fx_reval_entry"


@dataclass
class Records:
    journal: list[JSON] = field(default_factory=list)
    movements: list[JSON] = field(default_factory=list)
    evidence: list[JSON] = field(default_factory=list)
    fx_rates: list[JSON] = field(default_factory=list)
    instruments: list[JSON] = field(default_factory=list)


class Extra(Protocol):
    """Facts beyond trades. `holdings` is the custodian's true change per ISIN (e.g. a split's new shares)."""

    holdings: dict[str, int]

    def render(self, ids: IdMinter, rec: RecordIds, as_of: str) -> Records: ...


def line(account: str, side: str, amount: Decimal, ccy: str) -> JSON:
    return {"account": account, "side": side, "amount": dec_str(amount), "currency": ccy}


def movement(ids: IdMinter, at: str, isin: str, account: str, side: str, q: int, trade_id: str | None = None) -> JSON:
    m = {
        "movement_id": ids.mint("mov"),
        "booked_at": at,
        "account": f"{account}-{isin}",
        "isin": isin,
        "side": side,
        "quantity": str(q),
    }
    if trade_id:
        m["trade_id"] = trade_id
    return m


def evidence(ids: IdMinter, kind: str, source: str, at: str, fields: dict[str, str], text: str) -> JSON:
    return {
        "record_id": ids.mint("evd"),
        "version": 1,
        "kind": kind,
        "source_system": source,
        "received_at": at,
        "fields": fields,
        "text": text,
    }


_DEFAULT_PHRASES = {"holding": "Holding {q} {isin} as of {d}.", "debit": "Debit {a} {ccy}, ref {ref}."}


def _render_trade(
    t: TradeSim, ids: IdMinter, rec: RecordIds, as_of: str, out: Records, trades: list[JSON], ph: dict[str, str]
) -> None:
    ccy = t.currency
    if t.booked:
        booked_gross = gross(t.booked_quantity, t.booked_price, ccy)
        trades.append(
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
        at = utc(t.trade_date, 14, 30)  # ADR-016 buy, trade date
        rec.trade_entry[t.trade_id] = eid = ids.mint("jnl")
        out.journal.append(
            {
                "entry_id": eid,
                "booked_at": at,
                "trade_id": t.trade_id,
                "lines": [line(f"1300-{ccy}", "DR", booked_gross, ccy), line(f"1210-{ccy}", "CR", booked_gross, ccy)],
            }
        )
        out.movements += [
            movement(ids, at, t.isin, "S200", "DR", t.booked_quantity, t.trade_id),
            movement(ids, at, t.isin, "S900", "CR", t.booked_quantity, t.trade_id),
        ]
        if t.internally_settled:  # settlement date, on the contractual-date assumption
            at = utc(t.value_date, 12)
            rec.settle_entry[t.trade_id] = eid = ids.mint("jnl")
            out.journal.append(
                {
                    "entry_id": eid,
                    "booked_at": at,
                    "trade_id": t.trade_id,
                    "lines": [
                        line(f"1210-{ccy}", "DR", booked_gross, ccy),
                        line(f"1110-{ccy}", "CR", booked_gross, ccy),
                    ],
                }
            )
            out.movements += [
                movement(ids, at, t.isin, "S100", "DR", t.booked_quantity, t.trade_id),
                movement(ids, at, t.isin, "S200", "CR", t.booked_quantity, t.trade_id),
            ]
    if t.has_confirm:
        g = gross(t.quantity, t.confirm_price, ccy)
        e = evidence(
            ids,
            "BROKER_CONFIRM",
            "broker_sim",
            utc(t.trade_date, 17),
            {
                "trade_ref": t.ref,
                "isin": t.isin,
                "side": "BUY",
                "quantity": str(t.quantity),
                "price": dec_str(t.confirm_price),
                "gross": dec_str(g),
                "currency": ccy,
                "trade_date": t.trade_date,
                "settle_date": t.value_date,
                "counterparty": t.counterparty.name,
            },
            f"{t.counterparty.name}: BUY {t.quantity} {t.isin} @ {dec_str(t.confirm_price)} {ccy}.",
        )
        rec.confirm[t.trade_id] = e["record_id"]
        out.evidence.append(e)
    if t.has_status:
        f = {
            "trade_ref": t.ref,
            "status": t.ext_status,
            "value_date": t.value_date,
            "settle_date": t.status_settle_date,
            "currency": ccy,
            "quantity": str(t.settled_quantity if t.ext_status == "PARTIALLY_SETTLED" else t.quantity),
        }
        if t.cutoff_time:
            f["cutoff_time"] = t.cutoff_time
        if t.status_code:
            f["status_code"] = t.status_code
        e = evidence(ids, "SETTLEMENT_STATUS", "csd_sim", utc(as_of, 23), f, f"{t.ref}: {t.status_text}")
        rec.status[t.trade_id] = e["record_id"]
        out.evidence.append(e)
    if t.settled_quantity:  # nostro: cash actually paid for what the custodian delivered
        paid = gross(t.settled_quantity, t.confirm_price, ccy)
        e = evidence(
            ids,
            "NOSTRO_STATEMENT",
            "nostro_sim",
            utc(as_of, 23, 10),
            {
                "account": f"1110-{ccy}",
                "currency": ccy,
                "debit_amount": dec_str(paid),
                "value_date": t.status_settle_date,
                "trade_ref": t.ref,
            },
            ph["debit"].format(a=dec_str(paid), ccy=ccy, ref=t.ref),
        )
        rec.nostro[t.trade_id] = e["record_id"]
        out.evidence.append(e)


def render(
    trades: list[TradeSim],
    ids: IdMinter,
    scenario_id: str,
    as_of: str,
    extras: list[Extra] | None = None,
    phrases: dict[str, str] | None = None,
) -> tuple[JSON, RecordIds]:
    rec = RecordIds()
    out = Records()
    out_trades: list[JSON] = []
    ph = {**_DEFAULT_PHRASES, **(phrases or {})}
    for t in trades:
        _render_trade(t, ids, rec, as_of, out, out_trades, ph)
    held: dict[str, int] = defaultdict(int)
    for t in trades:
        held[t.isin] += t.settled_quantity
    instruments = {t.isin: {"isin": t.isin, "currency": t.currency, "name": t.instrument.name} for t in trades}
    for x in extras or []:
        r = x.render(ids, rec, as_of)
        out.journal += r.journal
        out.movements += r.movements
        out.evidence += r.evidence
        out.fx_rates += r.fx_rates
        instruments.update({i["isin"]: i for i in r.instruments})
        for isin, q in x.holdings.items():
            held[isin] += q
    for isin in sorted(held):  # custodian statement per ISIN: settled holdings as of the statement cutoff
        e = evidence(
            ids,
            "CUSTODIAN_STATEMENT",
            "custody_sim",
            utc(as_of, 23, 10),
            {"account": f"S100-{isin}", "isin": isin, "quantity": str(held[isin]), "as_of": as_of},
            ph["holding"].format(q=held[isin], isin=isin, d=as_of),
        )
        rec.custodian[isin] = e["record_id"]
        out.evidence.append(e)
    accounts = {ln["account"] for e in out.journal for ln in e["lines"]} | {m["account"] for m in out.movements}
    bundle: JSON = {
        "bundle_version": "1.0",
        "scenario_id": scenario_id,
        "as_of": as_of,
        "reference_snapshots": [],
        "instruments": [instruments[k] for k in sorted(instruments)],
        "accounts": [{"account": a, "kind": "security" if a.startswith("S") else "cash"} for a in sorted(accounts)],
        "fx_rates": sorted(out.fx_rates, key=lambda r: (r["as_of"], r["rate_id"])),
        "trades": sorted(out_trades, key=lambda r: r["trade_id"]),
        "journal_entries": sorted(out.journal, key=lambda r: (r["booked_at"], r["entry_id"])),
        "securities_movements": sorted(out.movements, key=lambda r: (r["booked_at"], r["movement_id"])),
        "evidence": sorted(out.evidence, key=lambda r: (r["received_at"], r["record_id"])),
        "breaks": [],
    }
    return bundle, rec


# ---- reconciliation over visible records only -----------------------------------------------------------
def _signed(amount: str, side: str) -> Decimal:
    return Decimal(amount) * (1 if side == "DR" else -1)


def _fx_breaks(bundle: JSON, ids: IdMinter) -> list[JSON]:
    """FX revaluation control: recompute each 4200 revaluation of the EUR position in USD with the designated
    (ECB) rate as of the bundle date; a difference is a CASH_DIFFERENCE break."""
    rates = {
        (r["base"], r["quote"], r["as_of"]): Decimal(r["rate"])
        for r in bundle["fx_rates"]
        if r["source"] == DESIGNATED_FX_SOURCE
    }
    notices = [e for e in bundle["evidence"] if e["kind"] == "FX_RATE_NOTICE"]
    bal: dict[str, Decimal] = defaultdict(Decimal)
    out = []
    for e in bundle["journal_entries"]:
        accts = {ln["account"][:4] for ln in e["lines"]}
        if "4200" in accts:
            reval = sum(
                (_signed(ln["amount"], ln["side"]) for ln in e["lines"] if ln["account"] == f"1500-{FX_BASE}"),
                Decimal(0),
            )
            exposure = -bal["1500-EUR"]  # EUR held: the conversion credited 1500-EUR
            book_rate = bal[f"1500-{FX_BASE}"] / exposure if exposure else Decimal(0)
            designated = rates.get(("EUR", FX_BASE, bundle["as_of"]))
            if designated is None:  # no fixing today: policy = last prior designated fixing
                prior = sorted(k for k in rates if k[:2] == ("EUR", FX_BASE) and k[2] < bundle["as_of"])
                designated = rates[prior[-1]] if prior else None
            if designated is not None and exposure:
                expected = money(exposure * (designated - book_rate), FX_BASE)
                diff = expected - reval
                if diff:
                    out.append(
                        {
                            "break_id": ids.mint("brk"),
                            "opened_at": utc(bundle["as_of"], 23, 30),
                            "symptom": "CASH_DIFFERENCE",
                            "currency": FX_BASE,
                            "cash_difference": dec_str(diff),
                            "evidence_ids": sorted(n["record_id"] for n in notices),
                        }
                    )
        for ln in e["lines"]:
            bal[ln["account"]] += _signed(ln["amount"], ln["side"])
    return out


def reconcile(bundle: JSON, ids: IdMinter) -> list[JSON]:
    """Confirm vs booking, custody vs S100 per ISIN, nostro vs 1110 per trade, the FX revaluation control.
    One break per ISIN with differences (positions, unmatched or unsettled trades), one per cash-only booking
    batch (currency, trade date), one per FX revaluation difference."""
    ev_by_ref: dict[str, dict[str, JSON]] = defaultdict(dict)
    custodian: dict[str, JSON] = {}
    notices_by_isin: dict[str, list[str]] = defaultdict(list)
    for e in bundle["evidence"]:
        if "trade_ref" in e["fields"]:
            ev_by_ref[e["fields"]["trade_ref"]][e["kind"]] = e
        if e["kind"] == "CUSTODIAN_STATEMENT":
            custodian[e["fields"]["isin"]] = e
        if e["kind"] == "CA_NOTICE":
            notices_by_isin[e["fields"]["isin"]].append(e["record_id"])
    trades = {t["trade_id"]: t for t in bundle["trades"]}
    booked_gross = {
        e["trade_id"]: Decimal(e["lines"][0]["amount"])
        for e in bundle["journal_entries"]
        if e.get("trade_id") and e["lines"][0]["account"].startswith("1300")
    }
    cash_1110: dict[str, Decimal] = defaultdict(Decimal)
    for e in bundle["journal_entries"]:
        for ln in e["lines"]:
            if ln["account"].startswith("1110") and e.get("trade_id"):
                cash_1110[e["trade_id"]] += _signed(ln["amount"], ln["side"])
    s100: dict[str, int] = defaultdict(int)
    for m in bundle["securities_movements"]:
        if m["account"].startswith("S100"):
            s100[m["isin"]] += int(m["quantity"]) * (1 if m["side"] == "DR" else -1)

    # per trade: what disagrees
    pos_suspects: dict[str, list[str]] = defaultdict(list)  # isin -> refs (trade ids or external refs)
    cash_batches: dict[tuple[str, str], list[str]] = defaultdict(list)
    gdiff: dict[str, Decimal] = {}
    cdiff: dict[str, Decimal] = {}
    unmatched: set[str] = set()
    failed: set[str] = set()
    ccy_of: dict[str, str] = {}
    for tid, t in trades.items():
        refs = ev_by_ref.get(tid, {})
        confirm, status = refs.get("BROKER_CONFIRM"), refs.get("SETTLEMENT_STATUS")
        ccy_of[tid] = t["currency"]
        nostro = refs.get("NOSTRO_STATEMENT")
        cdiff[tid] = (-Decimal(nostro["fields"]["debit_amount"]) if nostro else Decimal(0)) - cash_1110[tid]
        if confirm is None:
            unmatched.add(tid)
            pos_suspects[t["isin"]].append(tid)
            continue
        g = Decimal(confirm["fields"]["gross"]) - booked_gross[tid]
        q = int(confirm["fields"]["quantity"]) - int(t["quantity"])
        st = status["fields"] if status else {}
        if st.get("status") == "FAILED":
            failed.add(tid)
        settled_ok = st.get("status") == "SETTLED" and st.get("quantity") == t["quantity"]
        unsettled = t["status"] == "SETTLED" and not settled_ok
        gdiff[tid] = g
        if q or unsettled:
            pos_suspects[t["isin"]].append(tid)
        elif g:
            cash_batches[(t["currency"], t["trade_date"])].append(tid)
    for ref, refs in ev_by_ref.items():  # outside records for a trade the bank never booked
        if ref not in trades and "BROKER_CONFIRM" in refs:
            c = refs["BROKER_CONFIRM"]["fields"]
            unmatched.add(ref)
            ccy_of[ref] = c["currency"]
            nostro = refs.get("NOSTRO_STATEMENT")
            cdiff[ref] = -Decimal(nostro["fields"]["debit_amount"]) if nostro else Decimal(0)
            pos_suspects[c["isin"]].append(ref)

    breaks: list[JSON] = []
    opened = utc(bundle["as_of"], 23, 30)
    isins = sorted(set(custodian) | set(s100) | set(pos_suspects))
    for isin in isins:
        held = int(custodian[isin]["fields"]["quantity"]) if isin in custodian else 0
        qd = held - s100[isin]
        isin_refs = sorted(pos_suspects.get(isin, []))
        if not qd and not isin_refs:
            continue
        g = sum((gdiff.get(r, Decimal(0)) for r in isin_refs), Decimal(0))
        c = g if g else sum((cdiff.get(r, Decimal(0)) for r in isin_refs), Decimal(0))
        symptom = (
            "UNMATCHED_TRADE"
            if set(isin_refs) & unmatched
            else "SETTLEMENT_FAILURE"
            if set(isin_refs) & failed
            else "POSITION_DIFFERENCE"
            if qd
            else "CASH_DIFFERENCE"
        )
        ins_ccy = {i["isin"]: i["currency"] for i in bundle["instruments"]}
        ccy = ccy_of[isin_refs[0]] if isin_refs else ins_ccy[isin]
        evid = {e["record_id"] for r in isin_refs for e in ev_by_ref.get(r, {}).values()} | set(notices_by_isin[isin])
        if isin in custodian:
            evid.add(custodian[isin]["record_id"])
        br: JSON = {
            "break_id": ids.mint("brk"),
            "opened_at": opened,
            "symptom": symptom,
            "currency": ccy,
            "isin": isin,
            "trade_ids": sorted(r for r in isin_refs if r in trades),
            "evidence_ids": sorted(evid),
        }
        if c:
            br["cash_difference"] = dec_str(c)
        if qd:
            br["quantity_difference"] = str(qd)
        breaks.append(br)
    for (ccy, _day), tids in sorted(cash_batches.items()):
        tids = sorted(tids)
        isin_set = sorted({trades[t]["isin"] for t in tids})
        br = {
            "break_id": ids.mint("brk"),
            "opened_at": opened,
            "symptom": "CASH_DIFFERENCE",
            "currency": ccy,
            "trade_ids": tids,
            "evidence_ids": sorted({e["record_id"] for t in tids for e in ev_by_ref[t].values()}),
            "cash_difference": dec_str(sum((gdiff[t] for t in tids), Decimal(0))),
        }
        if len(isin_set) == 1:
            br["isin"] = isin_set[0]
        breaks.append(br)
    return breaks + _fx_breaks(bundle, ids)
