#!/usr/bin/env python3
"""
Script para aplicar la migración 001 - Fundaciones
Ejecutar ANTES de iniciar el servidor actualizado
"""
import sqlite3
import shutil
from datetime import datetime
import os

DB = "mozo.db"
BACKUP_DIR = "backups"

def backup_db():
    """Crear backup antes de migrar"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_name = f"mozo_pre_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    shutil.copy2(DB, backup_path)
    print(f"✅ Backup creado: {backup_path}")
    return backup_path

def aplicar_migracion():
    """Aplicar migración 001"""
    print("🚀 Iniciando migración...")
    
    # Backup
    backup_path = backup_db()
    
    con = sqlite3.connect(DB)
    cur = con.cursor()
    
    try:
        # Habilitar foreign keys
        cur.execute("PRAGMA foreign_keys = ON")
        
        # 1. Agregar columnas de auditoría
        print("📝 Agregando columnas de auditoría...")
        tablas = ['users', 'tables', 'categories', 'products', 'order_items', 'notas_generales']
        
        for tabla in tablas:
            try:
                if tabla not in ['categories', 'products', 'order_items']:
                    cur.execute(f"ALTER TABLE {tabla} ADD COLUMN activo INTEGER DEFAULT 1")
            except sqlite3.OperationalError:
                pass
            
            try:
                cur.execute(f"ALTER TABLE {tabla} ADD COLUMN created_at TEXT DEFAULT (datetime('now'))")
            except sqlite3.OperationalError:
                pass
            
            try:
                cur.execute(f"ALTER TABLE {tabla} ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))")
            except sqlite3.OperationalError:
                pass
        
        # Orders
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN estado TEXT DEFAULT 'pendiente'")
        except sqlite3.OperationalError:
            pass
        
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))")
        except sqlite3.OperationalError:
            pass
        
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN descuento_total REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN subtotal REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN pagado INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        # 2. Crear nuevas tablas
        print("📦 Creando nuevas tablas...")
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS modifiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio_extra REAL DEFAULT 0,
            activo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS order_item_modifiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_item_id INTEGER NOT NULL,
            modifier_id INTEGER,
            modifier_nombre TEXT NOT NULL,
            precio_extra REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE,
            FOREIGN KEY (modifier_id) REFERENCES modifiers(id) ON DELETE SET NULL
        )
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS discounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('porcentaje', 'monto')),
            valor REAL NOT NULL CHECK(valor >= 0),
            motivo TEXT NOT NULL,
            aplicado_por TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            metodo TEXT NOT NULL CHECK(metodo IN ('efectivo', 'debito', 'credito', 'qr', 'transferencia')),
            monto REAL NOT NULL CHECK(monto >= 0),
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
        """)
        
        cur.execute("""
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
        )
        """)
        
        # 3. Crear índices
        print("🔍 Creando índices...")
        
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_users_rol ON users(rol)",
            "CREATE INDEX IF NOT EXISTS idx_users_activo ON users(activo)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_nombre ON categories(nombre)",
            "CREATE INDEX IF NOT EXISTS idx_categories_orden ON categories(orden)",
            "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)",
            "CREATE INDEX IF NOT EXISTS idx_products_nombre ON products(nombre)",
            "CREATE INDEX IF NOT EXISTS idx_products_activo ON products(activo)",
            "CREATE INDEX IF NOT EXISTS idx_orders_table ON orders(table_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_estado ON orders(estado)",
            "CREATE INDEX IF NOT EXISTS idx_orders_anulada ON orders(anulada)",
            "CREATE INDEX IF NOT EXISTS idx_orders_ts ON orders(ts)",
            "CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_modifiers_activo ON modifiers(activo)",
            "CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_payments_metodo ON payments(metodo)",
            "CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity, entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at)"
        ]
        
        for idx in indices:
            try:
                cur.execute(idx)
            except sqlite3.OperationalError as e:
                print(f"  ⚠️  {e}")
        
        # 4. Poblar modificadores de ejemplo
        print("📋 Creando modificadores de ejemplo...")
        modificadores = [
            ('Sin azúcar', 0),
            ('Extra shot café', 500),
            ('Leche deslactosada', 200),
            ('Con hielo', 0),
            ('Sin sal', 0),
            ('Extra queso', 300),
            ('Poco hielo', 0),
            ('Sin cafeína', 0)
        ]
        
        for nombre, precio in modificadores:
            try:
                cur.execute("INSERT INTO modifiers (nombre, precio_extra) VALUES (?, ?)", (nombre, precio))
            except sqlite3.IntegrityError:
                pass
        
        # 5. Actualizar estados existentes
        print("🔄 Actualizando datos existentes...")
        cur.execute("UPDATE orders SET estado = 'pendiente' WHERE estado IS NULL OR estado = ''")
        cur.execute("UPDATE orders SET subtotal = total WHERE subtotal = 0")
        
        # Commit
        con.commit()
        print("✅ Migración completada exitosamente")
        print(f"📦 Backup disponible en: {backup_path}")
        print("\n🎯 Próximos pasos:")
        print("   1. Reemplaza app.py con la nueva versión")
        print("   2. Reinicia el servidor")
        print("   3. Prueba las nuevas funcionalidades")
        
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        print(f"💾 Puedes restaurar desde: {backup_path}")
        con.rollback()
        raise
    
    finally:
        con.close()

if __name__ == "__main__":
    print("=" * 60)
    print("MIGRACIÓN 001 - FUNDACIONES")
    print("El Café de los Pinos")
    print("=" * 60)
    print()
    
    if not os.path.exists(DB):
        print(f"❌ No se encontró la base de datos: {DB}")
        print("   Asegúrate de estar en la carpeta correcta")
        exit(1)
    
    respuesta = input("¿Continuar con la migración? (s/n): ")
    if respuesta.lower() != 's':
        print("❌ Migración cancelada")
        exit(0)
    
    aplicar_migracion()
    print("\n✅ ¡Todo listo!")