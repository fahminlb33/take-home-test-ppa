from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import engine
from .model import (
    BinLocation,
    InventoryBalance,
    PartMaster,
    Site,
    StockSerialBatch,
    Warehouse,
)


def _part_for_sku(session: Session, internal_sku: str) -> PartMaster:
    part = session.scalar(
        select(PartMaster).where(PartMaster.internal_sku == internal_sku)
    )

    if part is None:
        raise ValueError(f"No part found for internal SKU {internal_sku!r}.")
    
    return part


def get_stock_parameters(internal_sku: str) -> dict[str, Any]:
    """View reorder thresholds and critical/hazardous flags for a part."""

    with Session(engine) as session:
        part = _part_for_sku(session, internal_sku)
        return {
            "internal_sku": part.internal_sku,
            "description": part.description,
            "is_critical_spare": bool(part.is_critical_spare),
            "is_hazardous": bool(part.is_hazardous),
            "min_safety_stock": part.min_safety_stock,
            "reorder_point": part.reorder_point,
            "reorder_quantity": part.reorder_quantity,
        }


def update_reorder_parameters(
    internal_sku: str,
    min_safety_stock: int | None = None,
    reorder_point: int | None = None,
    reorder_quantity: int | None = None,
) -> dict[str, Any]:
    """Update one or more non-negative reorder thresholds for a part."""

    updates = {
        "min_safety_stock": min_safety_stock,
        "reorder_point": reorder_point,
        "reorder_quantity": reorder_quantity,
    }

    requested_updates = {
        key: value for key, value in updates.items() if value is not None
    }

    if not requested_updates:
        raise ValueError("Provide at least one reorder parameter to update.")
    
    for name, value in requested_updates.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer.")

    with Session(engine) as session, session.begin():
        part = _part_for_sku(session, internal_sku)
        for name, value in requested_updates.items():
            setattr(part, name, value)
        session.flush()
        return {
            "internal_sku": part.internal_sku,
            "description": part.description,
            "is_critical_spare": bool(part.is_critical_spare),
            "is_hazardous": bool(part.is_hazardous),
            "min_safety_stock": part.min_safety_stock,
            "reorder_point": part.reorder_point,
            "reorder_quantity": part.reorder_quantity,
        }


def _balance_summary(
    balance: InventoryBalance,
) -> dict[str, Any]:
    bin_location = balance.bin
    warehouse = bin_location.warehouse
    return {
        "site_code": warehouse.site.site_code,
        "warehouse_code": warehouse.warehouse_code,
        "warehouse_name": warehouse.warehouse_name,
        "bin_code": bin_location.bin_code,
        "zone": bin_location.zone,
        "qty_on_hand": balance.qty_on_hand,
        "qty_reserved": balance.qty_reserved,
        "qty_available": max(balance.qty_on_hand - balance.qty_reserved, 0),
        "qty_on_order": balance.qty_on_order,
    }


def check_stock_availability(
    internal_sku: str,
    site_code: str | None = None,
    warehouse_code: str | None = None,
    bin_code: str | None = None,
) -> dict[str, Any]:
    """Report balance quantities by bin; availability is on hand minus reserved."""
    statement = (
        select(InventoryBalance)
        .join(BinLocation, InventoryBalance.bin_id == BinLocation.bin_id)
        .join(Warehouse, BinLocation.warehouse_id == Warehouse.warehouse_id)
        .join(Site, Warehouse.site_id == Site.site_id)
        .join(PartMaster, InventoryBalance.part_id == PartMaster.part_id)
        .where(PartMaster.internal_sku == internal_sku)
        .order_by(Site.site_code, Warehouse.warehouse_code, BinLocation.bin_code)
    )

    if site_code:
        statement = statement.where(Site.site_code == site_code)

    if warehouse_code:
        statement = statement.where(Warehouse.warehouse_code == warehouse_code)

    if bin_code:
        statement = statement.where(BinLocation.bin_code == bin_code)

    with Session(engine) as session:
        part = _part_for_sku(session, internal_sku)
        balances = list(session.scalars(statement))
        locations = [_balance_summary(balance) for balance in balances]

        return {
            "internal_sku": part.internal_sku,
            "description": part.description,
            "locations": locations,
            "totals": {
                "qty_on_hand": sum(item["qty_on_hand"] for item in locations),
                "qty_reserved": sum(item["qty_reserved"] for item in locations),
                "qty_available": sum(item["qty_available"] for item in locations),
                "qty_on_order": sum(item["qty_on_order"] for item in locations),
            },
            "availability_note": (
                "Batch status has no quantity in the schema and is not deducted from "
                "available quantity."
            ),
        }


def search_serial_batches(
    internal_sku: str | None = None,
    serial_number: str | None = None,
    batch_number: str | None = None,
    include_expired: bool = True,
) -> list[dict[str, Any]]:
    """Search serial and batch records by SKU/serial/lot, including status and expiry."""

    # if not any((internal_sku, serial_number, batch_number)):
    #     raise ValueError("Provide an SKU, serial number, or batch number.")
    
    statement = (
        select(StockSerialBatch, InventoryBalance, PartMaster)
        .join(
            InventoryBalance,
            StockSerialBatch.inventory_id == InventoryBalance.inventory_id,
        )
        .join(PartMaster, InventoryBalance.part_id == PartMaster.part_id)
    )

    if internal_sku:
        statement = statement.where(PartMaster.internal_sku == internal_sku)

    if serial_number:
        statement = statement.where(
            func.lower(StockSerialBatch.serial_number).contains(
                serial_number.lower(), autoescape=True
            )
        )

    if batch_number:
        statement = statement.where(
            func.lower(StockSerialBatch.batch_number).contains(
                batch_number.lower(), autoescape=True
            )
        )

    if not include_expired:
        statement = statement.where(
            (StockSerialBatch.expiry_date.is_(None))
            | (StockSerialBatch.expiry_date >= date.today().isoformat())
        )

    with Session(engine) as session:
        return [
            {
                "internal_sku": part.internal_sku,
                "description": part.description,
                "serial_number": batch.serial_number,
                "batch_number": batch.batch_number,
                "expiry_date": batch.expiry_date,
                "is_expired": bool(
                    batch.expiry_date and batch.expiry_date < date.today().isoformat()
                ),
                "status": batch.status,
                "location": _balance_summary(inventory),
            }
            for batch, inventory, part in session.execute(statement)
        ]


def set_stock_batch_status(serial_batch_id: int, status: str) -> dict[str, Any]:
    """Set a serial/batch status supported by the schema."""

    if status not in {"available", "reserved", "quarantine", "in_transit", "scrapped"}:
        raise ValueError("Unsupported serial/batch status.")
    
    with Session(engine) as session, session.begin():
        batch = session.get(StockSerialBatch, serial_batch_id)
        if batch is None:
            raise ValueError(f"No serial or batch found for ID {serial_batch_id}.")
        
        if status == "available" and batch.expiry_date:
            if batch.expiry_date < date.today().isoformat():
                raise ValueError("Expired stock cannot be marked available.")
            
        batch.status = status
        return {
            "serial_batch_id": batch.serial_batch_id,
            "serial_number": batch.serial_number,
            "batch_number": batch.batch_number,
            "expiry_date": batch.expiry_date,
            "status": batch.status,
        }

