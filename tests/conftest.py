import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Any of the 10 customers seeded by backend_v3/advisor/synthetic_data.py.
KNOWN_CUSTOMER_ID = "cust_00570"  # John Kemp
UNKNOWN_CUSTOMER_ID = "cust_does_not_exist"

# This suite runs against the live Neo4j/Qdrant instance rather than mocks,
# which is deliberate — but it means test writes land in the same graph the
# demo reads from. Tests that create memories name them "<prefix> <uuid4>",
# and those artifacts were repeatedly showing up in the deployed app (as a
# customer's most recent life event, and inside generated briefings).
#
# This fixture sweeps them after the session. It matches only the exact
# shape tests generate — a known prefix followed by a bare UUID — so real
# customer data can never match it.
_TEST_VALUE_PATTERN = (
    r"^(test memory|rejected need|approved need|edited|life event|preference|concern|goal|need) "
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


@pytest.fixture(scope="session", autouse=True)
def purge_test_artifacts():
    yield
    try:
        from backend_v3.graph_store.neo4j_client import run_write

        # Scanning every property is what catches promoted nodes, whose text
        # lives under different keys (PendingMemory.value, Need.description,
        # Topic.name, LifeEvent.description).
        run_write(
            "MATCH (n) WHERE any(k IN keys(n) WHERE n[k] IS :: STRING "
            "  AND n[k] =~ $pattern) "
            "DETACH DELETE n",
            {"pattern": _TEST_VALUE_PATTERN},
        )
    except Exception as exc:  # never fail a green run over cleanup
        print(f"[conftest] artifact cleanup skipped: {type(exc).__name__}: {exc}")
