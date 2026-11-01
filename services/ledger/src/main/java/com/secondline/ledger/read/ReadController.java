package com.secondline.ledger.read;

import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Gateway → ledger read routes, one per §10 read tool (contracts openapi/ledger-internal.yaml). The gateway
 * maps run → ns; run_id never reaches the ledger. Realm authentication arrives with OM-07, a gate for SH-07;
 * until then any container on the compose network can call these routes, and the host only via 127.0.0.1.
 */
@RestController
@RequestMapping("/internal/v1/ns/{ns}")
public class ReadController {
    private final ReadService reads;

    public ReadController(ReadService reads) {
        this.reads = reads;
    }

    @GetMapping("/breaks")
    public ObjectNode listBreaks(@PathVariable UUID ns, @RequestParam(required = false) String status) {
        return reads.listBreaks(ns, status);
    }

    @GetMapping("/breaks/{breakId}")
    public ObjectNode getBreak(@PathVariable UUID ns, @PathVariable String breakId) {
        return reads.getBreak(ns, breakId);
    }

    @GetMapping("/trades/{tradeId}")
    public ObjectNode readTrade(@PathVariable UUID ns, @PathVariable String tradeId,
                                @RequestParam(name = "as_of_version", required = false) Long asOf) {
        return reads.readTrade(ns, tradeId, asOf);
    }

    @GetMapping("/trades/{tradeId}/bookings")
    public ObjectNode readBookings(@PathVariable UUID ns, @PathVariable String tradeId,
                                   @RequestParam(name = "as_of_version", required = false) Long asOf) {
        return reads.readBookings(ns, tradeId, asOf);
    }

    @GetMapping("/trades/{tradeId}/settlement")
    public ObjectNode readSettlementStatus(@PathVariable UUID ns, @PathVariable String tradeId) {
        return reads.readSettlementStatus(ns, tradeId);
    }

    @GetMapping("/positions")
    public ObjectNode readPositions(@PathVariable UUID ns, @RequestParam(required = false) String isin,
                                    @RequestParam(name = "as_of_version", required = false) Long asOf) {
        return reads.readPositions(ns, isin, asOf);
    }

    @GetMapping("/custodian-statement")
    public ObjectNode readCustodianStatement(@PathVariable UUID ns, @RequestParam(name = "as_of_date") String asOfDate,
                                             @RequestParam(required = false) String isin) {
        return reads.readCustodianStatement(ns, asOfDate, isin);
    }

    @GetMapping("/corporate-actions")
    public ObjectNode readCorporateActions(@PathVariable UUID ns, @RequestParam String isin) {
        return reads.readCorporateActions(ns, isin);
    }

    @GetMapping("/evidence/{recordId}")
    public ObjectNode readEvidence(@PathVariable UUID ns, @PathVariable String recordId) {
        return reads.readEvidence(ns, recordId);
    }

    @GetMapping("/reference-data/{recordId}")
    public ObjectNode readReferenceData(@PathVariable UUID ns, @PathVariable String recordId) {
        return reads.readReferenceData(ns, recordId);
    }

    @GetMapping("/fx")
    public ObjectNode readFxSnapshot(@PathVariable UUID ns, @RequestParam String base, @RequestParam String quote,
                                     @RequestParam(name = "as_of_date") String asOfDate) {
        return reads.readFxSnapshot(ns, base, quote, asOfDate);
    }
}
