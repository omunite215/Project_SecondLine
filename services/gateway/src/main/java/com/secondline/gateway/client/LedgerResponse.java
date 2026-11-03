package com.secondline.gateway.client;

import com.fasterxml.jackson.databind.JsonNode;

/** A ledger answer the gateway may pass on: 2xx, or a 4xx whose body is a contract error_response. */
public record LedgerResponse(int status, JsonNode body) {}
