package com.secondline.ledger.journal;

/** Debit or credit. A reversal swaps every line's side (docs/domain.md "Reversals"). */
public enum Side {
    D, C;

    public Side opposite() {
        return this == D ? C : D;
    }
}
