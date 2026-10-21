from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Site(Base):
    __tablename__ = "sites"

    site_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    site_name: Mapped[str] = mapped_column(Text, nullable=False)
    time_zone: Mapped[str | None] = mapped_column(Text, server_default=text("'UTC'"))
    created_at: Mapped[str | None] = mapped_column(
        Text, server_default=text("(datetime('now'))")
    )

    warehouses: Mapped[list["Warehouse"]] = relationship(back_populates="site")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="site")


class Warehouse(Base):
    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("site_id", "warehouse_code"),)

    warehouse_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.site_id", ondelete="CASCADE"), nullable=False
    )
    warehouse_code: Mapped[str] = mapped_column(Text, nullable=False)
    warehouse_name: Mapped[str] = mapped_column(Text, nullable=False)
    warehouse_type: Mapped[str | None] = mapped_column(Text)

    site: Mapped["Site"] = relationship(back_populates="warehouses")
    bin_locations: Mapped[list["BinLocation"]] = relationship(
        back_populates="warehouse"
    )


class BinLocation(Base):
    __tablename__ = "bin_locations"
    __table_args__ = (UniqueConstraint("warehouse_id", "bin_code"),)

    bin_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.warehouse_id", ondelete="CASCADE"), nullable=False
    )
    bin_code: Mapped[str] = mapped_column(Text, nullable=False)
    zone: Mapped[str | None] = mapped_column(Text)

    warehouse: Mapped["Warehouse"] = relationship(back_populates="bin_locations")
    inventory_balances: Mapped[list["InventoryBalance"]] = relationship(
        back_populates="bin"
    )


class PartMaster(Base):
    __tablename__ = "part_master"
    __table_args__ = (
        Index("idx_part_sku", "internal_sku"),
        Index("idx_part_oem", "oem_part_number"),
    )

    part_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_sku: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    oem_part_number: Mapped[str | None] = mapped_column(Text)
    oem_name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    unit_of_measure: Mapped[str] = mapped_column(Text, nullable=False)
    is_critical_spare: Mapped[bool | None] = mapped_column(
        Boolean, server_default=text("0")
    )
    is_hazardous: Mapped[bool | None] = mapped_column(Boolean, server_default=text("0"))
    min_safety_stock: Mapped[int | None] = mapped_column(
        Integer, server_default=text("0")
    )
    reorder_point: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    reorder_quantity: Mapped[int | None] = mapped_column(
        Integer, server_default=text("0")
    )
    created_at: Mapped[str | None] = mapped_column(
        Text, server_default=text("(datetime('now'))")
    )

    substitutions: Mapped[list["PartSubstitution"]] = relationship(
        foreign_keys="PartSubstitution.primary_part_id",
        back_populates="primary_part",
    )
    substituted_by: Mapped[list["PartSubstitution"]] = relationship(
        foreign_keys="PartSubstitution.substitute_part_id",
        back_populates="substitute_part",
    )
    equipment_xrefs: Mapped[list["PartEquipmentXref"]] = relationship(
        back_populates="part"
    )
    inventory_balances: Mapped[list["InventoryBalance"]] = relationship(
        back_populates="part"
    )
    po_line_items: Mapped[list["POLineItem"]] = relationship(back_populates="part")


class PartSubstitution(Base):
    __tablename__ = "part_substitutions"

    primary_part_id: Mapped[int] = mapped_column(
        ForeignKey("part_master.part_id", ondelete="CASCADE"), primary_key=True
    )
    substitute_part_id: Mapped[int] = mapped_column(
        ForeignKey("part_master.part_id", ondelete="CASCADE"), primary_key=True
    )
    substitution_notes: Mapped[str | None] = mapped_column(Text)

    primary_part: Mapped["PartMaster"] = relationship(
        foreign_keys=[primary_part_id], back_populates="substitutions"
    )
    substitute_part: Mapped["PartMaster"] = relationship(
        foreign_keys=[substitute_part_id], back_populates="substituted_by"
    )


