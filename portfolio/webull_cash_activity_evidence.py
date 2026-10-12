"""Bounded retail cash-page acquisition; no inferred accounting or publication pass."""

import hashlib


def collect_cash_pages(activity_client, account_id, *, max_pages=10):
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValueError("Private account identifier required")
    if type(max_pages) is not int or not 1 <= max_pages <= 10:
        raise ValueError("Bounded page count required")
    token = None
    seen = set()
    records, digests = [], []
    exhausted = False
    for _ in range(max_pages):
        response = activity_client.list_activities(account_id, pagination_key=token)
        if response.status_code != 200:
            raise ValueError("Cash activity page unavailable")
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise TypeError("Retail activity pagination schema unavailable")
        if any(not isinstance(row, dict) for row in payload["data"]):
            raise ValueError("Cash activity record invalid")
        digests.append(hashlib.sha256(response.content).hexdigest())
        # No invented ID, effective timestamp, flow classification or deduplication.
        records.extend(payload["data"])
        next_token = payload.get("pagination_key")
        if next_token is None:
            exhausted = True
            break
        if not isinstance(next_token, str) or not next_token or len(next_token) > 2000:
            raise ValueError("Invalid pagination key")
        if next_token in seen:
            raise ValueError("Repeated pagination key")
        seen.add(next_token)
        token = next_token
    return {
        "schema_version": "webull-cash-page-acquisition-v1",
        "records": records,
        "page_sha256": digests,
        "pages_read": len(digests),
        "returned_records": len(records),
        "currently_returned_pages_exhausted": exhausted,
        "requested_window": "PROVIDER_DEFAULT_LAST_7_DAYS",
        "external_flow_total": None,
        "blockers": [
            "ACTIVITY_PUBLICATION_UNQUALIFIED",
            "ACTIVITY_EFFECTIVE_TIME_UNQUALIFIED",
            "ACCOUNT_ASOF_UNQUALIFIED",
        ]
        + (["ACTIVITY_RECORDS_UNCLASSIFIED"] if records else [])
        + ([] if exhausted else ["ACTIVITY_PAGE_BOUND_REACHED"]),
        "execution_available": False,
        "trial_started": False,
    }
