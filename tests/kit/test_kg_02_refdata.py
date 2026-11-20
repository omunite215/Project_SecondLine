"""KG-02 (§6, REQ-001, SEC-14, RSK-15): reference-data parsers, hashed snapshots + MANIFEST, re-hash verify and
datasheet inputs. No network: parsers run on fixture text. Stdlib only: python3 -m unittest discover -s tests/kit"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("refdata", ROOT / "scripts" / "refdata.py")
assert _spec and _spec.loader
refdata = importlib.util.module_from_spec(_spec)
sys.modules["refdata"] = refdata
_spec.loader.exec_module(refdata)

ECB = """KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE,OBS_STATUS
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2026-11-02,1.1204,A
EXR.D.JPY.EUR.SP00.A,D,JPY,EUR,SP00,A,2026-11-02,176.81,A
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2026-11-03,1.1192,A
"""
H10 = '''"Series Description","Euro-Area Euro","Japanese Yen","Swiss Franc","United Kingdom Pound"
"Unit:","Currency","Currency","Currency","Currency"
"Multiplier:","1","1","1","1"
"Currency:","EUR","JPY","CHF","GBP"
"Unique Identifier: ","H10/H10/RXI$US_N.B.EU","H10/H10/RXI_N.B.JA","H10/H10/RXI_N.B.SZ","H10/H10/RXI$US_N.B.UK"
"Time Period","RXI$US_N.B.EU","RXI_N.B.JA","RXI_N.B.SZ","RXI$US_N.B.UK"
2026-11-02,1.1204,157.8100,0.8185,1.3420
2026-11-11,ND,ND,ND,ND
'''
GLEIF = {"data": [{"attributes": {"lei": "529900UPD2LG508R2403", "entity": {
    "legalName": {"name": "Example AG", "language": "de"}, "legalAddress": {"country": "DE"}, "category": "GENERAL",
    "status": "ACTIVE"}, "registration": {"status": "ISSUED", "lastUpdateDate": "2026-10-01T00:00:00Z"}}}]}


class Parsers(unittest.TestCase):
    def test_KG_02_ecb_rows_are_decimal_strings_per_eur(self) -> None:
        rows = refdata.parse_ecb(ECB)
        self.assertEqual(rows[0], {"date": "2026-11-02", "base": "EUR", "quote": "JPY", "rate": "176.81"})
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(isinstance(r["rate"], str) for r in rows))

    def test_KG_02_h10_keeps_published_direction_and_drops_nd(self) -> None:
        rows, dropped = refdata.parse_h10(H10)
        self.assertIn({"date": "2026-11-02", "base": "EUR", "quote": "USD", "rate": "1.1204"}, rows)  # USD per EUR
        self.assertIn({"date": "2026-11-02", "base": "USD", "quote": "JPY", "rate": "157.8100"}, rows)  # JPY per USD
        self.assertEqual(dropped, 4)
        self.assertFalse(any(r["date"] == "2026-11-11" for r in rows))

    def test_KG_02_aligned_dates_only_where_both_published(self) -> None:
        ecb, (h10, _) = refdata.parse_ecb(ECB), refdata.parse_h10(H10)
        self.assertEqual(refdata.aligned_dates(ecb, h10), ["2026-11-02"])

    def test_KG_02_gleif_records_trimmed(self) -> None:
        (rec,) = refdata.parse_gleif([GLEIF])
        self.assertEqual(rec, {"lei": "529900UPD2LG508R2403", "legal_name": "Example AG", "country": "DE",
                               "category": "GENERAL", "entity_status": "ACTIVE", "registration_status": "ISSUED",
                               "last_update": "2026-10-01T00:00:00Z"})

    def test_KG_02_gleif_drops_sole_proprietors(self) -> None:
        page = json.loads(json.dumps(GLEIF))
        page["data"][0]["attributes"]["entity"]["category"] = "SOLE_PROPRIETOR"
        self.assertEqual(refdata.parse_gleif([page]), [])

    def test_KG_02_raw_downloads_stored_with_lf(self) -> None:
        self.assertEqual(refdata.lf(b"a,b\r\nc,d"), b"a,b\nc,d\n")

    def test_KG_02_iso_codes_cited_and_flagged_verify(self) -> None:
        rows = refdata.iso_codes()
        codes = {r["code"] for r in rows}
        self.assertTrue({"LACK", "MONY", "CLAC", "CMON"} <= codes)
        self.assertTrue(all(r["verify"] is True and r["citation"].startswith("https://") for r in rows))


class Snapshots(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.entry = refdata.write_snapshot(
            self.root, source="ecb", date="2026-11-20",
            files={"raw.csv": ECB.encode(), "rates.json": refdata.dump_rows(refdata.parse_ecb(ECB))},
            meta={"url": ["https://example.invalid/ecb"], "retrieved_at": "2026-11-20T00:00:00Z", "license": "x",
                  "license_url": "https://example.invalid/l", "coverage_gaps": ["none"], "caveats": ["info only"]},
            rows={"rates.json": 3})

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_KG_02_snapshot_manifest_entry(self) -> None:
        manifest = json.loads((self.root / "MANIFEST.json").read_text())
        (snap,) = manifest["snapshots"]
        self.assertEqual(snap["ref"], "ecb@2026-11-20")
        self.assertEqual({f["path"] for f in snap["files"]}, {"ecb/2026-11-20/raw.csv", "ecb/2026-11-20/rates.json"})
        self.assertTrue(all(f["sha256"].startswith("sha256:") for f in snap["files"]))
        # idempotent: writing the same snapshot again keeps one entry
        refdata.write_snapshot(self.root, source="ecb", date="2026-11-20", files={"raw.csv": ECB.encode()},
                               meta=self.entry, rows={})
        self.assertEqual(len(json.loads((self.root / "MANIFEST.json").read_text())["snapshots"]), 1)

    def test_KG_02_verify_rehashes_every_snapshot(self) -> None:
        self.assertEqual(refdata.verify(self.root), [])
        p = self.root / "ecb" / "2026-11-20" / "raw.csv"
        p.write_bytes(p.read_bytes() + b"x")
        self.assertTrue(any("sha256 mismatch" in e for e in refdata.verify(self.root)))

    def test_KG_02_verify_flags_unlisted_files(self) -> None:
        (self.root / "ecb" / "2026-11-20" / "extra.csv").write_text("a\n")
        self.assertTrue(any("not in MANIFEST" in e for e in refdata.verify(self.root)))

    def test_KG_02_datasheet_inputs_recorded(self) -> None:
        text = refdata.datasheet(json.loads((self.root / "MANIFEST.json").read_text()))
        for needle in ("ecb@2026-11-20", "2026-11-20T00:00:00Z", "info only", "none", "https://example.invalid/l"):
            self.assertIn(needle, text)


class Committed(unittest.TestCase):
    def test_KG_02_committed_snapshots_verify(self) -> None:
        root = ROOT / "data" / "reference"
        self.assertTrue((root / "MANIFEST.json").is_file(), "run `make refdata-fetch` once and commit")
        self.assertEqual(refdata.verify(root), [])
        refs = {s["ref"].split("@")[0] for s in json.loads((root / "MANIFEST.json").read_text())["snapshots"]}
        self.assertEqual(refs, {"ecb", "h10", "gleif", "iso20022"})

    def test_KG_02_committed_datasheet_inputs_current(self) -> None:
        root = ROOT / "data" / "reference"
        expected = refdata.datasheet(json.loads((root / "MANIFEST.json").read_text()))
        self.assertEqual((root / "DATASHEET_INPUTS.md").read_text(), expected, "run `make refdata-verify`")


if __name__ == "__main__":
    unittest.main()
