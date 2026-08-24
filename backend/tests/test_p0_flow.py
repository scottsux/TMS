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
        main.configure_paths(db_path=Path(self.tempdir.name) / "test.db")
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
        main.configure_paths(db_path=Path(self.tempdir.name) / "test.db")
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
        self.original_upload_dir = main.config.UPLOAD_DIR
        main.configure_paths(
            db_path=Path(self.tempdir.name) / "test.db",
            upload_dir=Path(self.tempdir.name) / "uploads",
        )
        main.init_db()
        main.seed()
        self.client = TestClient(main.app)
        self.customer_user = fetch_user("customer@example.com")
        self.staff_user = fetch_user("staff@example.com")
        self.operator_user = fetch_user("operator@example.com")

    def tearDown(self):
        self.client.close()
        main.configure_paths(upload_dir=self.original_upload_dir)
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

    def set_order_state(self, order_id: int, status: main.OrderStatus, actual_weight: float = 0):
        conn = main.get_conn()
        try:
            conn.execute(
                "UPDATE orders SET status = ?, actual_weight = ? WHERE id = ?",
                (status.value, actual_weight, order_id),
            )
            conn.commit()
        finally:
            conn.close()

    def test_price_formula_rounds_and_persists(self):
        order_id = self.create_order()
        self.set_order_state(order_id, main.OrderStatus.COMPLETED, actual_weight=1.25)

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
        self.set_order_state(order_id, main.OrderStatus.COMPLETED)
        staff_response = self.client.patch(
            f"/orders/{order_id}/override_price",
            headers=self.auth_header(self.staff_user),
            json={"final_price": 42.5, "reason": "customer service adjustment"},
        )
        customer_response = self.client.patch(
            f"/orders/{order_id}/override_price",
            headers=self.auth_header(self.customer_user),
            json={"final_price": 42.5, "reason": "customer service adjustment"},
        )
        negative_response = self.client.patch(
            f"/orders/{order_id}/override_price",
            headers=self.auth_header(self.staff_user),
            json={"final_price": -0.01, "reason": "invalid negative price"},
        )

        self.assertEqual(staff_response.status_code, 200)
        self.assertEqual(staff_response.json()["final_price"], 42.5)
        self.assertEqual(customer_response.status_code, 403)
        self.assertEqual(negative_response.status_code, 422)

    def test_actual_and_volumetric_weight_persist_and_require_staff(self):
        order_id = self.create_order()
        self.set_order_state(order_id, main.OrderStatus.PACKING)
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
        self.assertTrue((main.config.UPLOAD_DIR / "1" / "package.png").is_file())
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

    def test_legacy_parcel_ids_migrate_to_relation_table_and_remain_in_api_response(self):
        conn = main.get_conn()
        try:
            cursor = conn.execute(
                """
                INSERT INTO orders (
                    customer_id, parcel_ids, status, actual_weight, final_price,
                    volumetric_weight, forwarding, created_at, order_no
                ) VALUES (?, ?, ?, 0, NULL, 0, NULL, ?, NULL)
                """,
                (1, "[1]", main.OrderStatus.DRAFT.value, main.utc_now_iso()),
            )
            order_id = cursor.lastrowid
            conn.commit()
            main.migrate_order_parcels(conn)
            conn.commit()
            relation_ids = main.get_order_parcel_ids(conn, order_id)
            legacy_value = conn.execute(
                "SELECT parcel_ids FROM orders WHERE id = ?", (order_id,)
            ).fetchone()["parcel_ids"]
        finally:
            conn.close()

        response = self.client.get(f"/orders/{order_id}", headers=self.auth_header(self.staff_user))
        self.assertEqual(relation_ids, [1])
        self.assertEqual(legacy_value, "[1]")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["parcel_ids"], [1])

    def test_order_parcel_add_remove_release_and_reassignment(self):
        order_id = self.create_order(parcel_ids=[1])
        add = self.client.patch(
            f"/orders/{order_id}/parcels",
            headers=self.auth_header(self.staff_user),
            json={"add": [2]},
        )
        remove = self.client.patch(
            f"/orders/{order_id}/parcels",
            headers=self.auth_header(self.staff_user),
            json={"remove": [1]},
        )
        reassigned_order_id = self.create_order(parcel_ids=[1])

        self.assertEqual(add.status_code, 200)
        self.assertEqual(add.json()["parcel_ids"], [1, 2])
        self.assertEqual(remove.status_code, 200)
        self.assertEqual(remove.json()["parcel_ids"], [2])
        conn = main.get_conn()
        try:
            self.assertEqual(main.get_order_parcel_ids(conn, order_id), [2])
            self.assertEqual(main.get_order_parcel_ids(conn, reassigned_order_id), [1])
            self.assertEqual(
                conn.execute("SELECT parcel_ids FROM orders WHERE id = ?", (order_id,)).fetchone()[
                    "parcel_ids"
                ],
                "[2]",
            )
        finally:
            conn.close()

    def test_order_parcel_relationship_rejects_duplicate_cross_customer_and_occupied_parcels(self):
        duplicate = self.client.post(
            "/orders",
            headers=self.auth_header(self.staff_user),
            json={"customer_id": 1, "parcel_ids": [1, 1]},
        )
        order_id = self.create_order(parcel_ids=[1])
        occupied = self.client.post(
            "/orders",
            headers=self.auth_header(self.staff_user),
            json={"customer_id": 1, "parcel_ids": [1]},
        )
        cross_customer_parcel = main.create_parcel(
            main.ParcelCreate(customer_id=2, tracking_number="CROSS-CUSTOMER-PARCEL"),
            user=self.staff_user,
        )
        cross_customer = self.client.patch(
            f"/orders/{order_id}/parcels",
            headers=self.auth_header(self.staff_user),
            json={"add": [cross_customer_parcel.id]},
        )

        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(occupied.status_code, 400)
        self.assertEqual(cross_customer.status_code, 400)

    def test_relation_table_enforces_one_order_per_parcel(self):
        first_order_id = self.create_order(parcel_ids=[1])
        second_order_id = self.create_order(parcel_ids=[2])
        conn = main.get_conn()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO order_parcels (order_id, parcel_id, created_at) VALUES (?, ?, ?)",
                    (second_order_id, 1, main.utc_now_iso()),
                )
            self.assertEqual(main.get_order_parcel_ids(conn, first_order_id), [1])
        finally:
            conn.close()

    def test_open_exception_blocks_shipping_and_pricing_until_staff_resolves_it(self):
        order_id = self.create_order()
        self.set_order_state(order_id, main.OrderStatus.READY_TO_SHIP, actual_weight=2)
        created = self.client.post(
            f"/orders/{order_id}/exceptions",
            headers=self.auth_header(self.customer_user),
            json={"type": "PRICE_DISPUTE", "reason": "price needs review"},
        )
        exception_id = created.json()["id"]
        ship = self.client.patch(f"/orders/{order_id}/ship", headers=self.auth_header(self.staff_user))
        self.set_order_state(order_id, main.OrderStatus.COMPLETED, actual_weight=2)
        price = self.client.patch(
            f"/orders/{order_id}/price",
            headers=self.auth_header(self.staff_user),
            json={"rate_per_kg": 10, "extra_fee": 0},
        )
        resolved = self.client.patch(
            f"/exceptions/{exception_id}/resolve",
            headers=self.auth_header(self.staff_user),
            json={"resolution_note": "pricing confirmed with customer"},
        )
        priced_after_resolution = self.client.patch(
            f"/orders/{order_id}/price",
            headers=self.auth_header(self.staff_user),
            json={"rate_per_kg": 10, "extra_fee": 0},
        )

        self.assertEqual(created.status_code, 200)
        self.assertEqual(ship.status_code, 400)
        self.assertEqual(price.status_code, 400)
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(priced_after_resolution.status_code, 200)

    def test_exception_type_permissions_and_resolution_audit(self):
        order_id = self.create_order()
        customer_forbidden = self.client.post(
            f"/orders/{order_id}/exceptions",
            headers=self.auth_header(self.customer_user),
            json={"type": "DAMAGED", "reason": "customer cannot report this type"},
        )
        operator_created = self.client.post(
            f"/orders/{order_id}/exceptions",
            headers=self.auth_header(self.operator_user),
            json={"type": "DAMAGED", "reason": "outer box damaged"},
        )
        exception_id = operator_created.json()["id"]
        operator_resolve = self.client.patch(
            f"/exceptions/{exception_id}/resolve",
            headers=self.auth_header(self.operator_user),
            json={"resolution_note": "operator cannot resolve"},
        )
        staff_resolve = self.client.patch(
            f"/exceptions/{exception_id}/resolve",
            headers=self.auth_header(self.staff_user),
            json={"resolution_note": "damage reviewed and repacked"},
        )
        audits = self.client.get(f"/orders/{order_id}/audits", headers=self.auth_header(self.staff_user))

        self.assertEqual(customer_forbidden.status_code, 403)
        self.assertEqual(operator_created.status_code, 200)
        self.assertEqual(operator_resolve.status_code, 403)
        self.assertEqual(staff_resolve.status_code, 200)
        self.assertEqual([item["action"] for item in audits.json()][:2], ["exception:resolve", "exception:create"])

    def test_weight_and_price_rules_create_server_audits(self):
        order_id = self.create_order()
        self.set_order_state(order_id, main.OrderStatus.PACKING)
        operator_actual = self.client.patch(
            f"/orders/{order_id}/actual_weight",
            headers=self.auth_header(self.operator_user),
            json={"actual_weight": 1.5},
        )
        operator_volume = self.client.patch(
            f"/orders/{order_id}/volumetric",
            headers=self.auth_header(self.operator_user),
            json={"volumetric_weight": 2.1},
        )
        self.set_order_state(order_id, main.OrderStatus.READY_TO_SHIP, actual_weight=1.5)
        staff_actual = self.client.patch(
            f"/orders/{order_id}/actual_weight",
            headers=self.auth_header(self.staff_user),
            json={"actual_weight": 1.6},
        )
        operator_late = self.client.patch(
            f"/orders/{order_id}/actual_weight",
            headers=self.auth_header(self.operator_user),
            json={"actual_weight": 1.7},
        )
        self.set_order_state(order_id, main.OrderStatus.COMPLETED, actual_weight=1.6)
        completed_weight = self.client.patch(
            f"/orders/{order_id}/actual_weight",
            headers=self.auth_header(self.staff_user),
            json={"actual_weight": 1.7},
        )
        price = self.client.patch(
            f"/orders/{order_id}/price",
            headers=self.auth_header(self.staff_user),
            json={"rate_per_kg": 10, "extra_fee": 1, "reason": "standard completed-order rate"},
        )
        override = self.client.patch(
            f"/orders/{order_id}/override_price",
            headers=self.auth_header(self.staff_user),
            json={"final_price": 18, "reason": "approved goodwill adjustment"},
        )
        audits = self.client.get(f"/orders/{order_id}/audits", headers=self.auth_header(self.staff_user))

        self.assertEqual(operator_actual.status_code, 200)
        self.assertEqual(operator_volume.status_code, 200)
        self.assertEqual(staff_actual.status_code, 200)
        self.assertEqual(operator_late.status_code, 400)
        self.assertEqual(completed_weight.status_code, 400)
        self.assertEqual(price.status_code, 200)
        self.assertEqual(override.status_code, 200)
        actions = [item["action"] for item in audits.json()]
        self.assertIn("weight:actual_update", actions)
        self.assertIn("weight:volumetric_update", actions)
        self.assertIn("price:calculate", actions)
        self.assertIn("price:override", actions)

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
