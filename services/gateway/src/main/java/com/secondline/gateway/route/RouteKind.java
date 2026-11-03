package com.secondline.gateway.route;

/** How the gateway serves a tool (OM-05 Task 3). */
public enum RouteKind {
    /** GET on the ledger's internal read API. */
    READ,
    /** POST the ProposedAction unchanged to the ledger's actions endpoint. */
    ACTION,
    /** Handled in the gateway, never touches the ledger (ADR-014: simulated, budgeted messaging). */
    SIMULATED,
    /** No ledger path yet (owning card noted on the route); answered with RETRYABLE_UNAVAILABLE. */
    UNROUTED
}
