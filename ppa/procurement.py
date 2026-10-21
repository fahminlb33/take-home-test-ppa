from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import engine
from .model import (
    BinLocation,
    InventoryBalance,
    PartMaster,
    POLineItem,
    PurchaseOrder,
    Site,
    Supplier,
    Warehouse,
)

_PO_STATUSES = {
    "draft",
    "pending_approval",
    "approved",
    "issued",
    "partially_received",
    "received",
    "cancelled",
}

_PO_TRANSITIONS = {
    "draft": {"pending_approval", "cancelled"},
    "pending_approval": {"approved", "draft", "cancelled"},
    "approved": {"issued", "cancelled"},
    "issued": {"cancelled"},
    "partially_received": {"issued", "cancelled"},
    "received": set(),
    "cancelled": set(),
}

_URGENCIES = {"routine", "medium", "high", "down_equipment_vop"}


def _po_summary(order: PurchaseOrder) -> dict[str, Any]:
    return {
        "po_number": order.po_number,
        "status": order.status,
        "urgency": order.urgency,
        "requested_by": order.requested_by,
        "created_at": order.created_at,
        "expected_delivery_date": order.expected_delivery_date,
        "site_code": order.site.site_code,
        "supplier": {
            "vendor_code": order.supplier.vendor_code,
            "vendor_name": order.supplier.vendor_name,
            "contact_email": order.supplier.contact_email,
            "contact_phone": order.supplier.contact_phone,
            "standard_lead_time_days": order.supplier.standard_lead_time_days,
            "is_vmi_vendor": bool(order.supplier.is_vmi_vendor),
        },
        "line_items": [
            {
                "line_number": line.line_number,
                "internal_sku": line.part.internal_sku,
                "description": line.part.description,
                "qty_ordered": line.qty_ordered,
                "qty_received": line.qty_received,
                "qty_open": line.qty_ordered - line.qty_received,
                "unit_price": line.unit_price,
                "line_status": line.line_status,
            }
            for line in order.line_items
        ],
    }


def track_purchase_orders(
    po_number: str | None = None,
    status: str | None = None,
    open_only: bool = True,
) -> list[dict[str, Any]]:
    """Track POs by number and status, including line quantities and ETA."""

    statement = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc())
    if po_number:
        statement = statement.where(PurchaseOrder.po_number == po_number)

    if status:
        if status not in _PO_STATUSES:
            raise ValueError(f"Unsupported PO status {status!r}.")
        statement = statement.where(PurchaseOrder.status == status)
    elif open_only:
        statement = statement.where(
            PurchaseOrder.status.not_in(("received", "cancelled"))
        )

    with Session(engine) as session:
        return [_po_summary(order) for order in session.scalars(statement)]


def track_incoming_shipments(
    po_number: str | None = None,
) -> list[dict[str, Any]]:
    """List open POs and their expected delivery dates; shipment manifests are not stored."""

    statement = select(PurchaseOrder).where(
        PurchaseOrder.status.not_in(("received", "cancelled"))
    )

    if po_number:
        statement = statement.where(PurchaseOrder.po_number == po_number)

    statement = statement.order_by(PurchaseOrder.expected_delivery_date)
    with Session(engine) as session:
        return [_po_summary(order) for order in session.scalars(statement)]


def _vendor_summary(supplier: Supplier) -> dict[str, Any]:
    return {
        "vendor_code": supplier.vendor_code,
        "vendor_name": supplier.vendor_name,
        "contact_email": supplier.contact_email,
        "contact_phone": supplier.contact_phone,
        "standard_lead_time_days": supplier.standard_lead_time_days,
        "is_vmi_vendor": bool(supplier.is_vmi_vendor),
    }



def lookup_vendors(
    vendor_code: str | None = None, vendor_name: str | None = None
) -> list[dict[str, Any]]:
    """Look up vendor contact, VMI flag, and standard lead time."""

    if not any((vendor_code, vendor_name)):
        raise ValueError("Provide a vendor code or vendor name.")
    
    statement = select(Supplier).order_by(Supplier.vendor_name)
    if vendor_code:
        statement = statement.where(Supplier.vendor_code == vendor_code)

    if vendor_name:
        statement = statement.where(
            func.lower(Supplier.vendor_name).contains(
                vendor_name.lower(), autoescape=True
            )
        )

    with Session(engine) as session:
        return [
            _vendor_summary(supplier)
            for supplier in session.scalars(statement)
        ]


def list_available_vendors() -> list[dict[str, Any]]:
    """List all available vendors and their contact and procurement details."""

    statement = select(Supplier).order_by(Supplier.vendor_name)
    with Session(engine) as session:
        return [
            _vendor_summary(supplier)
            for supplier in session.scalars(statement)
        ]
    

