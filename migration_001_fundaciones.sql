-- ========================================
-- MIGRACIÓN 001: FUNDACIONES
-- Soft-delete, timestamps, índices, restricciones
-- ========================================

-- 1. AGREGAR COLUMNAS DE AUDITORÍA A TODAS LAS TABLAS
-- users
ALTER TABLE users ADD COLUMN activo INTEGER DEFAULT 1;
ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT (datetime('now'));
ALTER TABLE users ADD COLUMN updated_at TEXT DEFAULT (datetime('now'));

-- tables
ALTER TABLE tables ADD COLUMN activo INTEGER DEFAULT 1;
ALTER TABLE tables ADD COLUMN created_at TEXT DEFAULT (datetime('now'));
ALTER TABLE tables ADD COLUMN updated_at TEXT DEFAULT (datetime('now'));

-- categories (ya tiene activo implícito, agregamos timestamps)
ALTER TABLE categories ADD COLUMN created_at TEXT DEFAULT (datetime('now'));
ALTER TABLE categories ADD COLUMN updated_at TEXT DEFAULT (datetime('now'));

-- products (ya tiene activo, agregamos timestamps)
ALTER TABLE products ADD COLUMN created_at TEXT DEFAULT (datetime('now'));
ALTER TABLE products ADD COLUMN updated_at TEXT DEFAULT (datetime('now'));

-- orders (ya tiene ts, agregamos estado y updated_at)
ALTER TABLE orders ADD COLUMN estado TEXT DEFAULT 'pendiente';
ALTER TABLE orders ADD COLUMN updated_at TEXT DEFAULT (datetime('now'));

-- order_items
ALTER TABLE order_items ADD COLUMN created_at TEXT DEFAULT (datetime('now'));
ALTER TABLE order_items ADD COLUMN updated_at TEXT DEFAULT (datetime('now'));

-- notas_generales (ya tiene ts)
ALTER TABLE notas_generales ADD COLUMN activo INTEGER DEFAULT 1;
ALTER TABLE notas_generales ADD COLUMN updated_at TEXT DEFAULT (datetime('now'));

-- 2. CREAR TABLA DE MODIFICADORES
CREATE TABLE IF NOT EXISTS modifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    precio_extra REAL DEFAULT 0,
    activo INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 3. CREAR TABLA DE MODIFICADORES POR ITEM
CREATE TABLE IF NOT EXISTS order_item_modifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_item_id INTEGER NOT NULL,
    modifier_id INTEGER,
    modifier_nombre TEXT,
    precio_extra REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE,
    FOREIGN KEY (modifier_id) REFERENCES modifiers(id) ON DELETE SET NULL
);

-- 4. CREAR TABLA DE DESCUENTOS
CREATE TABLE IF NOT EXISTS discounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    tipo TEXT NOT NULL CHECK(tipo IN ('porcentaje', 'monto')),
    valor REAL NOT NULL CHECK(valor >= 0),
    motivo TEXT NOT NULL,
    aplicado_por TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

-- 5. CREAR TABLA DE PAGOS
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    metodo TEXT NOT NULL CHECK(metodo IN ('efectivo', 'debito', 'credito', 'qr', 'transferencia')),
    monto REAL NOT NULL CHECK(monto >= 0),
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

-- 6. CREAR TABLA DE AUDITORÍA
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    user_nombre TEXT,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id INTEGER,
    data_json TEXT,
    ip TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 7. AGREGAR COLUMNAS EXTRAS A ORDERS
ALTER TABLE orders ADD COLUMN descuento_total REAL DEFAULT 0;
ALTER TABLE orders ADD COLUMN subtotal REAL DEFAULT 0;
ALTER TABLE orders ADD COLUMN pagado INTEGER DEFAULT 0;

-- 8. CREAR ÍNDICES PARA PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_users_rol ON users(rol);
CREATE INDEX IF NOT EXISTS idx_users_activo ON users(activo);

CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_nombre ON categories(nombre);
CREATE INDEX IF NOT EXISTS idx_categories_orden ON categories(orden);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_nombre ON products(nombre);
CREATE INDEX IF NOT EXISTS idx_products_activo ON products(activo);

CREATE INDEX IF NOT EXISTS idx_orders_table ON orders(table_id);
CREATE INDEX IF NOT EXISTS idx_orders_estado ON orders(estado);
CREATE INDEX IF NOT EXISTS idx_orders_anulada ON orders(anulada);
CREATE INDEX IF NOT EXISTS idx_orders_ts ON orders(ts);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(DATE(ts));

CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);

CREATE INDEX IF NOT EXISTS idx_modifiers_activo ON modifiers(activo);

CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_metodo ON payments(metodo);

CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

-- 9. AGREGAR RESTRICCIONES CHECK (en tablas nuevas, las viejas ya están creadas)
-- Para products (si pudieras recrear la tabla, pero SQLite no soporta ALTER con CHECK)
-- Lo manejaremos en el backend

-- 10. POBLAR MODIFICADORES DE EJEMPLO
INSERT OR IGNORE INTO modifiers (nombre, precio_extra) VALUES
    ('Sin azúcar', 0),
    ('Extra shot café', 500),
    ('Leche deslactosada', 200),
    ('Con hielo', 0),
    ('Sin sal', 0),
    ('Extra queso', 300);

-- 11. ACTUALIZAR ESTADOS DE PEDIDOS EXISTENTES
UPDATE orders SET estado = 'pendiente' WHERE estado IS NULL;

-- FIN MIGRACIÓN 001