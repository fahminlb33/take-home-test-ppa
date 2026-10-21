PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- 1. LOCATIONS & WAREHOUSES
-- -----------------------------------------------------------------------------
INSERT INTO sites (site_code, site_name, time_zone) VALUES
('PIT-A', 'Northern Open Pit Mine', 'UTC-7'),
('PLANT-01', 'Primary Concentrator Plant', 'UTC-7');

INSERT INTO warehouses (site_id, warehouse_code, warehouse_name, warehouse_type) VALUES
(1, 'WH-MAIN', 'Main Central Store', 'Central Warehouse'),
(1, 'CRIB-3', 'Pit A Satellite Crib', 'Tool Crib'),
(1, 'LAYDOWN-1', 'Heavy Equipment Yard', 'Laydown Yard'),
(2, 'PLANT-WH', 'Mill & Reagent Store', 'Central Warehouse');

INSERT INTO bin_locations (warehouse_id, bin_code, zone) VALUES
(1, 'A-02-R01-S3', 'General Maintenance'),
(1, 'A-02-R01-S4', 'General Maintenance'),
(1, 'HAZ-CHEM-01', 'Reagents & Flammables'),
(2, 'CR3-FL-12', 'Fast Moving Spares'),
(3, 'LY1-GET-05', 'Heavy Spares'),
(4, 'P1-REAG-02', 'Chemical Storage');

-- -----------------------------------------------------------------------------
-- 2. PART MASTER & CROSS-REFERENCING
-- -----------------------------------------------------------------------------
INSERT INTO part_master 
(internal_sku, oem_part_number, oem_name, description, category, unit_of_measure, is_critical_spare, is_hazardous, min_safety_stock, reorder_point, reorder_quantity) 
VALUES
('SKU-882104', '1R-0749', 'Caterpillar', 'Primary Fuel Filter (Heavy Duty)', 'Filters', 'EA', 0, 0, 10, 15, 30),
('SKU-882109', 'P551311', 'Donaldson', 'Fuel Filter Secondary (1R-0749 Direct Sub)', 'Filters', 'EA', 0, 0, 5, 10, 20),
('SKU-400122', '3102-100', 'Metso Outotec', 'Manganese Lower Jaw Liner - C160 Crusher', 'Crushing GET', 'EA', 1, 0, 2, 2, 4),
('SKU-770019', '209-3205', 'Caterpillar', 'Hydraulic Pump Assembly - 797F', 'Hydraulics', 'EA', 1, 0, 1, 1, 2),
('SKU-100882', 'XANTHATE-SIBX', 'Orica', 'Sodium Isobutyl Xanthate (Collector Reagent)', 'Reagents', 'KG', 0, 1, 1000, 2500, 5000);

-- Part Substitutions (CAT 1R-0749 <-> Donaldson P551311)
INSERT INTO part_substitutions (primary_part_id, substitute_part_id, substitution_notes) VALUES
(1, 2, '100% form, fit, and function equivalent for CAT 3500 series engines');

-- Part to Equipment Cross-Reference
INSERT INTO part_equipment_xref (part_id, equipment_model, component_group) VALUES
(1, 'CAT 797F', 'Engine Fuel System'),
(1, 'CAT 6060', 'Engine Fuel System'),
(2, 'CAT 797F', 'Engine Fuel System'),
(3, 'Metso C160', 'Primary Jaw Crusher'),
(4, 'CAT 797F', 'Main Hydraulic System');

-- -----------------------------------------------------------------------------
-- 3. INVENTORY BALANCES & BATCH/SERIAL TRACKING
-- -----------------------------------------------------------------------------
INSERT INTO inventory_balances (part_id, bin_id, qty_on_hand, qty_reserved, qty_on_order) VALUES
(1, 1, 0, 0, 30),  -- CAT Filter out of stock in WH-MAIN
(2, 2, 6, 1, 0),   -- Donaldson Filter in stock in WH-MAIN (Bin A-02-R01-S4)
(3, 5, 1, 0, 2),   -- Jaw Liner in Laydown Yard
(4, 1, 1, 0, 0),   -- Hydraulic Pump in WH-MAIN
(5, 6, 3200, 0, 0); -- Chemical Reagent at Plant

INSERT INTO stock_serial_batches (inventory_id, serial_number, batch_number, expiry_date, status) VALUES
(4, 'HYD-CAT-2026-9921', NULL, NULL, 'available'),
(5, NULL, 'BATCH-SIBX-202610', '2027-10-15', 'available');

-- -----------------------------------------------------------------------------
-- 4. SUPPLIERS & PROCUREMENT
-- -----------------------------------------------------------------------------
INSERT INTO suppliers (vendor_code, vendor_name, contact_email, contact_phone, standard_lead_time_days, is_vmi_vendor) VALUES
('VEND-101', 'Hastings Deering (CAT OEM)', 'orders@hastingsdeering.com', '+1-800-555-0199', 5, 0),
('VEND-402', 'Metso Outotec', 'spares@metso.com', '+1-800-555-0402', 14, 0),
('VEND-880', 'Orica Mining Chemicals', 'supply@orica.com', '+1-800-555-0880', 7, 1);

INSERT INTO purchase_orders (po_number, supplier_id, site_id, status, urgency, requested_by, expected_delivery_date) VALUES
('PO-84910', 2, 2, 'partially_received', 'high', 'J. Miller (Plant Maintenance)', '2026-10-24 00:00:00'),
('PO-91022', 1, 1, 'issued', 'down_equipment_vop', 'M. Ross (Pit A Supervisor)', '2026-10-22 00:00:00');

INSERT INTO po_line_items (po_id, line_number, part_id, qty_ordered, qty_received, unit_price, line_status) VALUES
(1, 1, 3, 2, 0, 4850.00, 'OPEN'),
(2, 1, 1, 30, 0, 42.50, 'OPEN');
