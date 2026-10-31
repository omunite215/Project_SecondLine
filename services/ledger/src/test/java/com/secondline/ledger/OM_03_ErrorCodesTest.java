package com.secondline.ledger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.secondline.contracts.generated.ErrorCode;
import org.junit.jupiter.api.Test;

/**
 * OM-03 golden rule 7: the ledger raises only errors.json codes. The type guarantees that (ErrorCode is
 * generated from errors.json, OM-02); what's left to pin is that a grader-only code can never be raised.
 */
class OM_03_ErrorCodesTest {

    @Test
    void OM_03_graderOnlyCodeCannotBeRaised() {
        assertThatThrownBy(() -> new LedgerException(ErrorCode.ORACLE_MISMATCH, "x"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void OM_03_codeAndHttpStatusComeFromTheContract() {
        LedgerException e = LedgerException.domainInvalid("bad");
        assertThat(e.code()).isEqualTo(ErrorCode.DOMAIN_INVALID);
        assertThat(e.code().httpStatus()).hasValue(422);
        assertThat(e).hasMessage("DOMAIN_INVALID: bad");
    }
}
