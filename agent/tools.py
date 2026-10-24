"""Homework 1: the remaining commerce-agent tools.

The three lecture tools (`search_help_center`, `get_order`, `issue_refund`)
are implemented in agent/agent.py and are worked examples of the pattern:
check permissions first, go through agent/db.py for data, and return a
structured dict, never a prose error. The homework tools follow the same
pattern. agent/agent.py already wraps each function below as an SDK tool, so
once a function works here it works in chat with no further wiring.

Result convention (see agent/auth.py):
  - Success: a dict with "ok": True plus the payload fields named in each
    docstring.
  - Failure: {"ok": False, "error": <code>, "reason": <human-readable str>}.

Run the contract tests with: uv run pytest tests/test_hw_holes.py -k hw1
They are marked xfail and flip to passing as you implement each function.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from agent import db
from agent.auth import AuthContext, can_cancel_order, can_view_order, permission_denied
from agent.config import load_facts
from agent.helpcenter import load_policy_docs
from agent.killswitch import kill_switch
from seed.eligibility import effective_return_window_days

MAX_SEARCH_LIMIT = 25
DEFAULT_ORDER_LIMIT = 20


def get_policy(ctx: AuthContext, policy_id: str) -> dict[str, Any]:
    """Fetch one policy doc by its exact id. Risk tier: read.

    Every role may read every policy doc (the corpus is public help-center
    content), so this tool needs no permission check.

    Args:
        ctx: The caller's auth context. Unused here, but every tool takes it.
        policy_id: An exact policy id, e.g. "cw-returns" or
            "store-juniper-home-goods-policy". Matching is exact and
            case-sensitive; ids are the `policy_id` front-matter field of the
            files in data/policies/.

    Returns:
        On success: {"ok": True, "policy_id": str, "title": str,
        "audience": str, "body": str} where body is the markdown body of the
        doc without the front matter.
        If no doc has that id: {"ok": False, "error": "not_found",
        "reason": ...} naming the id that was requested.

    Implementation notes:
        agent.helpcenter.load_policy_docs() returns every parsed doc.
    """
    for doc in load_policy_docs():
        if doc.policy_id == policy_id:
            return {
                "ok": True,
                "policy_id": doc.policy_id,
                "title": doc.title,
                "audience": doc.audience,
                "body": doc.body,
            }
    return {"ok": False, "error": "not_found", "reason": f"no policy doc with id {policy_id!r}"}


def search_products(
    ctx: AuthContext,
    query: str,
    store: str | None = None,
    max_price_usd: float | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search the product catalog. Risk tier: read.

    Every role may search products. Matching is deterministic keyword
    matching, not semantic search: a product matches when every whitespace
    token of `query` appears case-insensitively as a substring of the
    product's title or description.

    Args:
        ctx: The caller's auth context.
        query: Free-text query. Must be non-empty after stripping whitespace;
            otherwise return {"ok": False, "error": "invalid_argument",
            "reason": ...}.
        store: Optional store filter. Matched with
            agent.db.get_store_by_name (case-insensitive name or slug). If
            given and no store matches, return {"ok": False, "error":
            "not_found", "reason": ...} naming the store string.
        max_price_usd: Optional inclusive price ceiling. If given and not
            strictly positive, return an "invalid_argument" error.
        limit: Maximum products to return. Clamp to the range
            [1, MAX_SEARCH_LIMIT]; do not error on out-of-range values.

    Returns:
        {"ok": True, "products": [...], "count": <len(products)>} where each
        product is {"product_id": int, "store_id": int, "title": str,
        "price_usd": float}. Sort matches by price_usd ascending, then by
        product_id ascending, and truncate to `limit`. No matches is still a
        success: {"ok": True, "products": [], "count": 0}.

    Implementation notes:
        agent.db.list_products(conn, store_id) gives the candidate set.
        Use `with db.connection() as conn:` to close the database automatically.
    """
    tokens = query.lower().split()
    if not tokens:
        return {"ok": False, "error": "invalid_argument", "reason": "query must not be empty"}
    if max_price_usd is not None and max_price_usd <= 0:
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": f"max_price_usd must be positive, got {max_price_usd}",
        }
    limit = max(1, min(limit, MAX_SEARCH_LIMIT))

    with db.connection() as conn:
        store_id = None
        if store is not None:
            found = db.get_store_by_name(conn, store)
            if found is None:
                return {"ok": False, "error": "not_found", "reason": f"no store named {store!r}"}
            store_id = found.id
        products = db.list_products(conn, store_id)

    matches = [
        p
        for p in products
        if all(t in p.title.lower() or t in p.description.lower() for t in tokens)
        and (max_price_usd is None or p.price_usd <= max_price_usd)
    ]
    matches.sort(key=lambda p: (p.price_usd, p.id))
    results = [
        {"product_id": p.id, "store_id": p.store_id, "title": p.title, "price_usd": p.price_usd}
        for p in matches[:limit]
    ]
    return {"ok": True, "products": results, "count": len(results)}


