"""
Risk chain: underwriting, pricing and claims.

Everything the advisor-facing modules do for distribution, these do for risk
decisions -- on the same warehouse. DuckDB carries portfolio-scale facts,
Neo4j carries the provenance walk for a single case, and the rules store plus
decision log make any past decision reconstructable against the rule text that
was actually in force when it was made.
"""
