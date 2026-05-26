import sqlite3
import tempfile
import unittest
from pathlib import Path

import backend.main as main


def fetch_user(email: str) -> sqlite3.Row:
    conn = main.get_conn()
    try:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.role, u.customer_id, c.name AS customer_name
            FROM users u
            LEFT JOIN customers c ON c.id = u.customer_id
            WHERE u.email = ?
            """,
            (email,),
        ).fetchone()
        assert row is not None
        return row
    finally:
        conn.close()


class P0FlowTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        main.DB_PATH = Path(self.tempdir.name) / "test.db"
        main.init_db()
        main.seed()
        self.customer_user = fetch_user("customer@example.com")
        self.staff_user = fetch_user("staff@example.com")
        self.operator_user = fetch_user("operator@example.com")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_login_and_token_roundtrip(self):
        res = main.login(main.LoginReq(email="customer@example.com", password="demo123"))
        self.assertEqual(res.role, main.UserRole.customer)
        payload = main.parse_token(res.token)
        self.assertEqual(payload["role"], "customer")
        self.assertEqual(payload["customer_id"], 1)

    def test_ready_to_pack_to_ship_flow(self):
        parcel = main.patch_parcel_status(
            1,
            main.ParcelStatusPatch(status=main.ParcelStatus.ARRIVED),
            user=self.staff_user,
        )
        self.assertEqual(parcel.status, main.ParcelStatus.ARRIVED)

        notify = main.notify_ready_to_pack(
            main.ReadyNotify(customer_id=1),
            user=self.customer_user,
        )
        self.assertTrue(notify["ok"])
        order_id = notify["order_id"]
        order = main.get_order(order_id, user=self.customer_user)
        self.assertEqual(order.status, main.OrderStatus.READY_TO_PACK)

        task = main.list_tasks(order_id=order_id, user=self.operator_user)[0]
        main.start_task(task.id, user=self.operator_user)
        order = main.get_order(order_id, user=self.staff_user)
        self.assertEqual(order.status, main.OrderStatus.PACKING)

        main.complete_task(
            task.id,
            main.TaskComplete(actual_weight=1.25),
            user=self.operator_user,
        )
        order = main.get_order(order_id, user=self.staff_user)
        self.assertEqual(order.status, main.OrderStatus.READY_TO_SHIP)

        main.ship_order(order_id, user=self.staff_user)
        order = main.get_order(order_id, user=self.staff_user)
        self.assertEqual(order.status, main.OrderStatus.COMPLETED)

    def test_invalid_task_and_ship_transitions(self):
        main.patch_parcel_status(
            1,
            main.ParcelStatusPatch(status=main.ParcelStatus.ARRIVED),
            user=self.staff_user,
        )
        order_id = main.notify_ready_to_pack(
            main.ReadyNotify(customer_id=1),
            user=self.customer_user,
        )["order_id"]
        task = main.list_tasks(order_id=order_id, user=self.operator_user)[0]

        with self.assertRaises(main.HTTPException) as ctx:
            main.complete_task(task.id, main.TaskComplete(actual_weight=1.0), user=self.operator_user)
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(main.HTTPException) as ctx:
            main.ship_order(order_id, user=self.staff_user)
        self.assertEqual(ctx.exception.status_code, 400)

        main.start_task(task.id, user=self.operator_user)
        with self.assertRaises(main.HTTPException) as ctx:
            main.start_task(task.id, user=self.operator_user)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_customer_scope_is_enforced(self):
        with self.assertRaises(main.HTTPException) as ctx:
            main.require_permission("customer:view")(self.customer_user)
        self.assertEqual(ctx.exception.status_code, 403)

        rows = main.list_orders(user=self.customer_user)
        for row in rows:
            self.assertEqual(row.customer_id, 1)

        with self.assertRaises(main.HTTPException) as ctx:
            main.create_parcel(
                main.ParcelCreate(customer_id=2, tracking_number="SCOPE-FAIL"),
                user=self.customer_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