def create_purchase_order(
    po_number: str,
    supplier_vendor_code: str,
    site_code: str,
    internal_sku: str,
    quantity: int,
    requested_by: str,
    urgency: str = "routine",
    expected_delivery_date: str | None = None,
    unit_price: float | None = None,
) -> dict[str, Any]:
    """Create a PO with one part line, including emergency/down-equipment priority."""

    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("PO quantity must be a positive integer.")
    if urgency not in _URGENCIES:
        raise ValueError(f"Urgency must be one of {sorted(_URGENCIES)}.")
    if urgency in {"high", "down_equipment_vop"} and not requested_by.strip():
        raise ValueError("Provide the requester for an emergency PO.")
    if expected_delivery_date:
        try:
            date.fromisoformat(expected_delivery_date[:10])
        except ValueError as exc:
            raise ValueError("Expected delivery date must be ISO formatted.") from exc

    with Session(engine) as session, session.begin():
        supplier = session.scalar(
            select(Supplier).where(Supplier.vendor_code == supplier_vendor_code)
        )
        site = session.scalar(select(Site).where(Site.site_code == site_code))
        part = session.scalar(
            select(PartMaster).where(PartMaster.internal_sku == internal_sku)
        )

        if supplier is None:
            raise ValueError(
                f"No vendor found for vendor code {supplier_vendor_code!r}."
            )
        
        if site is None:
            raise ValueError(f"No site found for site code {site_code!r}.")
        
        if part is None:
            raise ValueError(f"No part found for internal SKU {internal_sku!r}.")
        
        order = PurchaseOrder(
            po_number=po_number,
            supplier=supplier,
            site=site,
            status="draft",
            urgency=urgency,
            requested_by=requested_by,
            expected_delivery_date=expected_delivery_date,
        )

        order.line_items.append(
            POLineItem(
                line_number=1,
                part=part,
                qty_ordered=quantity,
                unit_price=unit_price,
            )
        )

        session.add(order)
        session.flush()
        
        return _po_summary(order)


def update_purchase_order_status(po_number: str, new_status: str) -> dict[str, Any]:
    """Update a PO to a valid workflow status."""

    if new_status not in _PO_STATUSES:
        raise ValueError(f"Unsupported PO status {new_status!r}.")
    
    with Session(engine) as session, session.begin():
        order = session.scalar(
            select(PurchaseOrder).where(PurchaseOrder.po_number == po_number)
        )

        if order is None:
            raise ValueError(f"No purchase order found for {po_number!r}.")
        
        if new_status not in _PO_TRANSITIONS.get(order.status or "", set()):
            raise ValueError(
                f"Cannot change PO status from {order.status!r} to {new_status!r}."
            )
        
        order.status = new_status
        return _po_summary(order)


def log_goods_receipt(
    po_number: str,
    line_number: int,
    quantity: int,
    warehouse_code: str,
    bin_code: str,
    received_by: str,
) -> dict[str, Any]:
    """Update the PO line received quantity and on-hand balance for a received delivery."""

    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("Receipt quantity must be a positive integer.")
    
    if not received_by.strip():
        raise ValueError("Provide the receiver name.")
    
    with Session(engine) as session, session.begin():
        order = session.scalar(
            select(PurchaseOrder).where(PurchaseOrder.po_number == po_number)
        )

        if order is None:
            raise ValueError(f"No purchase order found for {po_number!r}.")
        
        if order.status not in {"approved", "issued", "partially_received"}:
            raise ValueError(f"Cannot receive against PO with status {order.status!r}.")
        
        line = session.get(POLineItem, (order.po_id, line_number))
        if line is None:
            raise ValueError(f"No PO line {line_number} found on {po_number!r}.")
        
        remaining = line.qty_ordered - line.qty_received
        if quantity > remaining:
            raise ValueError(
                f"Receipt exceeds open PO quantity ({remaining} remaining)."
            )
        
        bins = list(
            session.scalars(
                select(BinLocation)
                .join(Warehouse, BinLocation.warehouse_id == Warehouse.warehouse_id)
                .where(
                    Warehouse.site_id == order.site_id,
                    Warehouse.warehouse_code == warehouse_code,
                    BinLocation.bin_code == bin_code,
                )
            )
        )

        if len(bins) != 1:
            raise ValueError("No unique receiving bin found at the PO site.")
        
        bin_location = bins[0]
        balance = session.scalar(
            select(InventoryBalance).where(
                InventoryBalance.part_id == line.part_id,
                InventoryBalance.bin_id == bin_location.bin_id,
            )
        )

        if balance is None:
            balance = InventoryBalance(
                part_id=line.part_id,
                bin_id=bin_location.bin_id,
                qty_on_hand=0,
                qty_reserved=0,
                qty_on_order=0,
            )
            session.add(balance)

        balance.qty_on_hand += quantity
        line.qty_received += quantity
        line.line_status = (
            "RECEIVED" if line.qty_received == line.qty_ordered else "PARTIAL"
        )
        all_lines = list(
            session.scalars(select(POLineItem).where(POLineItem.po_id == order.po_id))
        )

        if all(item.qty_received == item.qty_ordered for item in all_lines):
            order.status = "received"
        else:
            order.status = "partially_received"

        session.flush()

        return {
            "po_number": order.po_number,
            "line_number": line.line_number,
            "internal_sku": line.part.internal_sku,
            "quantity_received": quantity,
            "qty_received_total": line.qty_received,
            "qty_open": line.qty_ordered - line.qty_received,
            "po_status": order.status,
            "received_by": received_by,
            "location": {
                "warehouse_code": bin_location.warehouse.warehouse_code,
                "bin_code": bin_location.bin_code,
                "qty_on_hand": balance.qty_on_hand,
            },
        }
