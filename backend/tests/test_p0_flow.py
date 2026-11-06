import sqlite3
import tempfile
import unittest
from pathlib import Path

import backend.main as main
from backend import manage_scope
from fastapi.testclient import TestClient


def fetch_user(email: str) -> sqlite3.Row:
    conn = main.get_conn()
    try:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.role, u.customer_id, u.tenant_id, u.warehouse_id,
                   c.name AS customer_name
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
        self.assertEqual(payload["tenant_id"], self.customer_user["tenant_id"])
        self.assertEqual(payload["warehouse_id"], self.customer_user["warehouse_id"])

    def test_existing_database_gets_default_tenant_and_warehouse(self):
        legacy_path = Path(self.tempdir.name) / "legacy.db"
        conn = sqlite3.connect(legacy_path)
        try:
            conn.executescript(
                """
                CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY, email TEXT NOT NULL, password_hash TEXT NOT NULL,
                    role TEXT NOT NULL, customer_id INTEGER
                );
                INSERT INTO customers (id, name) VALUES (1, 'Legacy Customer');
                INSERT INTO users (id, email, password_hash, role, customer_id)
                    VALUES (1, 'legacy@example.com', 'unused', 'customer', 1);
                """
            )
            conn.commit()
        finally:
            conn.close()

        main.configure_paths(db_path=legacy_path)
        main.init_db()
        conn = main.get_conn()
        try:
            customer = conn.execute("SELECT * FROM customers WHERE id = 1").fetchone()
            user = conn.execute("SELECT * FROM users WHERE id = 1").fetchone()
            tenant_count = conn.execute("SELECT COUNT(*) AS n FROM tenants").fetchone()["n"]
            warehouse_count = conn.execute("SELECT COUNT(*) AS n FROM warehouses").fetchone()["n"]
        finally:
            conn.close()

        self.assertEqual(tenant_count, 1)
        self.assertEqual(warehouse_count, 1)
        self.assertIsNotNone(customer["tenant_id"])
        self.assertIsNotNone(customer["warehouse_id"])
        self.assertEqual(user["tenant_id"], customer["tenant_id"])
        self.assertEqual(user["warehouse_id"], customer["warehouse_id"])

    def test_migration_fills_missing_warehouse_without_changing_existing_tenant(self):
        conn = main.get_conn()
        try:
            conn.executescript(
                "DROP TRIGGER customers_scope_insert; DROP TRIGGER users_scope_insert;"
            )
            conn.execute("INSERT INTO tenants (name) VALUES ('Partial Tenant')")
            tenant_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO customers (name, tenant_id, warehouse_id) VALUES (?, ?, NULL)",
                ("Partial Customer", tenant_id),
            )
            customer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO users (email, password_hash, role, customer_id, tenant_id, warehouse_id) "
                "VALUES ('partial-staff@example.com', 'unused', 'staff', NULL, ?, NULL)",
                (tenant_id,),
            )
            user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
        finally:
            conn.close()

        main.init_db()
        conn = main.get_conn()
        try:
            customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            warehouse = conn.execute(
                "SELECT tenant_id FROM warehouses WHERE id = ?", (customer["warehouse_id"],)
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(customer["tenant_id"], tenant_id)
        self.assertIsNotNone(customer["warehouse_id"])
        self.assertEqual(user["tenant_id"], tenant_id)
        self.assertIsNotNone(user["warehouse_id"])
        self.assertEqual(warehouse["tenant_id"], tenant_id)

    def test_scope_admin_commands_create_and_assign_valid_memberships(self):
        tenant_id = manage_scope.create_tenant("Managed Company")
        self.assertEqual(manage_scope.create_tenant("Managed Company"), tenant_id)
        warehouse_id = manage_scope.create_warehouse(tenant_id, "Managed Warehouse")
        manage_scope.assign_customer(2, tenant_id, warehouse_id)
        manage_scope.assign_user(
            "customer@example.com", "customer", tenant_id, warehouse_id, customer_id=2
        )
        manage_scope.assign_user("operator@example.com", "operator", tenant_id, warehouse_id)

        customer = fetch_user("customer@example.com")
        operator = fetch_user("operator@example.com")
        self.assertEqual(customer["customer_id"], 2)
        self.assertEqual(customer["tenant_id"], tenant_id)
        self.assertEqual(customer["warehouse_id"], warehouse_id)
        self.assertEqual(operator["tenant_id"], tenant_id)
        self.assertEqual(operator["warehouse_id"], warehouse_id)

        with self.assertRaisesRegex(ValueError, "does not belong"):
            manage_scope.assign_customer(1, tenant_id, self.customer_user["warehouse_id"])

    def test_database_rejects_customer_and_user_cross_tenant_warehouse_links(self):
        conn = main.get_conn()
        try:
            conn.execute("INSERT INTO tenants (name) VALUES ('Trigger Tenant')")
            other_tenant_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO warehouses (tenant_id, name) VALUES (?, 'Trigger Warehouse')",
                (other_tenant_id,),
            )
            other_warehouse_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO customers (name, tenant_id, warehouse_id) VALUES (?, ?, ?)",
                    ("Invalid Customer", self.staff_user["tenant_id"], other_warehouse_id),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE users SET tenant_id = ?, warehouse_id = ? WHERE id = ?",
                    (self.staff_user["tenant_id"], other_warehouse_id, self.staff_user["id"]),
                )
            conn.rollback()
        finally:
            conn.close()

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

    def test_controlled_read_api_requires_auth_and_enforces_resource_scope(self):
        self.assertEqual(self.client.get("/integration/v1/parcels").status_code, 401)
        customer_id, parcel_id, other_staff, _ = self.create_scoped_fixture()
        order = self.client.post(
            "/orders",
            headers=self.auth_header(other_staff),
            json={"customer_id": customer_id, "parcel_ids": [parcel_id]},
        )
        self.assertEqual(order.status_code, 200)
        order_id = order.json()["id"]
        exception = self.client.post(
            f"/orders/{order_id}/exceptions",
            headers=self.auth_header(other_staff),
            json={"type": "DAMAGED", "reason": "foreign exception"},
        )
        self.assertEqual(exception.status_code, 200)
        exception_id = exception.json()["id"]

        self.assertEqual(
            self.client.get(
                f"/integration/v1/parcels/{parcel_id}", headers=self.auth_header(self.staff_user)
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                f"/integration/v1/orders/{order_id}", headers=self.auth_header(self.staff_user)
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                f"/integration/v1/exceptions/{exception_id}", headers=self.auth_header(self.staff_user)
            ).status_code,
            403,
        )

        conn = main.get_conn()
        try:
            conn.execute(
                "INSERT INTO warehouses (tenant_id, name) VALUES (?, 'Read API Other Warehouse')",
                (self.staff_user["tenant_id"],),
            )
            other_warehouse_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO customers (name, tenant_id, warehouse_id) VALUES (?, ?, ?)",
                ("Read API Warehouse Customer", self.staff_user["tenant_id"], other_warehouse_id),
            )
            other_customer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO parcels (customer_id, tracking_number, status) VALUES (?, ?, ?)",
                (other_customer_id, "READ-API-OTHER-WH", main.ParcelStatus.IN_TRANSIT.value),
            )
            same_tenant_parcel = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        operator_scope = self.client.get(
            f"/integration/v1/parcels/{same_tenant_parcel}",
            headers=self.auth_header(self.operator_user),
        )
        self.assertEqual(operator_scope.status_code, 403)

    def test_controlled_read_api_ignores_forged_scope_query_and_filters_sensitive_fields(self):
        parcel = self.client.post(
            "/parcels",
            headers=self.auth_header(self.staff_user),
            json={
                "customer_id": self.customer_user["customer_id"],
                "tracking_number": "SAFE-READ-1",
                "courier_company": "Carrier",
                "item_category": "clothing",
                "item_description": "PRIVATE_DESCRIPTION_SENTINEL",
                "note": "PRIVATE_PARCEL_NOTE_SENTINEL",
            },
        )
        self.assertEqual(parcel.status_code, 200)
        parcel_id = parcel.json()["id"]
        order = self.client.post(
            "/orders",
            headers=self.auth_header(self.staff_user),
            json={"customer_id": self.customer_user["customer_id"], "parcel_ids": [parcel_id]},
        )
        self.assertEqual(order.status_code, 200)
        order_id = order.json()["id"]
        conn = main.get_conn()
        try:
            conn.execute(
                "UPDATE orders SET final_price = ?, forwarding = ? WHERE id = ?",
                (123.45, '{"consignee_name":"PRIVATE_NAME_SENTINEL","consignee_phone":"PRIVATE_PHONE_SENTINEL",'
                 '"consignee_address":"PRIVATE_ADDRESS_SENTINEL"}', order_id),
            )
            conn.commit()
        finally:
            conn.close()
        exception = self.client.post(
            f"/orders/{order_id}/exceptions",
            headers=self.auth_header(self.staff_user),
            json={"type": "DAMAGED", "reason": "PRIVATE_EXCEPTION_REASON_SENTINEL"},
        )
        self.assertEqual(exception.status_code, 200)
        exception_id = exception.json()["id"]

        forged_scope = "?customer_id=2&tenant_id=999999&warehouse_id=999999&user_id=999999&role=staff"
        parcel_list = self.client.get(
            "/integration/v1/parcels" + forged_scope,
            headers=self.auth_header(self.customer_user),
        )
        parcel_detail = self.client.get(
            f"/integration/v1/parcels/{parcel_id}", headers=self.auth_header(self.customer_user)
        )
        order_list = self.client.get(
            "/integration/v1/orders" + forged_scope,
            headers=self.auth_header(self.customer_user),
        )
        order_detail = self.client.get(
            f"/integration/v1/orders/{order_id}", headers=self.auth_header(self.customer_user)
        )
        exception_list = self.client.get(
            "/integration/v1/exceptions", headers=self.auth_header(self.customer_user)
        )
        exception_detail = self.client.get(
            f"/integration/v1/exceptions/{exception_id}", headers=self.auth_header(self.customer_user)
        )
        for response in (parcel_list, parcel_detail, order_list, order_detail, exception_list, exception_detail):
            self.assertEqual(response.status_code, 200)

        own_parcels = self.client.get("/parcels", headers=self.auth_header(self.customer_user))
        own_orders = self.client.get("/orders", headers=self.auth_header(self.customer_user))
        self.assertEqual(own_parcels.status_code, 200)
        self.assertEqual(own_orders.status_code, 200)
        self.assertEqual(
            {item["id"] for item in parcel_list.json()}, {item["id"] for item in own_parcels.json()}
        )
        self.assertIn(parcel_id, {item["id"] for item in parcel_list.json()})
        self.assertEqual(
            {item["id"] for item in order_list.json()}, {item["id"] for item in own_orders.json()}
        )
        self.assertIn(order_id, {item["id"] for item in order_list.json()})
        self.assertEqual([item["id"] for item in exception_list.json()], [exception_id])
        self.assertEqual(
            set(parcel_detail.json()),
            {"id", "tracking_number", "status", "courier_company", "item_category", "arrived_at",
             "pack_requested_at", "packed_at", "shipped_at"},
        )
        self.assertEqual(
            set(order_detail.json()),
            {"id", "order_no", "status", "parcel_ids", "actual_weight", "volumetric_weight", "created_at"},
        )
        self.assertEqual(
            set(exception_detail.json()),
            {"id", "order_id", "type", "status", "created_at", "resolved_at"},
        )
        response_text = str(
            [parcel_list.json(), parcel_detail.json(), order_list.json(), order_detail.json(),
             exception_list.json(), exception_detail.json()]
        )
        for sensitive_value in (
            "PRIVATE_DESCRIPTION_SENTINEL", "PRIVATE_PARCEL_NOTE_SENTINEL", "PRIVATE_NAME_SENTINEL",
            "PRIVATE_PHONE_SENTINEL", "PRIVATE_ADDRESS_SENTINEL", "PRIVATE_EXCEPTION_REASON_SENTINEL",
        ):
            self.assertNotIn(sensitive_value, response_text)

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

    def create_scoped_fixture(self, same_tenant=False):
        conn = main.get_conn()
        try:
            if same_tenant:
                tenant_id = self.staff_user["tenant_id"]
            else:
                conn.execute("INSERT INTO tenants (name) VALUES ('Other Company')")
                tenant_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO warehouses (tenant_id, name) VALUES (?, 'Other Warehouse')",
                (tenant_id,),
            )
            warehouse_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO customers (name, tenant_id, warehouse_id) VALUES (?, ?, ?)",
                ("Other Tenant Customer", tenant_id, warehouse_id),
            )
            customer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO users (email, password_hash, role, customer_id, tenant_id, warehouse_id) "
                "VALUES (?, ?, ?, NULL, ?, ?)",
                ("other-staff@example.com", "unused", "staff", tenant_id, warehouse_id),
            )
            staff_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO users (email, password_hash, role, customer_id, tenant_id, warehouse_id) "
                "VALUES (?, ?, ?, NULL, ?, ?)",
                ("other-operator@example.com", "unused", "operator", tenant_id, warehouse_id),
            )
            operator_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO parcels (customer_id, tracking_number, status) VALUES (?, ?, ?)",
                (customer_id, "OTHER-TENANT-PARCEL", main.ParcelStatus.IN_TRANSIT.value),
            )
            parcel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        return customer_id, parcel_id, fetch_user("other-staff@example.com"), fetch_user("other-operator@example.com")

    def test_staff_is_limited_to_own_tenant(self):
        customer_id, parcel_id, other_staff, _ = self.create_scoped_fixture()
        other_parcel = main.create_parcel(
            main.ParcelCreate(customer_id=customer_id, tracking_number="OTHER-TENANT-NEW"),
            user=other_staff,
        )

        listed_parcels = self.client.get("/parcels", headers=self.auth_header(self.staff_user))
        listed_customers = self.client.get("/customers", headers=self.auth_header(self.staff_user))
        foreign_parcel = self.client.patch(
            f"/parcels/{parcel_id}/status",
            headers=self.auth_header(self.staff_user),
            json={"status": "ARRIVED"},
        )
        foreign_customer_create = self.client.post(
            "/parcels",
            headers=self.auth_header(self.staff_user),
            json={"customer_id": customer_id, "tracking_number": "CROSS-TENANT-CREATE"},
        )

        self.assertEqual(listed_parcels.status_code, 200)
        self.assertNotIn(parcel_id, [item["id"] for item in listed_parcels.json()])
        self.assertEqual(listed_customers.status_code, 200)
        self.assertNotIn(customer_id, [item["id"] for item in listed_customers.json()])
        self.assertEqual(foreign_parcel.status_code, 403)
        self.assertEqual(foreign_customer_create.status_code, 403)
        self.assertGreater(other_parcel.id, 0)

    def test_operator_is_limited_to_assigned_warehouse(self):
        customer_id, parcel_id, _, other_operator = self.create_scoped_fixture(same_tenant=True)
        other_parcel = self.client.get(
            "/parcels", headers=self.auth_header(other_operator)
        )
        own_parcel = self.client.get(
            "/parcels", headers=self.auth_header(self.operator_user)
        )
        foreign_parcel_update = self.client.patch(
            f"/parcels/{parcel_id}/status",
            headers=self.auth_header(self.operator_user),
            json={"status": "ARRIVED"},
        )
        foreign_order_create = self.client.post(
            "/orders",
            headers=self.auth_header(self.operator_user),
            json={"customer_id": customer_id, "parcel_ids": [parcel_id]},
        )

        self.assertEqual(other_parcel.status_code, 200)
        self.assertIn(parcel_id, [item["id"] for item in other_parcel.json()])
        self.assertEqual(own_parcel.status_code, 200)
        self.assertNotIn(parcel_id, [item["id"] for item in own_parcel.json()])
        self.assertEqual(foreign_parcel_update.status_code, 403)
        self.assertEqual(foreign_order_create.status_code, 403)

    def test_staff_cannot_access_foreign_tenant_orders_tasks_exceptions_or_billing(self):
        customer_id, parcel_id, other_staff, _ = self.create_scoped_fixture()
        order_response = self.client.post(
            "/orders",
            headers=self.auth_header(other_staff),
            json={"customer_id": customer_id, "parcel_ids": [parcel_id]},
        )
        order_id = order_response.json()["id"]
        exception_response = self.client.post(
            f"/orders/{order_id}/exceptions",
            headers=self.auth_header(other_staff),
            json={"type": "DAMAGED", "reason": "test"},
        )
        exception_id = exception_response.json()["id"]
        conn = main.get_conn()
        try:
            task_id = conn.execute("SELECT id FROM tasks WHERE order_id = ?", (order_id,)).fetchone()["id"]
            conn.execute(
                "UPDATE orders SET status = ?, actual_weight = 1 WHERE id = ?",
                (main.OrderStatus.COMPLETED.value, order_id),
            )
            conn.commit()
        finally:
            conn.close()

        checks = {
            "order detail": self.client.get(f"/orders/{order_id}", headers=self.auth_header(self.staff_user)),
            "order update": self.client.patch(
                f"/orders/{order_id}/order_no",
                headers=self.auth_header(self.staff_user), json={"order_no": "DENIED"},
            ),
            "ship": self.client.patch(f"/orders/{order_id}/ship", headers=self.auth_header(self.staff_user)),
            "task list": self.client.get(f"/tasks?order_id={order_id}", headers=self.auth_header(self.staff_user)),
            "exception list": self.client.get(
                f"/orders/{order_id}/exceptions", headers=self.auth_header(self.staff_user)
            ),
            "exception create": self.client.post(
                f"/orders/{order_id}/exceptions",
                headers=self.auth_header(self.staff_user),
                json={"type": "DAMAGED", "reason": "denied"},
            ),
            "exception resolve": self.client.patch(
                f"/exceptions/{exception_id}/resolve",
                headers=self.auth_header(self.staff_user),
                json={"resolution_note": "denied"},
            ),
            "audit list": self.client.get(
                f"/orders/{order_id}/audits", headers=self.auth_header(self.staff_user)
            ),
            "price": self.client.patch(
                f"/orders/{order_id}/price",
                headers=self.auth_header(self.staff_user),
                json={"rate_per_kg": 1},
            ),
            "customer detail": self.client.get(
                f"/customers/{customer_id}", headers=self.auth_header(self.staff_user)
            ),
        }
        self.assertEqual(order_response.status_code, 200)
        self.assertEqual(exception_response.status_code, 200)
        self.assertGreater(task_id, 0)
        self.assertTrue(
            all(response.status_code == 403 for name, response in checks.items() if name != "task list"),
            {name: response.status_code for name, response in checks.items()},
        )
        self.assertEqual(checks["task list"].status_code, 200)
        self.assertNotIn(task_id, [item["id"] for item in checks["task list"].json()])

    def test_operator_cannot_read_or_mutate_foreign_warehouse_order_or_task(self):
        customer_id, parcel_id, other_staff, _ = self.create_scoped_fixture(same_tenant=True)
        order = self.client.post(
            "/orders",
            headers=self.auth_header(other_staff),
            json={"customer_id": customer_id, "parcel_ids": [parcel_id]},
        )
        order_id = order.json()["id"]
        conn = main.get_conn()
        try:
            task_id = conn.execute("SELECT id FROM tasks WHERE order_id = ?", (order_id,)).fetchone()["id"]
            conn.commit()
        finally:
            conn.close()

        self.assertEqual(order.status_code, 200)
        self.assertEqual(
            self.client.get(f"/orders/{order_id}", headers=self.auth_header(self.operator_user)).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(
                f"/tasks/{task_id}/start", headers=self.auth_header(self.operator_user)
            ).status_code,
            403,
        )
        tasks = self.client.get("/tasks", headers=self.auth_header(self.operator_user))
        self.assertEqual(tasks.status_code, 200)
        self.assertNotIn(task_id, [item["id"] for item in tasks.json()])

    def test_notifications_are_scoped_for_read_write_and_clear(self):
        customer_id, _, other_staff, _ = self.create_scoped_fixture()
        self.assertEqual(
            self.client.post(
                "/notify/ready_to_ship",
                headers=self.auth_header(other_staff),
                json={"customer_id": customer_id, "message": "foreign"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                f"/notifications?customer_id={customer_id}",
                headers=self.auth_header(self.staff_user),
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/notify/shipped",
                headers=self.auth_header(self.staff_user),
                json={"customer_id": customer_id, "message": "cross tenant"},
            ).status_code,
            403,
        )

        conn = main.get_conn()
        try:
            foreign_before = conn.execute(
                "SELECT COUNT(*) AS n FROM notifications WHERE customer_id = ?", (customer_id,)
            ).fetchone()["n"]
        finally:
            conn.close()
        self.assertEqual(
            self.client.delete("/notifications", headers=self.auth_header(self.staff_user)).status_code,
            200,
        )
        conn = main.get_conn()
        try:
            foreign_after = conn.execute(
                "SELECT COUNT(*) AS n FROM notifications WHERE customer_id = ?", (customer_id,)
            ).fetchone()["n"]
        finally:
            conn.close()
        self.assertEqual(foreign_before, 1)
        self.assertEqual(foreign_after, 1)


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
