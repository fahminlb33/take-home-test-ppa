-- Enable Foreign Key Constraints in SQLite
PRAGMA foreign_keys = ON;

-- ============================================================================
-- 1. LOCATIONS & WAREHOUSES
-- ============================================================================

CREATE TABLE sites (
    site_id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_code TEXT UNIQUE NOT NULL,      -- e.g., 'PIT-A', 'PLANT-01'
    site_name TEXT NOT NULL,
    time_zone TEXT DEFAULT 'UTC',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE warehouses (
    warehouse_id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    warehouse_code TEXT NOT NULL,        -- e.g., 'WH-MAIN', 'CRIB-3'
    warehouse_name TEXT NOT NULL,
    warehouse_type TEXT,                -- 'Central Warehouse', 'Tool Crib', 'Laydown Yard', 'Fuel Farm'
    FOREIGN KEY (site_id) REFERENCES sites(site_id) ON DELETE CASCADE,
    UNIQUE(site_id, warehouse_code)
);

CREATE TABLE bin_locations (
    bin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id INTEGER NOT NULL,
    bin_code TEXT NOT NULL,              -- e.g., 'A-02-R03-S1'
    zone TEXT,                           -- 'Flammables', 'Heavy Spares'
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    UNIQUE(warehouse_id, bin_code)
);

-- ============================================================================
-- 2. PART MASTER & CROSS-REFERENCING
-- ============================================================================

CREATE TABLE part_master (
    part_id INTEGER PRIMARY KEY AUTOINCREMENT,
    internal_sku TEXT UNIQUE NOT NULL,   -- Internal ERP SKU
    oem_part_number TEXT,
    oem_name TEXT,                       -- e.g., 'Caterpillar', 'Komatsu'
    description TEXT NOT NULL,
    category TEXT,                       -- 'Filters', 'GET', 'Hydraulics', 'Reagents'
    unit_of_measure TEXT NOT NULL,       -- 'EA', 'KG', 'LITER', 'METERS'
    is_critical_spare INTEGER DEFAULT 0, -- 0 = False, 1 = True
    is_hazardous INTEGER DEFAULT 0,      -- 0 = False, 1 = True
    min_safety_stock INTEGER DEFAULT 0,
    reorder_point INTEGER DEFAULT 0,
    reorder_quantity INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Interchangeable / Substitute Parts Mapping
CREATE TABLE part_substitutions (
    primary_part_id INTEGER NOT NULL,
    substitute_part_id INTEGER NOT NULL,
    substitution_notes TEXT,
    PRIMARY KEY (primary_part_id, substitute_part_id),
    FOREIGN KEY (primary_part_id) REFERENCES part_master(part_id) ON DELETE CASCADE,
    FOREIGN KEY (substitute_part_id) REFERENCES part_master(part_id) ON DELETE CASCADE
);

-- Map parts to mining equipment models for quick ADK tool lookups
CREATE TABLE part_equipment_xref (
    part_id INTEGER NOT NULL,
    equipment_model TEXT NOT NULL,       -- e.g., 'CAT 797F', 'Komatsu PC8000'
    component_group TEXT,                -- e.g., 'Final Drive', 'Engine Air Intake'
    PRIMARY KEY (part_id, equipment_model),
    FOREIGN KEY (part_id) REFERENCES part_master(part_id) ON DELETE CASCADE
);

-- ============================================================================
-- 3. INVENTORY BALANCES & SERIAL/BATCH TRACKING
-- ============================================================================

CREATE TABLE inventory_balances (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL,
    bin_id INTEGER NOT NULL,
    qty_on_hand INTEGER NOT NULL DEFAULT 0 CHECK (qty_on_hand >= 0),
    qty_reserved INTEGER NOT NULL DEFAULT 0 CHECK (qty_reserved >= 0),
    qty_on_order INTEGER NOT NULL DEFAULT 0 CHECK (qty_on_order >= 0),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (part_id) REFERENCES part_master(part_id) ON DELETE CASCADE,
    FOREIGN KEY (bin_id) REFERENCES bin_locations(bin_id) ON DELETE CASCADE,
    UNIQUE(part_id, bin_id)
);

CREATE TABLE stock_serial_batches (
    serial_batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id INTEGER NOT NULL,
    serial_number TEXT,
    batch_number TEXT,
    expiry_date TEXT,                    -- ISO8601 string 'YYYY-MM-DD'
    status TEXT DEFAULT 'available' CHECK (status IN ('available', 'reserved', 'quarantine', 'in_transit', 'scrapped')),
    received_date TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (inventory_id) REFERENCES inventory_balances(inventory_id) ON DELETE CASCADE
);

-- ============================================================================
-- 4. PROCUREMENT & SUPPLIERS
-- ============================================================================

CREATE TABLE suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_code TEXT UNIQUE NOT NULL,
    vendor_name TEXT NOT NULL,
    contact_email TEXT,
    contact_phone TEXT,
    standard_lead_time_days INTEGER DEFAULT 7,
    is_vmi_vendor INTEGER DEFAULT 0      -- 0 = False, 1 = True (Vendor Managed Inventory)
);

CREATE TABLE purchase_orders (
    po_id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT UNIQUE NOT NULL,
    supplier_id INTEGER NOT NULL,
    site_id INTEGER NOT NULL,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'pending_approval', 'approved', 'issued', 'partially_received', 'received', 'cancelled')),
    urgency TEXT DEFAULT 'routine' CHECK (urgency IN ('routine', 'medium', 'high', 'down_equipment_vop')),
    requested_by TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    expected_delivery_date TEXT,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    FOREIGN KEY (site_id) REFERENCES sites(site_id)
);

CREATE TABLE po_line_items (
    po_line_id INTEGER,
    po_id INTEGER NOT NULL,
    line_number INTEGER NOT NULL,
    part_id INTEGER NOT NULL,
    qty_ordered INTEGER NOT NULL CHECK (qty_ordered > 0),
    qty_received INTEGER NOT NULL DEFAULT 0 CHECK (qty_received <= qty_ordered),
    unit_price REAL,
    line_status TEXT DEFAULT 'OPEN',
    PRIMARY KEY (po_id, line_number),
    FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES part_master(part_id)
);

-- ============================================================================
-- 5. PERFORMANCE INDEXES FOR ADK AGENT QUERIES
-- ============================================================================

-- Speed up SKU and OEM number lookups from user prompts
CREATE INDEX idx_part_sku ON part_master(internal_sku);
CREATE INDEX idx_part_oem ON part_master(oem_part_number);

-- Speed up stock queries across bins and warehouses
CREATE INDEX idx_inv_part ON inventory_balances(part_id);
CREATE INDEX idx_inv_bin ON inventory_balances(bin_id);

-- Speed up PO tracking by PO Number and Urgency
CREATE INDEX idx_po_number ON purchase_orders(po_number);
CREATE INDEX idx_po_urgency ON purchase_orders(urgency);
