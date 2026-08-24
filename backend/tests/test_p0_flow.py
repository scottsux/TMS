import sqlite3
import tempfile
import unittest
from pathlib import Path

import backend.main as main
from fastapi.testclient import TestClient


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


class PermissionApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        main.DB_PATH = Path(self.tempdir.name) / "test.db"
        main.init_db()
        main.seed()
        self.client = TestClient(main.app)
        self.customer_user = fetch_user("customer@example.com")
        self.staff_user = fetch_user("staff@example.com")
        self.operator_user = fetch_user("operator@example.com")

    def tearDown(self):
        self.client.close()
        self.tempdir.cleanup()

    @staticmethod
    def auth_header(user: sqlite3.Row) -> dict[str, str]:
        return {"Authorization": f"Bearer {main.create_token(user)}"}

    def test_missing_token_is_rejected(self):
        self.assertEqual(self.client.get("/orders").status_code, 401)

    def test_customer_can_view_orders_but_cannot_view_tasks(self):
        orders = self.client.get("/orders", headers=self.auth_header(self.customer_user))
        tasks = self.client.get("/tasks", headers=self.auth_header(self.customer_user))
        self.assertEqual(orders.status_code, 200)
        self.assertEqual(tasks.status_code, 403)

    def test_staff_can_view_tasks_but_cannot_start_them(self):
        tasks = self.client.get("/tasks", headers=self.auth_header(self.staff_user))
        start = self.client.patch("/tasks/1/start", headers=self.auth_header(self.staff_user))
        self.assertEqual(tasks.status_code, 200)
        self.assertEqual(start.status_code, 403)

    def test_operator_can_view_tasks_but_cannot_ship_orders(self):
        tasks = self.client.get("/tasks", headers=self.auth_header(self.operator_user))
        ship = self.client.patch("/orders/1/ship", headers=self.auth_header(self.operator_user))
        self.assertEqual(tasks.status_code, 200)
        self.assertEqual(ship.status_code, 403)


class BusinessRuleApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_upload_dir = main.UPLOAD_DIR
        main.DB_PATH = Path(self.tempdir.name) / "test.db"
        main.UPLOAD_DIR = Path(self.tempdir.name) / "uploads"
        main.init_db()
        main.seed()
        self.client = TestClient(main.app)
        self.customer_user = fetch_user("customer@example.com")
        self.staff_user = fetch_user("staff@example.com")
        self.operator_user = fetch_user("operator@example.com")

    def tearDown(self):
        self.client.close()
        main.UPLOAD_DIR = self.original_upload_dir
        self.tempdir.cleanup()

    @staticmethod
    def auth_header(user: sqlite3.Row) -> dict[str, str]:
        return {"Authorization": f"Bearer {main.create_token(user)}"}

    def create_order(self, customer_id: int = 1, parcel_ids: list[int] | None = None) -> int:
        response = self.client.post(
            "/orders",
            headers=self.auth_header(self.staff_user),
            json={"customer_id": customer_id, "parcel_ids": parcel_ids or [1]},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    def test_price_formula_rounds_and_persists(self):
        order_id = self.create_order()

        response = self.client.patch(
            f"/orders/{order_id}/price",
            headers=self.auth_header(self.staff_user),
            json={"actual_weight": 1.25, "rate_per_kg": 3.2, "extra_fee": 0.05},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["final_price"], 4.05)
        order = self.client.get(f"/orders/{order_id}", headers=self.auth_header(self.staff_user))
        self.assertEqual(order.status_code, 200)
        self.assertEqual(order.json()["actual_weight"], 1.25)
        self.assertEqual(order.json()["final_price"], 4.05)

    def test_price_rejects_negative_values(self):
        order_id = self.create_order()
        valid = {"actual_weight": 1, "rate_per_kg": 2, "extra_fee": 0}
        invalid_values = (
            {**valid, "actual_weight": -0.01},
            {**valid, "rate_per_kg": -0.01},
            {**valid, "extra_fee": -0.01},
        )

        for body in invalid_values:
            with self.subTest(body=body):
                response = self.client.patch(
                    f"/orders/{order_id}/price",
                    headers=self.auth_header(self.staff_user),
                    json=body,
                )
                self.assertEqual(response.status_code, 422)

    def test_manual_price_override_requires_staff_and_rejects_negative_value(self):
        order_id = self.create_order()
        staff_response = self.client.patch(
            f"/orders/{order_id}/override_price",
            headers=self.auth_header(self.staff_user),
            json={"final_price": 42.5},
        )
        customer_response = self.client.patch(
            f"/orders/{order_id}/override_price",
            headers=self.auth_header(self.customer_user),
            json={"final_price": 42.5},
        )
        negative_response = self.client.patch(
            f"/orders/{order_id}/override_price",
            headers=self.auth_header(self.staff_user),
            json={"final_price": -0.01},
        )

        self.assertEqual(staff_response.status_code, 200)
        self.assertEqual(staff_response.json()["final_price"], 42.5)
        self.assertEqual(customer_response.status_code, 403)
        self.assertEqual(negative_response.status_code, 422)

    def test_actual_and_volumetric_weight_persist_and_require_staff(self):
        order_id = self.create_order()
        actual_response = self.client.patch(
            f"/orders/{order_id}/actual_weight",
            headers=self.auth_header(self.staff_user),
            json={"actual_weight": 2.75},
        )
        volumetric_response = self.client.patch(
            f"/orders/{order_id}/volumetric",
            headers=self.auth_header(self.staff_user),
            json={"volumetric_weight": 3.4},
        )
        customer_response = self.client.patch(
            f"/orders/{order_id}/actual_weight",
            headers=self.auth_header(self.customer_user),
            json={"actual_weight": 1},
        )
        order = self.client.get(f"/orders/{order_id}", headers=self.auth_header(self.staff_user))

        self.assertEqual(actual_response.status_code, 200)
        self.assertEqual(volumetric_response.status_code, 200)
        self.assertEqual(customer_response.status_code, 403)
        self.assertEqual(order.status_code, 200)
        self.assertEqual(order.json()["actual_weight"], 2.75)
        self.assertEqual(order.json()["volumetric_weight"], 3.4)

    def test_file_upload_accepts_images_and_rejects_boundary_violations(self):
        headers = self.auth_header(self.customer_user)
        valid = self.client.post(
            "/parcels/1/files",
            headers=headers,
            files=[("files", ("package.png", b"image-data", "image/png"))],
        )
        too_many = self.client.post(
            "/parcels/1/files",
            headers=headers,
            files=[("files", (f"package-{i}.png", b"x", "image/png")) for i in range(6)],
        )
        unsupported_type = self.client.post(
            "/parcels/1/files",
            headers=headers,
            files=[("files", ("package.gif", b"image-data", "image/gif"))],
        )
        too_large = self.client.post(
            "/parcels/1/files",
            headers=headers,
            files=[("files", ("package.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg"))],
        )
        operator = self.client.post(
            "/parcels/1/files",
            headers=self.auth_header(self.operator_user),
            files=[("files", ("package.png", b"image-data", "image/png"))],
        )

        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()["saved"], [{"filename": "package.png", "size": 10}])
        self.assertTrue((main.UPLOAD_DIR / "1" / "package.png").is_file())
        self.assertEqual(too_many.status_code, 400)
        self.assertEqual(unsupported_type.status_code, 400)
        self.assertEqual(too_large.status_code, 400)
        self.assertEqual(operator.status_code, 403)

    def test_customer_cannot_access_another_customers_order_or_parcel(self):
        other_parcel = main.create_parcel(
            main.ParcelCreate(customer_id=2, tracking_number="OTHER-CUSTOMER-PARCEL"),
            user=self.staff_user,
        )
        other_order_id = self.create_order(customer_id=2, parcel_ids=[other_parcel.id])

        orders = self.client.get("/orders", headers=self.auth_header(self.customer_user))
        parcel = self.client.get("/parcels", headers=self.auth_header(self.customer_user))
        other_order = self.client.get(
            f"/orders/{other_order_id}", headers=self.auth_header(self.customer_user)
        )

        self.assertEqual(orders.status_code, 200)
        self.assertNotIn(other_order_id, [item["id"] for item in orders.json()])
        self.assertEqual(parcel.status_code, 200)
        self.assertNotIn(other_parcel.id, [item["id"] for item in parcel.json()])
        self.assertEqual(other_order.status_code, 403)

    def test_parcel_status_transition_rejects_illegal_jump_and_unauthorized_role(self):
        illegal = self.client.patch(
            "/parcels/1/status",
            headers=self.auth_header(self.staff_user),
            json={"status": "PACKED"},
        )
        unauthorized = self.client.patch(
            "/parcels/1/status",
            headers=self.auth_header(self.customer_user),
            json={"status": "ARRIVED"},
        )

        self.assertEqual(illegal.status_code, 400)
        self.assertEqual(unauthorized.status_code, 403)


if __name__ == "__main__":
    unittest.main()
