from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .db import engine
from .model import (
    BinLocation,
    InventoryBalance,
    PartEquipmentXref,
    PartMaster,
    PartSubstitution,
    Site,
    Warehouse,
)


def _part_summary(part: PartMaster) -> dict[str, Any]:
    return {
        "internal_sku": part.internal_sku,
        "oem_part_number": part.oem_part_number,
        "oem_name": part.oem_name,
        "description": part.description,
        "category": part.category,
        "unit_of_measure": part.unit_of_measure,
        "is_critical_spare": bool(part.is_critical_spare),
        "is_hazardous": bool(part.is_hazardous),
        "min_safety_stock": part.min_safety_stock,
        "reorder_point": part.reorder_point,
        "reorder_quantity": part.reorder_quantity,
    }


def search_parts(
    query: str | None = None, component_group: str | None = None
) -> list[dict[str, Any]]:
    """Search the part master by SKU, OEM part number, description, or component group."""

    search_term = query.strip() if query else ""
    group_term = component_group.strip() if component_group else ""
    if not search_term and not group_term:
        raise ValueError("Provide a search query, component group, or both.")

    statement = select(PartMaster).distinct()
    if search_term:
        statement = statement.where(
            or_(
                func.lower(PartMaster.internal_sku).contains(
                    search_term.lower(), autoescape=True
                ),
                func.lower(PartMaster.oem_part_number).contains(
                    search_term.lower(), autoescape=True
                ),
                func.lower(PartMaster.description).contains(
                    search_term.lower(), autoescape=True
                ),
                func.lower(PartMaster.category).contains(
                    search_term.lower(), autoescape=True
                ),
            )
        )

    if group_term:
        statement = statement.join(PartEquipmentXref).where(
            func.lower(PartEquipmentXref.component_group).contains(
                group_term.lower(), autoescape=True
            )
        )

    with Session(engine) as session:
        results: list[dict[str, Any]] = []
        for part in session.scalars(statement.order_by(PartMaster.internal_sku)):
            row = _part_summary(part)
            groups = set(
                session.scalars(
                    select(PartEquipmentXref.component_group).where(
                        PartEquipmentXref.part_id == part.part_id
                    )
                )
            )

            row["component_groups"] = sorted(group for group in groups if group)
            results.append(row)

        return results


def get_part_interchangeability(
    internal_sku: str,
) -> list[dict[str, Any]]:
    """List substitution candidates and their notes; approval is not stored."""

    with Session(engine) as session:
        part = session.scalar(
            select(PartMaster).where(PartMaster.internal_sku == internal_sku)
        )

        if part is None:
            raise ValueError(f"No part found for internal SKU {internal_sku!r}.")

        outbound = (
            select(PartSubstitution, PartMaster)
            .join(PartMaster, PartMaster.part_id == PartSubstitution.substitute_part_id)
            .where(PartSubstitution.primary_part_id == part.part_id)
        )

        inbound = (
            select(PartSubstitution, PartMaster)
            .join(PartMaster, PartMaster.part_id == PartSubstitution.primary_part_id)
            .where(PartSubstitution.substitute_part_id == part.part_id)
        )

        results: list[dict[str, Any]] = []
        for statement, direction in (
            (outbound, "substitute_for"),
            (inbound, "alternative_to"),
        ):
            for substitution, related_part in session.execute(statement):
                results.append(
                    {
                        **_part_summary(related_part),
                        "relationship_direction": direction,
                        "substitution_notes": substitution.substitution_notes,
                        "approval_status": "not_recorded",
                    }
                )

        return results


def map_parts_to_equipment(
    equipment_model: str,
    component_group: str | None = None,
) -> list[dict[str, Any]]:
    """Find parts mapped to an equipment model and optional component group."""

    model_term = equipment_model.strip()
    group_term = component_group.strip() if component_group else ""
    if not model_term:
        raise ValueError("Provide an equipment model.")

    with Session(engine) as session:
        model_matches = (
            select(PartMaster, PartEquipmentXref)
            .join(PartEquipmentXref, PartEquipmentXref.part_id == PartMaster.part_id)
            .where(
                func.lower(PartEquipmentXref.equipment_model).contains(
                    model_term.lower(), autoescape=True
                )
            )
        )

        if group_term:
            model_matches = model_matches.where(
                func.lower(PartEquipmentXref.component_group).contains(
                    group_term.lower(), autoescape=True
                )
            )

        return [
            {
                **_part_summary(part),
                "equipment_model": xref.equipment_model,
                "component_group": xref.component_group,
            }
            for part, xref in session.execute(model_matches)
        ]


