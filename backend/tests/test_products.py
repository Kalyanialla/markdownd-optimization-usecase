"""
Unit tests for Product Catalog endpoints.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_headers(client: TestClient):
    email = "catalog_analyst@retail.com"
    password = "Password123!"
    signup_res = client.post("/api/v1/auth/signup", json={
        "email": email,
        "password": password,
        "full_name": "Catalog Analyst"
    })
    if signup_res.status_code == 201:
        token = signup_res.json()["access_token"]
    else:
        login_res = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password
        })
        token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_products_unauthenticated(client: TestClient):
    """Attempting to list products without authentication returns 401."""
    res = client.get("/api/v1/products")
    assert res.status_code == 401


def test_list_products_authenticated(client: TestClient, auth_headers: dict):
    """Authenticated user can list paginated products and receive categories/brands."""
    res = client.get("/api/v1/products", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] > 0
    assert len(data["items"]) <= 20
    assert "categories" in data
    assert "brands" in data

    first = data["items"][0]
    assert "sku_id" in first
    assert "regular_price" in first
    assert "unit_cost" in first


def test_filter_products_by_category(client: TestClient, auth_headers: dict):
    """Filtering by category returns only products belonging to that category."""
    res = client.get("/api/v1/products?category=TShirt", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    for item in data["items"]:
        assert item["category"].lower() == "tshirt"


def test_get_product_by_sku_success(client: TestClient, auth_headers: dict):
    """Getting existing SKU details returns 200 with full specification."""
    res = client.get("/api/v1/products/SKU-0001", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["sku_id"] == "SKU-0001"
    assert data["product_name"] == "Aurelia V-Neck T-Shirt - Beige (XS)"
    assert data["regular_price"] == 1099.0


def test_get_product_by_sku_not_found(client: TestClient, auth_headers: dict):
    """Requesting non-existent SKU returns 404."""
    res = client.get("/api/v1/products/NON-EXISTENT-SKU", headers=auth_headers)
    assert res.status_code == 404


def test_get_price_history_for_sku(client: TestClient, auth_headers: dict):
    """Requesting price history for a SKU returns chronological events."""
    res = client.get("/api/v1/products/SKU-0001/price-history", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_inventory_loaded_from_latest_valid_snapshot_not_summed():
    """
    Regression Test: Confirm current inventory is selected from the latest valid snapshot
    for each SKU and store, rather than summing historical snapshots across time.
    """
    import pandas as pd
    from backend.app.core.config import settings
    from backend.app.services.product_service import ProductService

    # ProductService should return latest snapshot, NOT historical sum
    # SKU-0004 had historical sum 18,240 across 546 daily snapshots; latest snapshot at STORE-05 is 2
    sku_0004_store05 = ProductService.get_product_by_sku("SKU-0004", store_id="STORE-05")
    assert sku_0004_store05.current_stock == 2
    assert sku_0004_store05.current_stock < 1000

    # SKU-0101 had historical sum 50,851; latest snapshot at STORE-01 is 11, total chain is 18
    sku_0101_store01 = ProductService.get_product_by_sku("SKU-0101", store_id="STORE-01")
    assert sku_0101_store01.current_stock == 11

    sku_0101_chain = ProductService.get_product_by_sku("SKU-0101")
    assert sku_0101_chain.current_stock == 18
    assert sku_0101_chain.current_stock < 50000


def test_process_inventory_snapshots_handles_duplicates_and_invalids():
    """
    Regression Test: Verify process_inventory_snapshots handles duplicate snapshots
    on the same date/store (retains latest), invalid dates/units, and incomplete flags.
    """
    import pandas as pd
    from backend.app.services.product_service import process_inventory_snapshots

    synthetic_snapshots = pd.DataFrame([
        # Valid historical baseline for SKU-A at STORE-01
        {"snapshot_id": "SNP-001", "snapshot_date": "2025-01-01", "sku_id": "SKU-A", "store_id": "STORE-01", "available_units": 50, "inventory_data_complete_flag": 1},
        # Newer snapshot for SKU-A at STORE-01
        {"snapshot_id": "SNP-002", "snapshot_date": "2025-06-30", "sku_id": "SKU-A", "store_id": "STORE-01", "available_units": 15, "inventory_data_complete_flag": 1},
        # Duplicate snapshot on the SAME date 2025-06-30 with later snapshot_id SNP-003 (e.g. intraday revision to 18 units)
        {"snapshot_id": "SNP-003", "snapshot_date": "2025-06-30", "sku_id": "SKU-A", "store_id": "STORE-01", "available_units": 18, "inventory_data_complete_flag": 1},
        # Incomplete data flag (should be ignored)
        {"snapshot_id": "SNP-004", "snapshot_date": "2025-07-01", "sku_id": "SKU-A", "store_id": "STORE-01", "available_units": 99, "inventory_data_complete_flag": 0},
        # Corrupt / unparseable date (should be ignored)
        {"snapshot_id": "SNP-005", "snapshot_date": "INVALID_DATE", "sku_id": "SKU-A", "store_id": "STORE-01", "available_units": 99, "inventory_data_complete_flag": 1},
        # Negative inventory (should be ignored)
        {"snapshot_id": "SNP-006", "snapshot_date": "2025-07-02", "sku_id": "SKU-A", "store_id": "STORE-01", "available_units": -5, "inventory_data_complete_flag": 1},
        # SKU-B in STORE-02
        {"snapshot_id": "SNP-007", "snapshot_date": "2025-06-30", "sku_id": "SKU-B", "store_id": "STORE-02", "available_units": 42, "inventory_data_complete_flag": 1},
    ])

    sku_store_map, date_map, sku_totals, primary_map, stores = process_inventory_snapshots(synthetic_snapshots)

    # SKU-A in STORE-01 must resolve to 18 (the latest valid deduplicated snapshot SNP-003, NOT sum 50+15+18=83, NOT corrupt SNP-004/005/006)
    assert sku_store_map[("SKU-A", "STORE-01")] == 18
    assert date_map[("SKU-A", "STORE-01")] == "2025-06-30"

    # SKU-B in STORE-02 resolves to 42
    assert sku_store_map[("SKU-B", "STORE-02")] == 42

    # Missing snapshot test: SKU-A in STORE-02 has no snapshot -> .get returns 0
    assert sku_store_map.get(("SKU-A", "STORE-02"), 0) == 0

    # Chain totals
    assert sku_totals["SKU-A"] == 18
    assert sku_totals["SKU-B"] == 42


def test_filter_products_by_store_api(client: TestClient, auth_headers: dict):
    """Filtering by store returns store-specific products with latest store-level inventory."""
    res = client.get("/api/v1/products?store=STORE-01", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    for item in data["items"]:
        assert item["store_id"] == "STORE-01"
        assert item["current_stock"] >= 0