def list_my_orders(ctx: AuthContext) -> dict[str, Any]:
    """List recent orders in the caller's own scope. Risk tier: read.

    Role behavior, straight from the access matrix in SPEC.md:
        - shopper: the caller's own orders.
        - merchant: the caller's store's orders (ctx.store_id).
        - support: support staff have no orders of their own and look up
          specific orders with get_order instead, so return {"ok": False,
          "error": "invalid_argument", "reason": ...} saying exactly that.

    Returns:
        For shopper and merchant: {"ok": True, "orders": [...],
        "count": <len(orders)>} where each order is
        agent.db.Order.to_public_dict() and the list holds at most
        DEFAULT_ORDER_LIMIT orders, newest first (agent.db.list_orders_for_user
        and list_orders_for_store already sort and limit this way).

    Implementation notes:
        No permission check is needed beyond the role dispatch, because the
        scope is baked into which query you run. That is the point of the
        tool: the model cannot ask for someone else's orders through it.
    """
    if ctx.role == "support":
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": "support staff have no orders of their own; look up a specific order with get_order",
        }
    with db.connection() as conn:
        if ctx.role == "shopper":
            orders = db.list_orders_for_user(conn, ctx.user_id, limit=DEFAULT_ORDER_LIMIT)
        elif ctx.role == "merchant" and ctx.store_id is not None:
            orders = db.list_orders_for_store(conn, ctx.store_id, limit=DEFAULT_ORDER_LIMIT)
        else:
            return permission_denied(f"role {ctx.role!r} cannot list orders")
    results = [o.to_public_dict() for o in orders]
    return {"ok": True, "orders": results, "count": len(results)}


