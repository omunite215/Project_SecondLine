package com.secondline.contracts;

import com.fasterxml.jackson.annotation.JsonProperty;

/** common.schema.json#/$defs/evidence_ref: a cited record at the version the agent read. */
public record EvidenceRef(@JsonProperty("record_id") String recordId, @JsonProperty("version") long version) {}
