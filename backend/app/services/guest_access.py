"""Project cached discovery data into the caller's permitted preview."""

GUEST_SEARCH_PAGE_SIZE = 10
GUEST_SEARCH_VISIBLE = 7
GUEST_REVIEW_VISIBLE = 2


def search_response(data: dict, authenticated: bool) -> dict:
    if authenticated:
        return {**data, "locked_count": 0}
    items = data["items"][:GUEST_SEARCH_VISIBLE]
    return {
        **data,
        "items": items,
        "locked_count": max(0, len(data["items"]) - len(items)),
    }


def reviews_response(items: list, authenticated: bool) -> dict:
    visible = items if authenticated else items[:GUEST_REVIEW_VISIBLE]
    return {"items": visible, "total": len(items), "locked_count": len(items) - len(visible)}