def find_storage_locations(
    internal_sku: str | None = None,
    warehouse_type: str | None = None,
    zone: str | None = None,
    site_code: str | None = None,
    warehouse_code: str | None = None,
    bin_code: str | None = None,
) -> list[dict[str, Any]]:
    """Look up warehouse/bin details and any stock recorded at those locations."""

    sku_term = internal_sku.strip() if internal_sku else ""
    warehouse_term = warehouse_type.strip() if warehouse_type else ""
    zone_term = zone.strip() if zone else ""
    site_term = site_code.strip() if site_code else ""
    warehouse_code_term = warehouse_code.strip() if warehouse_code else ""
    bin_term = bin_code.strip() if bin_code else ""

    if not any(
        (sku_term, warehouse_term, zone_term, site_term, warehouse_code_term, bin_term)
    ):
        raise ValueError(
            "Provide a part SKU, warehouse type/code, zone, site code, or bin code."
        )

    statement = (
        select(BinLocation, Warehouse, Site, InventoryBalance, PartMaster)
        .join(Warehouse, BinLocation.warehouse_id == Warehouse.warehouse_id)
        .join(Site, Warehouse.site_id == Site.site_id)
        .outerjoin(InventoryBalance, InventoryBalance.bin_id == BinLocation.bin_id)
        .outerjoin(PartMaster, PartMaster.part_id == InventoryBalance.part_id)
    )

    if sku_term:
        statement = statement.where(PartMaster.internal_sku == sku_term)

    if warehouse_term:
        statement = statement.where(
            func.lower(Warehouse.warehouse_type).contains(
                warehouse_term.lower(), autoescape=True
            )
        )

    if zone_term:
        statement = statement.where(
            func.lower(BinLocation.zone).contains(zone_term.lower(), autoescape=True)
        )

    if site_term:
        statement = statement.where(Site.site_code == site_term)

    if warehouse_code_term:
        statement = statement.where(Warehouse.warehouse_code == warehouse_code_term)
    
    if bin_term:
        statement = statement.where(BinLocation.bin_code == bin_term)

    with Session(engine) as session:
        results: list[dict[str, Any]] = []
        for bin_location, warehouse, site, inventory, part in session.execute(
            statement
        ):
            results.append(
                {
                    "site_code": site.site_code,
                    "site_name": site.site_name,
                    "warehouse_code": warehouse.warehouse_code,
                    "warehouse_name": warehouse.warehouse_name,
                    "warehouse_type": warehouse.warehouse_type,
                    "bin_code": bin_location.bin_code,
                    "zone": bin_location.zone,
                    "part": _part_summary(part) if part else None,
                    "qty_on_hand": inventory.qty_on_hand if inventory else None,
                    "qty_reserved": inventory.qty_reserved if inventory else None,
                    "qty_on_order": inventory.qty_on_order if inventory else None,
                }
            )

        return results


def list_sites_warehouses_bins(
    site_code: str | None = None,
    warehouse_code: str | None = None,
) -> list[dict[str, Any]]:
    """List sites, their warehouses, and each warehouse's bin locations."""

    statement = (
        select(Site, Warehouse, BinLocation)
        .outerjoin(Warehouse, Warehouse.site_id == Site.site_id)
        .outerjoin(BinLocation, BinLocation.warehouse_id == Warehouse.warehouse_id)
        .order_by(
            Site.site_code,
            Warehouse.warehouse_code,
            BinLocation.bin_code,
        )
    )

    if site_code:
        statement = statement.where(Site.site_code == site_code)

    if warehouse_code:
        statement = statement.where(Warehouse.warehouse_code == warehouse_code)

    with Session(engine) as session:
        sites: dict[str, dict[str, Any]] = {}
        for site, warehouse, bin_location in session.execute(statement):
            site_info = sites.setdefault(
                site.site_code,
                {
                    "site_code": site.site_code,
                    "site_name": site.site_name,
                    "time_zone": site.time_zone,
                    "warehouses": [],
                },
            )

            if warehouse is None:
                continue

            warehouses = site_info["warehouses"]
            warehouse_info = next(
                (
                    item
                    for item in warehouses
                    if item["warehouse_code"] == warehouse.warehouse_code
                ),
                None,
            )

            if warehouse_info is None:
                warehouse_info = {
                    "warehouse_code": warehouse.warehouse_code,
                    "warehouse_name": warehouse.warehouse_name,
                    "warehouse_type": warehouse.warehouse_type,
                    "bin_locations": [],
                }
                warehouses.append(warehouse_info)
                
            if bin_location is not None:
                warehouse_info["bin_locations"].append(
                    {
                        "bin_code": bin_location.bin_code,
                        "zone": bin_location.zone,
                    }
                )

        return list(sites.values())
