package com.secondline.ledger.positions;

import com.secondline.ledger.domain.Isin;
import com.secondline.ledger.domain.SecuritiesAccount;
import com.secondline.ledger.journal.SecuritiesLine;
import com.secondline.ledger.journal.Side;
import java.math.BigDecimal;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;

/**
 * Positions from the securities ledger only (never cash, §5). `apply` maintains the stored rows inside
 * the posting transaction; `recompute` derives them from securities_lines, and the two must agree.
 */
@Component
public class PositionProjection {
    private static final String RECOMPUTE = """
            SELECT isin,
                   sum(CASE WHEN account_code IN ('S100', 'S200') THEN signed ELSE 0 END) AS trading,
                   sum(CASE WHEN account_code = 'S100' THEN signed ELSE 0 END) AS settled
            FROM (SELECT isin, account_code, CASE side WHEN 'D' THEN quantity ELSE -quantity END AS signed
                  FROM ledger.securities_lines WHERE ns = ?) l
            GROUP BY isin""";

    private final JdbcClient jdbc;

    public PositionProjection(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /** Must run inside the transaction that inserts these lines. */
    public void apply(UUID ns, List<SecuritiesLine> lines) {
        Map<Isin, Position> delta = new HashMap<>();
        for (SecuritiesLine l : lines) {
            BigDecimal q = l.side() == Side.D ? l.qty().units() : l.qty().units().negate();
            BigDecimal trading = l.account() == SecuritiesAccount.STREET ? BigDecimal.ZERO : q;
            BigDecimal settled = l.account() == SecuritiesAccount.CUSTODY ? q : BigDecimal.ZERO;
            delta.merge(l.isin(), new Position(trading, settled),
                    (a, b) -> new Position(a.trading().add(b.trading()), a.settled().add(b.settled())));
        }
        delta.forEach((isin, d) -> jdbc.sql("""
                        INSERT INTO ledger.positions (ns, isin, trading_qty, settled_qty) VALUES (?, ?, ?, ?)
                        ON CONFLICT (ns, isin) DO UPDATE SET trading_qty = positions.trading_qty + EXCLUDED.trading_qty,
                                                             settled_qty = positions.settled_qty + EXCLUDED.settled_qty""")
                .params(ns, isin.value(), d.trading(), d.settled()).update());
    }

    public Map<Isin, Position> recompute(UUID ns) {
        Map<Isin, Position> out = new HashMap<>();
        jdbc.sql(RECOMPUTE).param(ns).query(rs -> {
            out.put(new Isin(rs.getString(1)), new Position(rs.getBigDecimal(2), rs.getBigDecimal(3)));
        });
        return out;
    }

    public Position stored(UUID ns, Isin isin) {
        return jdbc.sql("SELECT trading_qty, settled_qty FROM ledger.positions WHERE ns = ? AND isin = ?")
                .params(ns, isin.value())
                .query((rs, i) -> new Position(rs.getBigDecimal(1), rs.getBigDecimal(2)))
                .optional().orElse(Position.ZERO);
    }
}
