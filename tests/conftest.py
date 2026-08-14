import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Any of the 10 customers seeded by backend_v3/advisor/synthetic_data.py.
KNOWN_CUSTOMER_ID = "cust_00570"  # John Kemp
UNKNOWN_CUSTOMER_ID = "cust_does_not_exist"