def cancel_order(ctx: AuthContext, order_id: int, reason: str) -> dict[str, Any]:
    """Cancel an order. Risk tier: write.

    This is the homework's write tool, and it must enforce two independent
    rules in this order:

    1. The access matrix (scope): use agent.auth.can_cancel_order. Shoppers
       may cancel only their own orders, merchants only their own store's
       orders, support any order. On failure return
       agent.auth.permission_denied(...) with a reason naming the role and
       the order id. Scope is checked before the status rule so that an
       out-of-scope caller learns nothing about the order's state.
    2. The pre-shipment rule (facts.yaml `cancel_cutoff`): only orders whose
       status is exactly "placed" can be cancelled, for every role. If the
       order is in scope but its status is not "placed", return
       {"ok": False, "error": "not_eligible", "reason": ...} that names the
       current status and states that orders can be cancelled only before
       shipment.

    Args:
        ctx: The caller's auth context.
        order_id: The order to cancel.
        reason: Free-text reason from the user; not validated.

    Returns:
        If no order has this id: {"ok": False, "error": "not_found",
        "reason": ...}.
        On success: {"ok": True, "order_id": order_id, "status": "cancelled"}
        after persisting the new status with agent.db.set_order_status.

    Implementation notes:
        Fetch with agent.db.get_order. Note the argument order of
        can_cancel_order(ctx, order_user_id, order_store_id).

    The Module 4 kill switch is checked first (before the scope and
    status rules and before your code), so that a paused write tool touches
    nothing. It is provided; the default ("off") returns None and falls
    through to your implementation.
    """
    paused = kill_switch("cancel_order")
    if paused is not None:
        return {"ok": False, "error": "paused", "reason": paused}
    with db.connection() as conn:
        order = db.get_order(conn, order_id)
        if order is None:
            return {"ok": False, "error": "not_found", "reason": f"no order #{order_id}"}
        if not can_cancel_order(ctx, order.user_id, order.store_id):
            return permission_denied(f"{ctx.role} may not cancel order #{order_id}")
        if order.status != "placed":
            return {
                "ok": False,
                "error": "not_eligible",
                "reason": (
                    f"order #{order_id} is {order.status}; orders can be cancelled "
                    "only before shipment"
                ),
            }
        db.set_order_status(conn, order_id, "cancelled")
    return {"ok": True, "order_id": order_id, "status": "cancelled"}


def find_order(ctx: AuthContext, query: str) -> dict[str, Any]:
    """Search the caller's orders by product name. Risk tier: read.

    Takes a natural-language query (e.g., "earmuffs I bought last week")
    and searches the authenticated user's orders for products whose name
    matches. Use fuzzy string matching (e.g., thefuzz.fuzz.partial_ratio
    or case-insensitive substring matching) to find orders whose product name is close to the
    query.

    Access rules: a shopper searches only the shopper's own orders, a
    merchant searches orders from the merchant's store, and support staff
    can search any orders. Use agent.db.list_order_search_candidates with
    user_id=ctx.user_id for shoppers, store_id=ctx.store_id for merchants,
    or all_orders=True only for support. Derive the scope from ctx, never
    from the query; reject unsupported roles or missing required identity.
    Use agent.db.list_products to map product IDs to product titles.

    The helper returns the complete authorised scope, newest first with
    order ID descending as the tie-breaker. Match product names first,
    preserve that order, then return at most five matches. Do not search
    only the 20 most recent orders. Convert matches with to_public_dict().

    Args:
        ctx: The caller's auth context.
        query: A natural-language description of the product.

    Returns:
        {"ok": True, "orders": [...]} with a list of matching orders
        (at most 5), each as the dict returned by agent.db. If no orders
        match, return {"ok": True, "orders": []}.
    """
    if ctx.role == "shopper":
        scope = {"user_id": ctx.user_id}
    elif ctx.role == "merchant" and ctx.store_id is not None:
        scope = {"store_id": ctx.store_id}
    elif ctx.role == "support":
        scope = {"all_orders": True}
    else:
        return permission_denied(f"role {ctx.role!r} cannot search orders")

    query_words = _words(query) - _FILLER_WORDS
    if not query_words:
        return {"ok": True, "orders": []}

    with db.connection() as conn:
        titles = {p.id: p.title for p in db.list_products(conn)}
        candidates = db.list_order_search_candidates(conn, **scope)
    matches = [o for o in candidates if query_words & _words(titles.get(o.product_id, ""))]
    return {"ok": True, "orders": [o.to_public_dict() for o in matches[:5]]}


# Conversational words that never identify a product in find_order queries.
_FILLER_WORDS = {
    "a", "an", "the", "i", "me", "my", "mine", "we", "our", "you", "it", "that", "this",
    "of", "for", "from", "to", "in", "on", "at", "with", "and", "or", "is", "was",
    "want", "wanted", "need", "bought", "buy", "ordered", "order", "orders", "purchased",
    "got", "get", "return", "find", "where", "which", "last", "week", "month", "year",
    "ago", "recently", "some", "one", "item", "thing", "product",
}


