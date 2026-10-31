package com.secondline.ledger;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;

/** OM-03 golden rule 7: every code the ledger raises exists in packages/contracts/errors.json (and isn't grader-only). */
class OM_03_ErrorCodesTest {
    static final Path ROOT = Path.of(System.getProperty("repo.root"));

    @Test
    void OM_03_everyRaisedCodeIsAContractCode() throws IOException {
        String errors = Files.readString(ROOT.resolve("packages/contracts/errors.json"));
        Set<String> raised = new TreeSet<>();
        Pattern literal = Pattern.compile("new LedgerException\\(\\s*\"([A-Z_]+)\"");
        try (Stream<Path> files = Files.walk(ROOT.resolve("services/ledger/src/main/java"))) {
            for (Path f : files.filter(p -> p.toString().endsWith(".java")).toList()) {
                Matcher m = literal.matcher(Files.readString(f));
                while (m.find()) raised.add(m.group(1));
            }
        }
        assertThat(raised).isNotEmpty();
        for (String code : raised) {
            assertThat(errors).as(code).contains("\"code\": \"" + code + "\"");
            assertThat(code).isNotEqualTo("ORACLE_MISMATCH"); // grader-only
        }
    }
}
