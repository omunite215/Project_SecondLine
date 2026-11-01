package com.secondline.ledger.read;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.Digests;
import com.secondline.ledger.Bundles;
import com.secondline.ledger.LedgerDb;
import com.secondline.ledger.Services;
import com.secondline.ledger.domain.CashAccount;
import com.secondline.ledger.domain.Currency;
import com.secondline.ledger.domain.Isin;
import com.secondline.ledger.domain.Money;
import com.secondline.ledger.domain.Quantity;
import com.secondline.ledger.domain.SecuritiesAccount;
import com.secondline.ledger.journal.BookingRef;
import com.secondline.ledger.journal.CashEntry;
import com.secondline.ledger.journal.CashLine;
import com.secondline.ledger.journal.SecuritiesEntry;
import com.secondline.ledger.journal.SecuritiesLine;
import com.secondline.ledger.journal.Side;
import com.secondline.ledger.load.TruthKeys;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.ArrayDeque;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

/** OM-04 §10 REQ-001 REQ-002: the read tools' behaviour (as-of versions, provenance, denial) through HTTP. */
class OM_04_ReadApiTest {
    static final MockMvc MVC = Services.readMvc();
    static UUID ns;

    @BeforeAll
    static void load() {
        LedgerDb.migrate();
        ns = Services.namespaces().create();
        Services.loader().load(ns, Bundles.rich());
    }

    static MvcResult call(UUID in, String path) throws Exception {
        return MVC.perform(get("/internal/v1/ns/" + in + path)).andReturn();
    }

    static JsonNode ok(String path) throws Exception {
        MvcResult r = call(ns, path);
        assertThat(r.getResponse().getStatus()).as(path + " " + r.getResponse().getContentAsString()).isEqualTo(200);
        return Contracts.MAPPER.readTree(r.getResponse().getContentAsString());
    }

    static JsonNode error(UUID in, String path, int status, String code) throws Exception {
        MvcResult r = call(in, path);
        assertThat(r.getResponse().getStatus()).as(path).isEqualTo(status);
        JsonNode body = Contracts.MAPPER.readTree(r.getResponse().getContentAsString());
        assertThat(body.get("error_code").asText()).isEqualTo(code);
        assertThat(com.secondline.contracts.SchemaRegistry.load().validate("error_response.schema.json", body)).isEmpty();
        return body;
    }

    @Test
    void OM_04_asOfFutureOrNegativeVersionRejected() throws Exception {
        error(ns, "/positions?as_of_version=1", 422, "DOMAIN_INVALID");
        error(ns, "/positions?as_of_version=-1", 422, "DOMAIN_INVALID");
        error(ns, "/trades/trd_0000B001/bookings?as_of_version=99", 422, "DOMAIN_INVALID");
    }

    @Test
    void OM_04_asOfReturnsHistoricalPositionsAndBookings() throws Exception {
        UUID own = Services.namespaces().create();
        Services.loader().load(own, Bundles.minimal());
        // One more buy of 100 at version 1 (what OM-08 will do inside an action transaction).
        Services.TX.executeWithoutResult(s -> {
            Services.namespaces().bumpVersion(own);
            Services.cash().post(new CashEntry(own, "TRADE", LocalDate.parse("2026-03-03"), List.of(
                    new CashLine(CashAccount.fromCode("1300"), Side.D, Money.of("1234.56", Currency.USD)),
                    new CashLine(CashAccount.fromCode("1110"), Side.C, Money.of("1234.56", Currency.USD)))),
                    new BookingRef("jnl_0000C002", "trd_0000B001", null));
            Services.securities().post(new SecuritiesEntry(own, "TRADE", LocalDate.parse("2026-03-03"), List.of(
                    new SecuritiesLine(SecuritiesAccount.CUSTODY, Side.D, new Isin("XS0000000012"), Quantity.of("100")),
                    new SecuritiesLine(SecuritiesAccount.STREET, Side.C, new Isin("XS0000000012"), Quantity.of("100")))),
                    new BookingRef(null, "trd_0000B001", null));
        });
        JsonNode then = Contracts.MAPPER.readTree(call(own, "/positions?as_of_version=0").getResponse().getContentAsString());
        JsonNode now = Contracts.MAPPER.readTree(call(own, "/positions").getResponse().getContentAsString());
        assertThat(then.at("/positions/0/trading_position").asText()).isEqualTo("300");
        assertThat(then.at("/positions/0/cost").asText()).isEqualTo("3703.68");
        assertThat(then.get("state_version").asLong()).isZero();
        assertThat(now.at("/positions/0/trading_position").asText()).isEqualTo("400");
        assertThat(now.at("/positions/0/cost").asText()).isEqualTo("4938.24");
        assertThat(now.get("state_version").asLong()).isEqualTo(1);
        JsonNode bookingsThen = Contracts.MAPPER.readTree(call(own, "/trades/trd_0000B001/bookings?as_of_version=0")
                .getResponse().getContentAsString());
        assertThat(bookingsThen.get("entries")).hasSize(1);
        JsonNode bookingsNow = Contracts.MAPPER.readTree(call(own, "/trades/trd_0000B001/bookings").getResponse().getContentAsString());
        assertThat(bookingsNow.get("entries")).hasSize(2);
        assertThat(bookingsNow.at("/entries/1/entry_id").asText()).isEqualTo("jnl_0000C002");
    }