class PartEquipmentXref(Base):
    __tablename__ = "part_equipment_xref"

    part_id: Mapped[int] = mapped_column(
        ForeignKey("part_master.part_id", ondelete="CASCADE"), primary_key=True
    )
    equipment_model: Mapped[str] = mapped_column(Text, primary_key=True)
    component_group: Mapped[str | None] = mapped_column(Text)

    part: Mapped["PartMaster"] = relationship(back_populates="equipment_xrefs")


class InventoryBalance(Base):
    __tablename__ = "inventory_balances"
    __table_args__ = (
        CheckConstraint("qty_on_hand >= 0"),
        CheckConstraint("qty_reserved >= 0"),
        CheckConstraint("qty_on_order >= 0"),
        UniqueConstraint("part_id", "bin_id"),
        Index("idx_inv_part", "part_id"),
        Index("idx_inv_bin", "bin_id"),
    )

    inventory_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    part_id: Mapped[int] = mapped_column(
        ForeignKey("part_master.part_id", ondelete="CASCADE"), nullable=False
    )
    bin_id: Mapped[int] = mapped_column(
        ForeignKey("bin_locations.bin_id", ondelete="CASCADE"), nullable=False
    )
    qty_on_hand: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    qty_reserved: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    qty_on_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    updated_at: Mapped[str | None] = mapped_column(
        Text, server_default=text("(datetime('now'))")
    )

    part: Mapped["PartMaster"] = relationship(back_populates="inventory_balances")
    bin: Mapped["BinLocation"] = relationship(back_populates="inventory_balances")
    stock_serial_batches: Mapped[list["StockSerialBatch"]] = relationship(
        back_populates="inventory"
    )


class StockSerialBatch(Base):
    __tablename__ = "stock_serial_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'reserved', 'quarantine', 'in_transit', 'scrapped')"
        ),
    )

    serial_batch_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    inventory_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_balances.inventory_id", ondelete="CASCADE"),
        nullable=False,
    )
    serial_number: Mapped[str | None] = mapped_column(Text)
    batch_number: Mapped[str | None] = mapped_column(Text)
    expiry_date: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text, server_default=text("'available'"))
    received_date: Mapped[str | None] = mapped_column(
        Text, server_default=text("(datetime('now'))")
    )

    inventory: Mapped["InventoryBalance"] = relationship(
        back_populates="stock_serial_batches"
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    vendor_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    vendor_name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    standard_lead_time_days: Mapped[int | None] = mapped_column(
        Integer, server_default=text("7")
    )
    is_vmi_vendor: Mapped[bool | None] = mapped_column(
        Boolean, server_default=text("0")
    )

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        back_populates="supplier"
    )


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'pending_approval', 'approved', 'issued', "
            "'partially_received', 'received', 'cancelled')"
        ),
        CheckConstraint(
            "urgency IN ('routine', 'medium', 'high', 'down_equipment_vop')"
        ),
        Index("idx_po_number", "po_number"),
        Index("idx_po_urgency", "urgency"),
    )

    po_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.supplier_id"), nullable=False
    )
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.site_id"), nullable=False)
    status: Mapped[str | None] = mapped_column(Text, server_default=text("'draft'"))
    urgency: Mapped[str | None] = mapped_column(Text, server_default=text("'routine'"))
    requested_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str | None] = mapped_column(
        Text, server_default=text("(datetime('now'))")
    )
    expected_delivery_date: Mapped[str | None] = mapped_column(Text)

    supplier: Mapped["Supplier"] = relationship(back_populates="purchase_orders")
    site: Mapped["Site"] = relationship(back_populates="purchase_orders")
    line_items: Mapped[list["POLineItem"]] = relationship(
        back_populates="purchase_order"
    )


class POLineItem(Base):
    __tablename__ = "po_line_items"
    __table_args__ = (
        CheckConstraint("qty_ordered > 0"),
        CheckConstraint("qty_received <= qty_ordered"),
    )

    po_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.po_id", ondelete="CASCADE"), primary_key=True
    )
    line_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("part_master.part_id"), nullable=False
    )
    qty_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_received: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    unit_price: Mapped[float | None] = mapped_column(Float)
    line_status: Mapped[str | None] = mapped_column(Text, server_default=text("'OPEN'"))

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="line_items")
    part: Mapped["PartMaster"] = relationship(back_populates="po_line_items")
