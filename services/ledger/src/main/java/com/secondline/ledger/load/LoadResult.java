package com.secondline.ledger.load;

import java.util.UUID;

/** Outcome of a load: the bundle's hash (snapshot id), the ns state version, and whether it was already there. */
public record LoadResult(UUID ns, String snapshotHash, long stateVersion, boolean alreadyLoaded) {}