    @Test
    void OM_04_reversalShowsUnderItsTrade() throws Exception {
        UUID own = Services.namespaces().create();
        Services.loader().load(own, Bundles.minimal());
        UUID original = LedgerDb.query(LedgerDb.app(), "SELECT entry_id FROM ledger.journal_headers WHERE ns = ?", own) == null
                ? null : UUID.fromString(LedgerDb.query(LedgerDb.app(), "SELECT entry_id FROM ledger.journal_headers WHERE ns = ?", own));
        Services.reversals().reverseCash(own, original, "booked twice by the feed");
        JsonNode b = Contracts.MAPPER.readTree(call(own, "/trades/trd_0000B001/bookings").getResponse().getContentAsString());
        assertThat(b.get("entries")).hasSize(2);
        assertThat(b.at("/entries/1/entry_type").asText()).isEqualTo("REVERSAL");
        assertThat(b.at("/entries/1/reverses_entry_id").asText()).isEqualTo("jnl_0000C001");
        assertThat(b.at("/entries/1/entry_id").asText()).matches("^jnl_[0-9a-f]{16}$");
    }

    @Test
    void OM_04_crossNamespaceReadIsDenied() throws Exception {
        UUID other = Services.namespaces().create();
        Services.loader().load(other, Bundles.with(b -> {
            ((com.fasterxml.jackson.databind.node.ObjectNode) b.at("/trades/0")).put("trade_id", "trd_0000X777");
            ((com.fasterxml.jackson.databind.node.ObjectNode) b.at("/journal_entries/0")).put("trade_id", "trd_0000X777");
            ((com.fasterxml.jackson.databind.node.ObjectNode) b.at("/securities_movements/0")).put("trade_id", "trd_0000X777");
            ((com.fasterxml.jackson.databind.node.ObjectNode) b.at("/securities_movements/1")).put("trade_id", "trd_0000X777");
            ((com.fasterxml.jackson.databind.node.ArrayNode) b.at("/breaks/0/trade_ids")).set(0, "trd_0000X777");
        }));
        error(ns, "/trades/trd_0000X777", 403, "PERMISSION_DENIED");
        error(other, "/trades/trd_0000B001", 403, "PERMISSION_DENIED");
        error(UUID.randomUUID(), "/breaks", 403, "PERMISSION_DENIED");
    }

    @Test
    void OM_04_retiredOrEmptyNamespaceIsDenied() throws Exception {
        UUID empty = Services.namespaces().create();
        error(empty, "/breaks", 403, "PERMISSION_DENIED");
        UUID retired = Services.namespaces().create();
        Services.loader().load(retired, Bundles.minimal());
        Services.namespaces().retire(retired);
        error(retired, "/trades/trd_0000B001", 403, "PERMISSION_DENIED");
    }

    @Test
    void OM_04_malformedParametersAreDomainInvalidAndNotEchoed() throws Exception {
        JsonNode body = error(ns, "/trades/trd_EVAL0001", 422, "DOMAIN_INVALID");
        assertThat(body.get("message").asText()).doesNotContain("EVAL");
        error(ns, "/positions?isin=nope", 422, "DOMAIN_INVALID");
        error(ns, "/fx?base=EUR&quote=XXX&as_of_date=2026-03-02", 422, "DOMAIN_INVALID");
        error(ns, "/breaks?status=IN_REVIEW", 422, "DOMAIN_INVALID");
        error(ns, "/custodian-statement", 422, "DOMAIN_INVALID");
        MvcResult badNs = MVC.perform(get("/internal/v1/ns/not-a-uuid/breaks")).andReturn();
        assertThat(badNs.getResponse().getStatus()).isEqualTo(422);
    }

