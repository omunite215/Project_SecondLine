package com.secondline.contracts;

/** A document can't be canonicalised, validated or digested. Callers fail closed (golden rule 7). */
public class ContractException extends RuntimeException {
    public ContractException(String message) {
        super(message);
    }

    public ContractException(String message, Throwable cause) {
        super(message, cause);
    }
}
