package com.secondline.ledger.journal;

import java.time.OffsetDateTime;

/**
 * Optional provenance for a ledger entry: the opaque ref the agent cites (evidence_ref.record_id), the trade it
 * books and when it was booked. Without one the DB draws a ref and stamps posted_at = now().
 */
public record BookingRef(String ref, String tradeId, OffsetDateTime postedAt) {}
