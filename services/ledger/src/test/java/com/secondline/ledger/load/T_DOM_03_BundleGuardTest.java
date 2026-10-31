package com.secondline.ledger.load;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.ledger.LedgerException;
import java.io.IOException;
import java.nio.file.Path;
import java.util.function.Consumer;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

/** OM-04 §5 ADR-015 T-DOM-03 REQ-006: the loader's gate. Truth keys, canaries and dangling refs never get in. */
class T_DOM_03_BundleGuardTest {
    static final BundleGuard GUARD = new BundleGuard();

    static ObjectNode minimal() {
        try {
            ObjectNode b = (ObjectNode) Contracts.MAPPER.readTree(
                    Path.of(System.getProperty("contracts.root"), "examples/scenario/world_bundle_minimal.json").toFile());
            b.remove("x-validates");
            return b;
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    static LedgerException rejected(ObjectNode bundle) {
        Throwable t = org.assertj.core.api.Assertions.catchThrowable(() -> GUARD.check(bundle));
        assertThat(t).isInstanceOf(LedgerException.class);
        LedgerException e = (LedgerException) t;
        assertThat(e.code()).isEqualTo(ErrorCode.DOMAIN_INVALID);
        return e;
    }

    static ObjectNode with(Consumer<ObjectNode> edit) {
        ObjectNode b = minimal();
        edit.accept(b);
        return b;
    }

    @Test
    void OM_04_minimalExampleAccepted() {
        // break_id, breaks, isin, currency, account and scenario_id are truth-schema names AND visible ones.
        assertThatCode(() -> GUARD.check(minimal())).doesNotThrowAnyException();
    }

    static Stream<Arguments> truthKeyPlacements() {
        return TruthKeys.load().stream().flatMap(k -> Stream.of(
                Arguments.of(k, "", "/" + k),
                Arguments.of(k, "/trades/0", "/trades/0/" + k),
                Arguments.of(k, "/evidence/0/fields", "/evidence/0/fields/" + k)));
    }

    @ParameterizedTest(name = "{0} at {1}")
    @MethodSource("truthKeyPlacements")
    void T_DOM_03_truthKeyAnywhereRejected(String key, String at, String pointer) {
        ObjectNode b = minimal();
        ((ObjectNode) (at.isEmpty() ? b : b.at(at))).put(key, "x");
        assertThat(rejected(b)).hasMessageContaining("truth").hasMessageContaining(pointer);
    }

    @Test
    void T_DOM_03_truthKeysAreTheHiddenOnesNotTheShared() {
        assertThat(TruthKeys.load()).contains("root_cause", "expected_state_delta", "allowed_outcomes",
                "required_evidence_ids", "truth_ref", "canary", "break_type");
        assertThat(TruthKeys.load()).doesNotContain("break_id", "breaks", "isin", "currency", "account", "scenario_id");
    }

    @Test
    void T_DOM_03_truthKeyMatchIgnoresCase() {
        assertThat(rejected(with(b -> b.put("Root_Cause", "fee"))).getMessage()).contains("/Root_Cause");
    }

    @Test
    void T_DOM_03_canaryRejectedAndNeverEchoed() {
        LedgerException e = rejected(with(b -> ((ObjectNode) b.at("/evidence/0")).put("text", "see SLCANARY-9f2c01")));
        assertThat(e).hasMessageContaining("/evidence/0/text").hasMessageNotContaining("SLCANARY-");
    }

    @Test
    void OM_04_schemaViolationNamesPointersOnly() {
        LedgerException e = rejected(with(b -> ((ObjectNode) b.at("/trades/0")).put("price", 12.3456)));
        assertThat(e).hasMessageContaining("/trades/0/price").hasMessageNotContaining("12.3456");
    }

    @Test
    void OM_04_deepNestingRejected() {
        ObjectNode b = minimal();
        ObjectNode n = b.putObject("x");
        for (int i = 0; i < 100; i++) n = n.putObject("x");
        assertThat(rejected(b)).hasMessageContaining("too deep");
    }

    static Stream<Arguments> danglingRefs() {
        return Stream.of(
                Arguments.of("trade → unknown counterparty", "/trades/0/counterparty_id",
                        (Consumer<ObjectNode>) b -> ((ObjectNode) b.at("/trades/0")).put("counterparty_id", "cpt_0000Z999")),
                Arguments.of("counterparty → unknown institution", "/counterparties/0/institution_id",
                        (Consumer<ObjectNode>) b -> ((ObjectNode) b.at("/counterparties/0")).put("institution_id", "ins_0000Z999")),
                Arguments.of("trade → unknown isin", "/trades/0/isin",
                        (Consumer<ObjectNode>) b -> ((ObjectNode) b.at("/trades/0")).put("isin", "XS0000000020")),
                Arguments.of("journal entry → unknown trade", "/journal_entries/0/trade_id",
                        (Consumer<ObjectNode>) b -> ((ObjectNode) b.at("/journal_entries/0")).put("trade_id", "trd_0000Z999")),
                Arguments.of("movement → unknown trade", "/securities_movements/0/trade_id",
                        (Consumer<ObjectNode>) b -> ((ObjectNode) b.at("/securities_movements/0")).put("trade_id", "trd_0000Z999")),
                Arguments.of("break → unknown evidence", "/breaks/0/evidence_ids/0",
                        (Consumer<ObjectNode>) b -> ((ArrayNode) b.at("/breaks/0/evidence_ids")).set(0, "evd_0000Z999")),
                Arguments.of("break → unknown trade", "/breaks/0/trade_ids/0",
                        (Consumer<ObjectNode>) b -> ((ArrayNode) b.at("/breaks/0/trade_ids")).set(0, "trd_0000Z999")),
                Arguments.of("cash line currency ≠ account currency", "/journal_entries/0/lines/0",
                        (Consumer<ObjectNode>) b -> ((ObjectNode) b.at("/journal_entries/0/lines/0")).put("currency", "EUR")),
                Arguments.of("movement isin ≠ account isin", "/securities_movements/0",
                        (Consumer<ObjectNode>) b -> ((ObjectNode) b.at("/securities_movements/0")).put("account", "S100-XS0000000020")),
                Arguments.of("undeclared account", "/journal_entries/0/lines/0/account",
                        (Consumer<ObjectNode>) b -> ((ObjectNode) b.at("/journal_entries/0/lines/0")).put("account", "4300-USD")),
                Arguments.of("duplicate trade id", "/trades/1/trade_id",
                        (Consumer<ObjectNode>) b -> ((ArrayNode) b.get("trades")).add(b.at("/trades/0").deepCopy())),
                Arguments.of("duplicate evidence version", "/evidence/",
                        (Consumer<ObjectNode>) b -> ((ArrayNode) b.get("evidence")).add(b.at("/evidence/0").deepCopy())));
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("danglingRefs")
    void OM_04_danglingOrInconsistentRefsRejected(String name, String pointer, Consumer<ObjectNode> edit) {
        assertThat(rejected(with(edit))).hasMessageContaining(pointer);
    }

    @Test
    void OM_04_rejectionWritesNothingBecauseItRunsBeforeTheTransaction() {
        // BundleGuard is pure: it has no repository and takes only the document.
        assertThat(BundleGuard.class.getDeclaredFields()).allSatisfy(f ->
                assertThat(f.getType().getName()).doesNotContain("Jdbc").doesNotContain("DataSource"));
    }

    @Test
    void OM_04_nonObjectBundleRejected() {
        assertThatThrownBy(() -> GUARD.check(Contracts.MAPPER.getNodeFactory().arrayNode()))
                .isInstanceOf(LedgerException.class);
    }

}