def _words(text: str) -> set[str]:
    """Lowercase alphanumeric words with a trailing plural "s" removed."""
    words = "".join(c if c.isalnum() else " " for c in text.lower()).split()
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words}


# ---------------------------------------------------------------------------
# Student tool (HW1 Part A extension): order details with return deadline.
# ---------------------------------------------------------------------------


def get_order_details(ctx: AuthContext, order_id: int) -> dict[str, Any]:
    """Order lookup with the product name and the return deadline. Risk tier: read.

    Same access rule as get_order: the caller must be allowed to view the
    order (agent.auth.can_view_order), checked before anything about the
    order is returned.

    The return window is the store's override when it has one, otherwise the
    platform default (facts.yaml `return_window_days`), chosen by
    seed.eligibility.effective_return_window_days. The deadline is the
    delivery date plus the window (inclusive, matching is_refund_eligible),
    and days are counted from the world's fixed date (db.world_asof).

    Returns:
        On success: {"ok": True, "order": {...}} where order is
        Order.to_public_dict() plus "product_title", "store_name",
        "return_window_days", "return_window_policy_id" (the policy to
        cite), "return_deadline" (ISO date, or None if not yet delivered),
        "days_left" (0 once the deadline has passed), and
        "days_past_deadline" (0 while the window is open), and
        "data_issues" (a list of inconsistencies found in the record). The
        deadline fields are None for undelivered orders and when the
        record's dates are inconsistent; product_title is None when the
        product is missing or untitled.
        Errors: "not_found" for an unknown order, "permission_denied" for an
        order outside the caller's scope.
    """
    with db.connection() as conn:
        order = db.get_order(conn, order_id)
        if order is None:
            return {"ok": False, "error": "not_found", "reason": f"no order #{order_id}"}
        if not can_view_order(ctx, order.user_id, order.store_id):
            return permission_denied(
                f"role '{ctx.role}' (user {ctx.user_id}) may not view order #{order_id}"
            )
        store = db.get_store(conn, order.store_id)
        product = next(
            (p for p in db.list_products(conn, order.store_id) if p.id == order.product_id), None
        )
        as_of = db.world_asof(conn)

    override = store.return_window_days_override if store else None
    window = effective_return_window_days(load_facts()["return_window_days"], override)
    policy_id = "cw-returns"
    if override is not None:
        store_policy = f"store-{store.slug}-policy"
        if any(doc.policy_id == store_policy for doc in load_policy_docs()):
            policy_id = store_policy

    # Inconsistent records are reported, never computed from (seeded data
    # quality cases in the `data_quality_cases` table).
    data_issues = []
    if product is None:
        data_issues.append("the order's product does not belong to the order's store")
    elif not product.title.strip():
        data_issues.append("the product has no title")
    if order.status == "delivered" and order.delivered_at is None:
        data_issues.append("the order is marked delivered but has no delivery date")
    if order.shipped_at and order.delivered_at and order.shipped_at > order.delivered_at:
        data_issues.append("the shipment date is after the delivery date")
    dates_reliable = not any("date" in issue for issue in data_issues)

    deadline = days_left = days_past = None
    if order.delivered_at is not None and dates_reliable:
        deadline_date = order.delivered_at + timedelta(days=window)
        remaining = (deadline_date - as_of).days
        deadline = deadline_date.isoformat()
        days_left, days_past = max(remaining, 0), max(-remaining, 0)

    payload = order.to_public_dict()
    payload.update(
        product_title=product.title if product and product.title.strip() else None,
        store_name=store.name if store else None,
        return_window_days=window,
        return_window_policy_id=policy_id,
        return_deadline=deadline,
        days_left=days_left,
        days_past_deadline=days_past,
        data_issues=data_issues,
    )
    return {"ok": True, "order": payload}
