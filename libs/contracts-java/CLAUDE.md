# libs/contracts-java — contract types, validation, JCS, digests (owner: Om; shapes owned by both)
Rules: .claude/rules/contracts.md. The schemas in packages/contracts are the source of truth; this library never redefines a shape.
```text
src/main/java/com/secondline/contracts/
  SchemaRegistry      validate(target, JsonNode) → errors; 2020-12, classpath copy of the schemas, no network; unknown schema throws
  CanonicalJson       RFC 8785 JCS, integers only (|n| ≤ 2^53−1); strict parse (no duplicate keys)
  Digests             sha256:<hex>, sha256Canonical(node)
  ActionDigest        ADR-011 digest over x-action-digest.include (actions/proposed_action.schema.json)
  Contracts.MAPPER    strict Jackson mapper for the records (unknown fields fail)
  ProposedAction EvidenceRef ErrorResponse   hand-written records; RecordParityTest pins them to the schemas
src/generated/java/   GENERATED enums (ErrorCode ReasonCode ActionType Decision); never edit; `make codegen-java`
```
Commands: `make codegen-java` (committed output; kit test fails on a diff) · `./gradlew :libs:contracts-java:test`
Golden digest vectors: packages/contracts/test-vectors/action_digest.json (Python-computed; Java must match).
Tests read packages/contracts/examples directly (`contracts.root` system property), the same files `make contracts-check` reads, so the Java and Python validators must agree.