    @Test
    void OM_04_evidenceContentIsUntrustedAndHashed() throws Exception {
        JsonNode e = ok("/evidence/evd_0000E001");
        assertThat(e.get("untrusted").asBoolean()).isTrue();
        String content = e.get("content").asText();
        assertThat(e.get("content_sha256").asText()).isEqualTo(Digests.sha256(content.getBytes(StandardCharsets.UTF_8)));
        assertThat(CanonicalJson.parse(content).at("/fields/debit_amount").asText()).isEqualTo("3703.69");
        assertThat(CanonicalJson.canonicalize(content)).isEqualTo(content);
    }

    @Test
    void OM_04_evidenceBackedReadsCiteTheRecordVersion() throws Exception {
        JsonNode s = ok("/trades/trd_0000B001/settlement");
        assertThat(s.get("status").asText()).isEqualTo("SETTLED");
        assertThat(s.get("settled_quantity").asText()).isEqualTo("300");  // SETTLED without a quantity = the trade's
        assertThat(s.get("record_version").asInt()).isEqualTo(1);
        JsonNode c = ok("/custodian-statement?as_of_date=2026-03-02");
        assertThat(c.at("/lines/0/record_id").asText()).isEqualTo("evd_0000E004");
        assertThat(c.at("/lines/0/quantity").asText()).isEqualTo("300");
        assertThat(ok("/custodian-statement?as_of_date=2026-03-01").get("lines")).isEmpty();
        JsonNode ca = ok("/corporate-actions?isin=XS0000000012");
        assertThat(ca.at("/events/0/type").asText()).isEqualTo("SPLIT");
        assertThat(ca.at("/events/0/ratio_numerator").asInt()).isEqualTo(2);
        assertThat(ok("/reference-data/ssi_0000E006").get("record_type").asText()).isEqualTo("SSI");
        assertThat(ok("/reference-data/cpt_0000H001").at("/attributes/name").asText()).isEqualTo("Fictional Broker AG");
        assertThat(ok("/reference-data/isn_XS0000000012").get("record_type").asText()).isEqualTo("SECURITY");
        assertThat(ok("/fx?base=EUR&quote=USD&as_of_date=2026-03-02").get("rate").asText()).isEqualTo("1.0850");
        error(ns, "/fx?base=EUR&quote=USD&as_of_date=2026-03-03", 403, "PERMISSION_DENIED");
    }

    @Test
    void OM_04_breaksShowSymptomsAndLinks() throws Exception {
        JsonNode all = ok("/breaks");
        assertThat(all.at("/breaks/0/symptom").asText()).isEqualTo("CASH_DIFFERENCE");
        assertThat(all.at("/breaks/0/difference").asText()).isEqualTo("-0.01");
        assertThat(ok("/breaks?status=RESOLVED").get("breaks")).isEmpty();
        JsonNode one = ok("/breaks/brk_0000F001");
        assertThat(one.get("evidence_ids")).hasSize(3);
        assertThat(one.get("opened_at").asText()).isEqualTo("2026-03-02T16:00:00Z");
    }

    @Test
    void OM_04_noTruthInAnyResponse() throws Exception {
        // A key is a leak if it's a truth-only name the tool's own output schema doesn't declare (read_positions
        // legitimately returns "positions", which truth also uses).
        for (var p : OM_04_ReadContractTest.PATHS.entrySet()) {
            String path = p.getValue();
            JsonNode body = ok(path);
            java.util.Set<String> declared = OM_04_ReadContractTest.declaredNames(p.getKey());
            ArrayDeque<JsonNode> todo = new ArrayDeque<>(List.of(body));
            while (!todo.isEmpty()) {
                JsonNode n = todo.pop();
                n.properties().forEach(e -> {
                    if (!declared.contains(e.getKey())) {
                        assertThat(TruthKeys.load()).as(path).doesNotContain(e.getKey().toLowerCase());
                    }
                });
                n.forEach(todo::push);
                if (n.isTextual()) assertThat(n.asText().toLowerCase()).doesNotContain("slcanary-");
            }
            assertThat(body.toString()).doesNotContainPattern("B[1-8]_[A-Z]");
        }
    }
}
