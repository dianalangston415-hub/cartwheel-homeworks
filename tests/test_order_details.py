"""The student-added get_order_details tool (HW1 Part A extension), tested
offline through its logic function."""

from __future__ import annotations

import sqlite3

from agent import tools
from agent.agent import TOOLS_BY_ROLE
from agent.auth import AuthContext

SHOPPER_1 = AuthContext(user_id=1, role="shopper")
MERCHANT_STORE_2 = AuthContext(user_id=9002, role="merchant", store_id=2)
SUPPORT = AuthContext(user_id=9501, role="support")


def test_order_details_adds_product_name_and_deadline(world: dict) -> None:
    order = tools.get_order_details(SHOPPER_1, 4127)["order"]
    assert order["product_title"] == "Heavy-Duty Vase"
    assert order["store_name"] == "Blue Heron Ceramics"
    assert order["return_window_days"] == 30
    assert order["return_window_policy_id"] == "cw-returns"
    assert order["return_deadline"] == "2026-07-19"
    assert order["days_left"] == 18
    assert order["days_past_deadline"] == 0


def test_order_details_reports_days_past_an_expired_deadline(world: dict) -> None:
    order = tools.get_order_details(SHOPPER_1, 3980)["order"]
    assert order["refund_eligible"] is False
    assert order["return_deadline"] == "2026-06-16"
    assert order["days_left"] == 0
    assert order["days_past_deadline"] == 15


def test_order_details_uses_the_store_override_and_cites_it(world: dict) -> None:
    conn = sqlite3.connect(world["db"])
    try:
        order_id = conn.execute(
            "SELECT o.id FROM orders o JOIN stores s ON s.id = o.store_id "
            "WHERE s.name = 'Saltbox Pantry' AND o.delivered_at IS NOT NULL LIMIT 1"
        ).fetchone()[0]
    finally:
        conn.close()
    order = tools.get_order_details(SUPPORT, order_id)["order"]
    assert order["return_window_days"] == 7
    assert order["return_window_policy_id"] == "store-saltbox-pantry-policy"


def test_order_details_deadline_agrees_with_refund_eligibility(world: dict) -> None:
    """For every consistent delivered order, an open window matches the seeded eligibility flag."""
    conn = sqlite3.connect(world["db"])
    try:
        ids = [row[0] for row in conn.execute("SELECT id FROM orders WHERE status = 'delivered'")]
    finally:
        conn.close()
    for order_id in ids:
        order = tools.get_order_details(SUPPORT, order_id)["order"]
        if order["data_issues"]:
            continue
        assert order["refund_eligible"] == (order["days_past_deadline"] == 0), order_id


def test_order_details_flags_seeded_data_defects_instead_of_computing(world: dict) -> None:
    conn = sqlite3.connect(world["db"])
    try:
        cases = dict(
            conn.execute(
                "SELECT entity_id, issue_type FROM data_quality_cases WHERE entity_type = 'order'"
            ).fetchall()
        )
    finally:
        conn.close()
    assert set(cases.values()) == {
        "reversed_chronology",
        "missing_required_date",
        "store_mismatch",
    }
    for order_id, issue_type in cases.items():
        order = tools.get_order_details(SUPPORT, order_id)["order"]
        assert order["data_issues"], issue_type
        if issue_type == "store_mismatch":
            assert order["product_title"] is None
        else:
            assert order["return_deadline"] is None
            assert order["days_left"] is None


def test_order_details_has_no_deadline_before_delivery(world: dict) -> None:
    conn = sqlite3.connect(world["db"])
    try:
        order_id = conn.execute("SELECT id FROM orders WHERE status = 'placed' LIMIT 1").fetchone()[0]
    finally:
        conn.close()
    order = tools.get_order_details(SUPPORT, order_id)["order"]
    assert order["return_deadline"] is None
    assert order["days_left"] is None
    assert order["days_past_deadline"] is None


def test_order_details_enforces_the_access_matrix(world: dict) -> None:
    denied = tools.get_order_details(MERCHANT_STORE_2, 4127)
    assert denied["ok"] is False
    assert denied["error"] == "permission_denied"
    assert "order" not in denied

    missing = tools.get_order_details(SHOPPER_1, 999_999)
    assert missing["error"] == "not_found"


def test_order_details_is_registered_for_every_role() -> None:
    for role, role_tools in TOOLS_BY_ROLE.items():
        assert "get_order_details" in {t.name for t in role_tools}, role
