# app.py - VERSIÓN MEJORADA CON FUNDACIONES
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import sqlite3, json, os, io, csv, shutil, socket
from pathlib import Path

DB = "mozo.db"
BACKUP_DIR = "backups"
ADMIN_PIN = "1234"  # Cambia esto por tu PIN deseado

app = FastAPI(title="El Café de los Pinos")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --- Función para obtener IP local ---
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# --- Endpoint para obtener IP ---
@app.get("/api/server-info")
def server_info():
    local_ip = get_local_ip()
    return {
        "ip": local_ip,
        "port": 8000,
        "url_local": f"http://localhost:8000",
        "url_lan": f"http://{local_ip}:8000"
    }

# --- Verificar PIN de Admin ---
@app.post("/api/admin/verify-pin")
def verify_admin_pin(payload: dict = Body(...)):
    pin = payload.get("pin", "")
    if pin == ADMIN_PIN:
        return {"ok": True, "token": "admin_verified"}
    raise HTTPException(401, "PIN incorrecto")


# --- DB helpers ---
def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def log_audit(user_id=None, user_nombre=None, action=None, entity=None, entity_id=None, data=None, ip=None):
    """Registrar acción en audit_log"""
    try:
        con = db()
        cur = con.cursor()
        cur.execute("""INSERT INTO audit_log(user_id, user_nombre, action, entity, entity_id, data_json, ip)
                       VALUES(?,?,?,?,?,?,?)""",
                    (user_id, user_nombre, action, entity, entity_id, json.dumps(data) if data else None, ip))
        con.commit()
        con.close()
    except Exception as e:
        print(f"Error logging audit: {e}")

def init_db():
    con = db(); cur = con.cursor()
    
    # Crear tablas base
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        rol TEXT NOT NULL,
        pin TEXT,
        activo INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    
    CREATE TABLE IF NOT EXISTS tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        activo INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        orden INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        precio REAL NOT NULL CHECK(precio >= 0),
        category_id INTEGER,
        activo INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
    );
    
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_id INTEGER,
        user_id INTEGER,
        mozo_nombre TEXT,
        subtotal REAL DEFAULT 0,
        descuento_total REAL DEFAULT 0,
        total REAL DEFAULT 0,
        estado TEXT DEFAULT 'pendiente' CHECK(estado IN ('pendiente', 'listo', 'cobrado')),
        anulada INTEGER DEFAULT 0,
        pagado INTEGER DEFAULT 0,
        ts TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (table_id) REFERENCES tables(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        product_nombre TEXT NOT NULL,
        product_precio REAL DEFAULT 0,
        cantidad INTEGER NOT NULL CHECK(cantidad > 0),
        notas TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
    );
    
    CREATE TABLE IF NOT EXISTS modifiers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        precio_extra REAL DEFAULT 0,
        activo INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    
    CREATE TABLE IF NOT EXISTS order_item_modifiers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_item_id INTEGER NOT NULL,
        modifier_id INTEGER,
        modifier_nombre TEXT NOT NULL,
        precio_extra REAL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE,
        FOREIGN KEY (modifier_id) REFERENCES modifiers(id) ON DELETE SET NULL
    );
    
    CREATE TABLE IF NOT EXISTS discounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('porcentaje', 'monto')),
        valor REAL NOT NULL CHECK(valor >= 0),
        motivo TEXT NOT NULL,
        aplicado_por TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        metodo TEXT NOT NULL CHECK(metodo IN ('efectivo', 'debito', 'credito', 'qr', 'transferencia')),
        monto REAL NOT NULL CHECK(monto >= 0),
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
    
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
    
    CREATE TABLE IF NOT EXISTS notas_generales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contenido TEXT NOT NULL,
        activo INTEGER DEFAULT 1,
        ts TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    """)
    
    # Crear índices
    cur.executescript("""
    CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
    CREATE INDEX IF NOT EXISTS idx_products_nombre ON products(nombre);
    CREATE INDEX IF NOT EXISTS idx_products_activo ON products(activo);
    CREATE INDEX IF NOT EXISTS idx_orders_estado ON orders(estado);
    CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(DATE(ts));
    CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity, entity_id);
    """)
    
    con.commit()
    con.close()

init_db()


# --- Pydantic Models ---
class ModifierIn(BaseModel):
    modifier_id: Optional[int] = None
    nombre: Optional[str] = None

class ItemIn(BaseModel):
    product_id: Optional[int] = None
    cantidad: int = Field(gt=0)
    notas: Optional[str] = None
    modifiers: List[ModifierIn] = []

class OrderIn(BaseModel):
    table_id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    items: List[ItemIn]

class ProductIn(BaseModel):
    nombre: str
    precio: float = Field(ge=0)
    category_id: Optional[int] = None
    
    @validator('nombre')
    def nombre_no_vacio(cls, v):
        if not v or not v.strip():
            raise ValueError('El nombre no puede estar vacío')
        return v.strip()

class CategoryIn(BaseModel):
    nombre: str
    orden: int = 0
    
    @validator('nombre')
    def nombre_no_vacio(cls, v):
        if not v or not v.strip():
            raise ValueError('El nombre no puede estar vacío')
        return v.strip()

class ModifierCreate(BaseModel):
    nombre: str
    precio_extra: float = 0

class DiscountIn(BaseModel):
    order_id: int
    tipo: str = Field(pattern='^(porcentaje|monto)$')
    valor: float = Field(ge=0)
    motivo: str
    aplicado_por: Optional[str] = None

class PaymentIn(BaseModel):
    order_id: int
    metodo: str = Field(pattern='^(efectivo|debito|credito|qr|transferencia)$')
    monto: float = Field(ge=0)

# --- WebSocket Hub ---
class Hub:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {"kitchen": []}
    async def connect(self, ws: WebSocket, room: str):
        await ws.accept()
        self.rooms[room].append(ws)
    def remove(self, ws: WebSocket, room: str):
        if ws in self.rooms[room]:
            self.rooms[room].remove(ws)
    async def broadcast(self, room: str, message: dict):
        dead = []
        for ws in list(self.rooms[room]):
            try:
                await ws.send_text(json.dumps(message))
            except:
                dead.append(ws)
        for d in dead:
            self.remove(d, room)

hub = Hub()

# --- Helper: Calcular totales ---
def calcular_totales_order(order_id: int, con=None):
    """Recalcula subtotal, descuentos y total de una orden"""
    close_con = False
    if not con:
        con = db()
        close_con = True
    
    cur = con.cursor()
    
    # Calcular subtotal (items + modificadores)
    items = cur.execute("""
        SELECT oi.product_precio * oi.cantidad as item_total,
               (SELECT COALESCE(SUM(oim.precio_extra), 0) 
                FROM order_item_modifiers oim 
                WHERE oim.order_item_id = oi.id) * oi.cantidad as mods_total
        FROM order_items oi
        WHERE oi.order_id = ?
    """, (order_id,)).fetchall()
    
    subtotal = sum(row['item_total'] + row['mods_total'] for row in items)
    
    # Calcular descuentos
    descuentos = cur.execute("""
        SELECT tipo, valor FROM discounts WHERE order_id = ?
    """, (order_id,)).fetchall()
    
    descuento_total = 0
    for desc in descuentos:
        if desc['tipo'] == 'porcentaje':
            descuento_total += subtotal * (desc['valor'] / 100)
        else:
            descuento_total += desc['valor']
    
    total = subtotal - descuento_total
    if total < 0:
        total = 0
    
    cur.execute("""
        UPDATE orders 
        SET subtotal = ?, descuento_total = ?, total = ?, updated_at = datetime('now')
        WHERE id = ?
    """, (subtotal, descuento_total, total, order_id))
    
    if close_con:
        con.commit()
        con.close()
    
    return {"subtotal": subtotal, "descuento_total": descuento_total, "total": total}

# --- API ENDPOINTS ---

# PRODUCTOS
@app.get("/products")
def products(category_id: Optional[int] = None, search: Optional[str] = None):
    con = db()
    cur = con.cursor()
    
    query = """SELECT p.id, p.nombre, p.precio, p.category_id, c.nombre as categoria
               FROM products p 
               LEFT JOIN categories c ON c.id = p.category_id
               WHERE p.activo=1"""
    params = []
    
    if category_id:
        query += " AND p.category_id = ?"
        params.append(category_id)
    
    if search:
        query += " AND p.nombre LIKE ?"
        params.append(f"%{search}%")
    
    query += " ORDER BY c.orden, c.nombre, p.nombre"
    
    rows = cur.execute(query, params).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.on_event("startup")
def on_startup():
    print("🚀 Iniciando El Café de los Pinos...")
    local_ip = get_local_ip()
    print(f"📡 IP Local: {local_ip}")
    print(f"🌐 Acceso local: http://localhost:8000")
    print(f"📱 Acceso LAN: http://{local_ip}:8000")
    backup_database()
    print("✅ Sistema listo")

@app.post("/orders")
async def create_order(payload: OrderIn, request: Request):
    if not payload.items:
        raise HTTPException(400, "Pedido sin items")
    
    con = db()
    cur = con.cursor()
    
    # Crear orden
    cur.execute("""INSERT INTO orders(table_id, user_id, mozo_nombre, estado)
                   VALUES(?,?,?,'pendiente')""",
                (payload.table_id, payload.user_id, payload.user_name))
    order_id = cur.lastrowid
    
    # Agregar items
    for it in payload.items:
        if it.product_id:
            prod = cur.execute("SELECT nombre, precio FROM products WHERE id=?", (it.product_id,)).fetchone()
            if prod:
                nombre = prod["nombre"]
                precio = prod["precio"]
            else:
                nombre = "Producto desconocido"
                precio = 0
        else:
            nombre = "Pedido libre"
            precio = 0
        
        cur.execute("""INSERT INTO order_items(order_id, product_id, product_nombre, product_precio, cantidad, notas)
                       VALUES(?,?,?,?,?,?)""",
                    (order_id, it.product_id, nombre, precio, it.cantidad, it.notas))
        item_id = cur.lastrowid
        
        # Agregar modificadores
        for mod in it.modifiers:
            if mod.modifier_id:
                mod_data = cur.execute("SELECT nombre, precio_extra FROM modifiers WHERE id=?", (mod.modifier_id,)).fetchone()
                if mod_data:
                    cur.execute("""INSERT INTO order_item_modifiers(order_item_id, modifier_id, modifier_nombre, precio_extra)
                                   VALUES(?,?,?,?)""",
                                (item_id, mod.modifier_id, mod_data["nombre"], mod_data["precio_extra"]))
            elif mod.nombre:
                cur.execute("""INSERT INTO order_item_modifiers(order_item_id, modifier_nombre, precio_extra)
                               VALUES(?,?,?)""",
                            (item_id, mod.nombre, 0))
    
    # Calcular totales
    calcular_totales_order(order_id, con)
    
    log_audit(user_nombre=payload.user_name, action="CREATE", entity="orders", entity_id=order_id,
              data={"table_id": payload.table_id}, ip=request.client.host if request.client else None)
    
    con.commit()
    con.close()
    
    await hub.broadcast("kitchen", {"type": "new_order", "order_id": order_id})
    return {"ok": True, "order_id": order_id}

@app.get("/orders")
def list_orders(estado: Optional[str] = None, anuladas: int = 0):
    con = db()
    cur = con.cursor()
    
    query = """SELECT o.id, o.table_id, o.user_id, o.mozo_nombre, o.subtotal, o.descuento_total,
                      o.total, o.estado, o.anulada, o.pagado, o.ts, o.updated_at,
                      t.nombre AS mesa, u.nombre AS mozo
               FROM orders o
               LEFT JOIN tables t ON t.id=o.table_id
               LEFT JOIN users u ON u.id=o.user_id
               WHERE o.anulada=?"""
    params = [anuladas]
    
    if estado:
        query += " AND o.estado=?"
        params.append(estado)
    
    query += " ORDER BY o.id DESC"
    
    rows = cur.execute(query, params).fetchall()
    data = []
    
    for r in rows:
        items_query = """
            SELECT oi.id, oi.product_nombre as nombre, oi.product_precio as precio,
                   oi.cantidad, oi.notas
            FROM order_items oi
            WHERE oi.order_id=?"""
        items = cur.execute(items_query, (r["id"],)).fetchall()
        
        items_con_mods = []
        for it in items:
            mods = cur.execute("""
                SELECT modifier_nombre, precio_extra 
                FROM order_item_modifiers 
                WHERE order_item_id=?
            """, (it["id"],)).fetchall()
            
            item_dict = dict(it)
            item_dict["modifiers"] = [dict(m) for m in mods]
            items_con_mods.append(item_dict)
        
        mozo_final = r["mozo_nombre"] or (r["mozo"] if r["mozo"] else str(r["user_id"] or ""))
        order_dict = dict(r)
        order_dict["mozo"] = mozo_final
        order_dict["items"] = items_con_mods
        data.append(order_dict)
    
    con.close()
    return data

@app.put("/orders/{order_id}/estado")
async def update_order_estado(order_id: int, payload: dict = Body(...), request: Request = None):
    estado = payload.get("estado")
    if estado not in ["pendiente", "listo", "cobrado"]:
        raise HTTPException(400, "Estado inválido")
    
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE orders SET estado=?, updated_at=datetime('now') WHERE id=?", (estado, order_id))
    con.commit()
    
    log_audit(action="UPDATE_ESTADO", entity="orders", entity_id=order_id, data={"estado": estado},
              ip=request.client.host if request.client else None)
    
    con.close()
    await hub.broadcast("kitchen", {"type": "order_updated", "order_id": order_id})
    return {"ok": True, "estado": estado}

@app.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE orders SET anulada=1, updated_at=datetime('now') WHERE id=?", (order_id,))
    con.commit()
    
    log_audit(action="CANCEL", entity="orders", entity_id=order_id, ip=request.client.host if request.client else None)
    
    con.close()
    await hub.broadcast("kitchen", {"type": "order_cancelled", "order_id": order_id})
    return {"ok": True}

@app.get("/categories")
def categories():
    con = db()
    rows = con.execute("SELECT id, nombre, orden FROM categories ORDER BY orden, nombre").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.post("/categories")
def create_category(payload: CategoryIn, request: Request):
    con = db()
    cur = con.cursor()
    
    try:
        cur.execute("INSERT INTO categories(nombre, orden) VALUES(?,?)", (payload.nombre, payload.orden))
        cid = cur.lastrowid
        con.commit()
        
        log_audit(action="CREATE", entity="categories", entity_id=cid, data=payload.dict(), 
                  ip=request.client.host if request.client else None)
        
        con.close()
        return {"ok": True, "id": cid}
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(400, "Ya existe una categoría con ese nombre")

@app.delete("/categories/{category_id}")
def delete_category(category_id: int, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM categories WHERE id=?", (category_id,))
    con.commit()
    
    log_audit(action="DELETE", entity="categories", entity_id=category_id, ip=request.client.host if request.client else None)
    
    con.close()
    return {"ok": True}

@app.get("/modifiers")
def get_modifiers():
    con = db()
    rows = con.execute("SELECT id, nombre, precio_extra FROM modifiers WHERE activo=1 ORDER BY nombre").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.post("/modifiers")
def create_modifier(payload: ModifierCreate, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("INSERT INTO modifiers(nombre, precio_extra) VALUES(?,?)", 
                (payload.nombre, payload.precio_extra))
    mid = cur.lastrowid
    con.commit()
    
    log_audit(action="CREATE", entity="modifiers", entity_id=mid, data=payload.dict(), 
              ip=request.client.host if request.client else None)
    
    con.close()
    return {"ok": True, "id": mid}

@app.delete("/modifiers/{modifier_id}")
def delete_modifier(modifier_id: int, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE modifiers SET activo=0, updated_at=datetime('now') WHERE id=?", (modifier_id,))
    con.commit()
    
    log_audit(action="DELETE", entity="modifiers", entity_id=modifier_id, ip=request.client.host if request.client else None)
    
    con.close()
    return {"ok": True}

@app.get("/tables")
def tables():
    con = db()
    rows = con.execute("SELECT id, nombre FROM tables WHERE activo=1 ORDER BY id").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/users")
def users(rol: Optional[str] = None):
    con = db()
    if rol:
        rows = con.execute("SELECT id, nombre, rol FROM users WHERE rol=? AND activo=1", (rol,)).fetchall()
    else:
        rows = con.execute("SELECT id, nombre, rol FROM users WHERE activo=1").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/notas")
def get_notas():
    con = db()
    rows = con.execute("SELECT id, contenido, ts FROM notas_generales WHERE activo=1 ORDER BY id DESC LIMIT 50").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.post("/notas")
async def create_nota(payload: dict = Body(...), request: Request = None):
    con = db()
    cur = con.cursor()
    contenido = payload.get("contenido", "")
    cur.execute("INSERT INTO notas_generales(contenido) VALUES(?)", (contenido,))
    nid = cur.lastrowid
    con.commit()
    
    log_audit(action="CREATE", entity="notas", entity_id=nid, data={"contenido": contenido},
              ip=request.client.host if request.client else None)
    
    con.close()
    await hub.broadcast("kitchen", {"type": "new_nota", "id": nid})
    return {"ok": True, "id": nid}

@app.delete("/notas/{nota_id}")
async def delete_nota(nota_id: int, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE notas_generales SET activo=0, updated_at=datetime('now') WHERE id=?", (nota_id,))
    con.commit()
    
    log_audit(action="DELETE", entity="notas", entity_id=nota_id, ip=request.client.host if request.client else None)
    
    con.close()
    await hub.broadcast("kitchen", {"type": "nota_deleted", "id": nota_id})
    return {"ok": True}

@app.get("/stats/today")
def stats_today():
    con = db()
    today = datetime.utcnow().date().isoformat()
    
    total_vendido = con.execute("""
        SELECT SUM(total) as total FROM orders 
        WHERE DATE(ts) = ? AND anulada=0
    """, (today,)).fetchone()["total"] or 0
    
    total_comandas = con.execute("""
        SELECT COUNT(*) as count FROM orders 
        WHERE DATE(ts) = ? AND anulada=0
    """, (today,)).fetchone()["count"]
    
    por_mesa = con.execute("""
        SELECT t.nombre as mesa, SUM(o.total) as total, COUNT(*) as comandas
        FROM orders o
        LEFT JOIN tables t ON t.id=o.table_id
        WHERE DATE(o.ts) = ? AND o.anulada=0
        GROUP BY o.table_id
        ORDER BY total DESC
    """, (today,)).fetchall()
    
    por_mozo = con.execute("""
        SELECT mozo_nombre as mozo, SUM(total) as total, COUNT(*) as comandas
        FROM orders
        WHERE DATE(ts) = ? AND anulada=0 AND mozo_nombre IS NOT NULL
        GROUP BY mozo_nombre
        ORDER BY total DESC
    """, (today,)).fetchall()
    
    top_productos = con.execute("""
        SELECT oi.product_nombre, SUM(oi.cantidad) as vendidos, 
               SUM(oi.product_precio * oi.cantidad) as ingresos
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE DATE(o.ts) = ? AND o.anulada=0
        GROUP BY oi.product_nombre
        ORDER BY vendidos DESC
        LIMIT 10
    """, (today,)).fetchall()
    
    por_estado = con.execute("""
        SELECT estado, COUNT(*) as count
        FROM orders
        WHERE DATE(ts) = ? AND anulada=0
        GROUP BY estado
    """, (today,)).fetchall()
    
    con.close()
    return {
        "fecha": today,
        "total_vendido": total_vendido,
        "total_comandas": total_comandas,
        "por_mesa": [dict(r) for r in por_mesa],
        "por_mozo": [dict(r) for r in por_mozo],
        "top_productos": [dict(r) for r in top_productos],
        "por_estado": [dict(r) for r in por_estado]
    }

@app.get("/export/orders")
def export_orders(fecha: Optional[str] = None):
    con = db()
    if fecha:
        rows = con.execute("""
            SELECT o.id, o.ts, t.nombre as mesa, o.mozo_nombre, o.subtotal, 
                   o.descuento_total, o.total, o.estado, o.anulada
            FROM orders o
            LEFT JOIN tables t ON t.id=o.table_id
            WHERE DATE(o.ts) = ?
            ORDER BY o.id
        """, (fecha,)).fetchall()
    else:
        today = datetime.utcnow().date().isoformat()
        rows = con.execute("""
            SELECT o.id, o.ts, t.nombre as mesa, o.mozo_nombre, o.subtotal,
                   o.descuento_total, o.total, o.estado, o.anulada
            FROM orders o
            LEFT JOIN tables t ON t.id=o.table_id
            WHERE DATE(o.ts) = ?
            ORDER BY o.id
        """, (today,)).fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Fecha/Hora', 'Mesa', 'Mozo', 'Subtotal', 'Descuento', 'Total', 'Estado', 'Anulada'])
    
    for r in rows:
        writer.writerow([
            r['id'], r['ts'], r['mesa'], r['mozo_nombre'], 
            r['subtotal'], r['descuento_total'], r['total'], 
            r['estado'], 'SI' if r['anulada'] else 'NO'
        ])
    
    con.close()
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=comandas_{datetime.utcnow().date()}.csv"}
    )

@app.get("/audit")
def get_audit_log(limit: int = 100):
    con = db()
    rows = con.execute("""
        SELECT * FROM audit_log 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def backup_database():
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_name = f"mozo_backup_{datetime.utcnow().date()}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        if not os.path.exists(backup_path):
            shutil.copy2(DB, backup_path)
            print(f"Backup creado: {backup_name}")
            
            for f in os.listdir(BACKUP_DIR):
                if f.startswith("mozo_backup_"):
                    file_path = os.path.join(BACKUP_DIR, f)
                    if os.path.getctime(file_path) < (datetime.now() - timedelta(days=7)).timestamp():
                        os.remove(file_path)
    except Exception as e:
        print(f"Error en backup: {e}")

@app.on_event("startup")
def on_startup():
    print("Iniciando El Café de los Pinos...")
    local_ip = get_local_ip()
    print(f"IP Local: {local_ip}")
    print(f"Acceso local: http://localhost:8000")
    print(f"Acceso LAN: http://{local_ip}:8000")
    backup_database()
    print("Sistema listo")

@app.websocket("/ws/kitchen")
async def ws_kitchen(ws: WebSocket):
    await hub.connect(ws, "kitchen")
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.remove(ws, "kitchen")

@app.middleware("http")
async def add_nocache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

STATIC_DIR = "."
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def root():
    return {
        "ok": True, 
        "app": "El Café de los Pinos",
        "version": "3.0",
        "endpoints": {
            "web": "/static/index.html",
            "docs": "/docs",
            "mozo": "/static/mozo.html",
            "cocina": "/static/cocina.html",
            "admin": "/static/admin.html"
        }
    }

@app.post("/products")
def create_product(payload: ProductIn, request: Request):
    con = db()
    cur = con.cursor()
    
    # Validar duplicado
    existe = cur.execute("""
        SELECT id FROM products 
        WHERE nombre = ? AND category_id IS ? AND activo = 1
    """, (payload.nombre, payload.category_id)).fetchone()
    
    if existe:
        con.close()
        raise HTTPException(400, "Ya existe un producto con ese nombre en esta categoría")
    
    cur.execute("""INSERT INTO products(nombre, precio, category_id) VALUES(?,?,?)""",
                (payload.nombre, payload.precio, payload.category_id))
    pid = cur.lastrowid
    con.commit()
    
    log_audit(action="CREATE", entity="products", entity_id=pid, 
              data=payload.dict(), ip=request.client.host if request.client else None)
    
    con.close()
    return {"ok": True, "id": pid}

@app.delete("/products/{product_id}")
def delete_product(product_id: int, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE products SET activo=0, updated_at=datetime('now') WHERE id=?", (product_id,))
    con.commit()
    
    log_audit(action="DELETE", entity="products", entity_id=product_id, ip=request.client.host if request.client else None)
    
    con.close()
    return {"ok": True}

# CATEGORÍAS
@app.get("/categories")
def categories():
    con = db()
    rows = con.execute("SELECT id, nombre, orden FROM categories ORDER BY orden, nombre").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.post("/categories")
def create_category(payload: CategoryIn, request: Request):
    con = db()
    cur = con.cursor()
    
    try:
        cur.execute("INSERT INTO categories(nombre, orden) VALUES(?,?)", (payload.nombre, payload.orden))
        cid = cur.lastrowid
        con.commit()
        
        log_audit(action="CREATE", entity="categories", entity_id=cid, data=payload.dict(), 
                  ip=request.client.host if request.client else None)
        
        con.close()
        return {"ok": True, "id": cid}
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(400, "Ya existe una categoría con ese nombre")

@app.delete("/categories/{category_id}")
def delete_category(category_id: int, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM categories WHERE id=?", (category_id,))
    con.commit()
    
    log_audit(action="DELETE", entity="categories", entity_id=category_id, ip=request.client.host if request.client else None)
    
    con.close()
    return {"ok": True}

# MODIFICADORES
@app.get("/modifiers")
def get_modifiers():
    con = db()
    rows = con.execute("SELECT id, nombre, precio_extra FROM modifiers WHERE activo=1 ORDER BY nombre").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.post("/modifiers")
def create_modifier(payload: ModifierCreate, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("INSERT INTO modifiers(nombre, precio_extra) VALUES(?,?)", 
                (payload.nombre, payload.precio_extra))
    mid = cur.lastrowid
    con.commit()
    
    log_audit(action="CREATE", entity="modifiers", entity_id=mid, data=payload.dict(), 
              ip=request.client.host if request.client else None)
    
    con.close()
    return {"ok": True, "id": mid}

@app.delete("/modifiers/{modifier_id}")
def delete_modifier(modifier_id: int, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE modifiers SET activo=0, updated_at=datetime('now') WHERE id=?", (modifier_id,))
    con.commit()
    
    log_audit(action="DELETE", entity="modifiers", entity_id=modifier_id, ip=request.client.host if request.client else None)
    
    con.close()
    return {"ok": True}

# COMANDAS
@app.post("/orders")
async def create_order(payload: OrderIn, request: Request):
    if not payload.items:
        raise HTTPException(400, "Pedido sin items")
    
    con = db()
    cur = con.cursor()
    
    # Crear orden
    cur.execute("""INSERT INTO orders(table_id, user_id, mozo_nombre, estado)
                   VALUES(?,?,?,'pendiente')""",
                (payload.table_id, payload.user_id, payload.user_name))
    order_id = cur.lastrowid
    
    # Agregar items
    for it in payload.items:
        if it.product_id:
            prod = cur.execute("SELECT nombre, precio FROM products WHERE id=?", (it.product_id,)).fetchone()
            if prod:
                nombre = prod["nombre"]
                precio = prod["precio"]
            else:
                nombre = "Producto desconocido"
                precio = 0
        else:
            nombre = "Pedido libre"
            precio = 0
        
        cur.execute("""INSERT INTO order_items(order_id, product_id, product_nombre, product_precio, cantidad, notas)
                       VALUES(?,?,?,?,?,?)""",
                    (order_id, it.product_id, nombre, precio, it.cantidad, it.notas))
        item_id = cur.lastrowid
        
        # Agregar modificadores
        for mod in it.modifiers:
            if mod.modifier_id:
                mod_data = cur.execute("SELECT nombre, precio_extra FROM modifiers WHERE id=?", (mod.modifier_id,)).fetchone()
                if mod_data:
                    cur.execute("""INSERT INTO order_item_modifiers(order_item_id, modifier_id, modifier_nombre, precio_extra)
                                   VALUES(?,?,?,?)""",
                                (item_id, mod.modifier_id, mod_data["nombre"], mod_data["precio_extra"]))
            elif mod.nombre:
                cur.execute("""INSERT INTO order_item_modifiers(order_item_id, modifier_nombre, precio_extra)
                               VALUES(?,?,?)""",
                            (item_id, mod.nombre, 0))
    
    # Calcular totales
    calcular_totales_order(order_id, con)
    
    log_audit(user_nombre=payload.user_name, action="CREATE", entity="orders", entity_id=order_id,
              data={"table_id": payload.table_id}, ip=request.client.host if request.client else None)
    
    con.commit()
    con.close()
    
    await hub.broadcast("kitchen", {"type": "new_order", "order_id": order_id})
    return {"ok": True, "order_id": order_id}

@app.get("/orders")
def list_orders(estado: Optional[str] = None, anuladas: int = 0):
    con = db()
    cur = con.cursor()
    
    query = """SELECT o.id, o.table_id, o.user_id, o.mozo_nombre, o.subtotal, o.descuento_total,
                      o.total, o.estado, o.anulada, o.pagado, o.ts, o.updated_at,
                      t.nombre AS mesa, u.nombre AS mozo
               FROM orders o
               LEFT JOIN tables t ON t.id=o.table_id
               LEFT JOIN users u ON u.id=o.user_id
               WHERE o.anulada=?"""
    params = [anuladas]
    
    if estado:
        query += " AND o.estado=?"
        params.append(estado)
    
    query += " ORDER BY o.id DESC"
    
    rows = cur.execute(query, params).fetchall()
    data = []
    
    for r in rows:
        items_query = """
            SELECT oi.id, oi.product_nombre as nombre, oi.product_precio as precio,
                   oi.cantidad, oi.notas
            FROM order_items oi
            WHERE oi.order_id=?"""
        items = cur.execute(items_query, (r["id"],)).fetchall()
        
        items_con_mods = []
        for it in items:
            mods = cur.execute("""
                SELECT modifier_nombre, precio_extra 
                FROM order_item_modifiers 
                WHERE order_item_id=?
            """, (it["id"],)).fetchall()
            
            item_dict = dict(it)
            item_dict["modifiers"] = [dict(m) for m in mods]
            items_con_mods.append(item_dict)
        
        mozo_final = r["mozo_nombre"] or (r["mozo"] if r["mozo"] else str(r["user_id"] or ""))
        order_dict = dict(r)
        order_dict["mozo"] = mozo_final
        order_dict["items"] = items_con_mods
        data.append(order_dict)
    
    con.close()
    return data

@app.put("/orders/{order_id}/estado")
async def update_order_estado(order_id: int, payload: dict = Body(...), request: Request = None):
    """Cambiar estado de una orden"""
    estado = payload.get("estado")
    if estado not in ["pendiente", "listo", "cobrado"]:
        raise HTTPException(400, "Estado inválido")
    
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE orders SET estado=?, updated_at=datetime('now') WHERE id=?", (estado, order_id))
    con.commit()
    
    log_audit(action="UPDATE_ESTADO", entity="orders", entity_id=order_id, data={"estado": estado},
              ip=request.client.host if request.client else None)
    
    con.close()
    await hub.broadcast("kitchen", {"type": "order_updated", "order_id": order_id})
    return {"ok": True, "estado": estado}

@app.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE orders SET anulada=1, updated_at=datetime('now') WHERE id=?", (order_id,))
    con.commit()
    
    log_audit(action="CANCEL", entity="orders", entity_id=order_id, ip=request.client.host if request.client else None)
    
    con.close()
    await hub.broadcast("kitchen", {"type": "order_cancelled", "order_id": order_id})
    return {"ok": True}

# DESCUENTOS
@app.post("/discounts")
async def create_discount(payload: DiscountIn, request: Request):
    con = db()
    cur = con.cursor()
    
    cur.execute("""INSERT INTO discounts(order_id, tipo, valor, motivo, aplicado_por)
                   VALUES(?,?,?,?,?)""",
                (payload.order_id, payload.tipo, payload.valor, payload.motivo, payload.aplicado_por))
    did = cur.lastrowid
    
    # Recalcular totales
    calcular_totales_order(payload.order_id, con)
    
    log_audit(user_nombre=payload.aplicado_por, action="CREATE", entity="discounts", 
              entity_id=did, data=payload.dict(), ip=request.client.host if request.client else None)
    
    con.commit()
    con.close()
    
    await hub.broadcast("kitchen", {"type": "discount_applied", "order_id": payload.order_id})
    return {"ok": True, "id": did}

@app.get("/discounts/{order_id}")
def get_discounts(order_id: int):
    con = db()
    rows = con.execute("SELECT * FROM discounts WHERE order_id=?", (order_id,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.delete("/discounts/{discount_id}")
async def delete_discount(discount_id: int, request: Request):
    con = db()
    cur = con.cursor()
    
    # Obtener order_id antes de borrar
    discount = cur.execute("SELECT order_id FROM discounts WHERE id=?", (discount_id,)).fetchone()
    if not discount:
        con.close()
        raise HTTPException(404, "Descuento no encontrado")
    
    order_id = discount["order_id"]
    cur.execute("DELETE FROM discounts WHERE id=?", (discount_id,))
    
    # Recalcular totales
    calcular_totales_order(order_id, con)
    
    log_audit(action="DELETE", entity="discounts", entity_id=discount_id, 
              ip=request.client.host if request.client else None)
    
    con.commit()
    con.close()
    
    await hub.broadcast("kitchen", {"type": "discount_removed", "order_id": order_id})
    return {"ok": True}

# PAGOS
@app.post("/payments")
async def create_payment(payload: PaymentIn, request: Request):
    con = db()
    cur = con.cursor()
    
    # Verificar que la orden exista
    order = cur.execute("SELECT total, pagado FROM orders WHERE id=?", (payload.order_id,)).fetchone()
    if not order:
        con.close()
        raise HTTPException(404, "Orden no encontrada")
    
    cur.execute("""INSERT INTO payments(order_id, metodo, monto) VALUES(?,?,?)""",
                (payload.order_id, payload.metodo, payload.monto))
    pid = cur.lastrowid
    
    # Calcular total pagado
    total_pagado = cur.execute("""SELECT SUM(monto) as total FROM payments WHERE order_id=?""",
                               (payload.order_id,)).fetchone()["total"] or 0
    
    # Marcar como pagado si se completó el pago
    pagado = 1 if total_pagado >= order["total"] else 0
    cur.execute("UPDATE orders SET pagado=?, updated_at=datetime('now') WHERE id=?", 
                (pagado, payload.order_id))
    
    log_audit(action="CREATE", entity="payments", entity_id=pid, data=payload.dict(),
              ip=request.client.host if request.client else None)
    
    con.commit()
    con.close()
    
    await hub.broadcast("kitchen", {"type": "payment_added", "order_id": payload.order_id})
    return {"ok": True, "id": pid, "pagado": bool(pagado)}

@app.get("/payments/{order_id}")
def get_payments(order_id: int):
    con = db()
    rows = con.execute("SELECT * FROM payments WHERE order_id=? ORDER BY created_at", 
                      (order_id,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

# TABLAS/MESAS
@app.get("/tables")
def tables():
    con = db()
    rows = con.execute("SELECT id, nombre FROM tables WHERE activo=1 ORDER BY id").fetchall()
    con.close()
    return [dict(r) for r in rows]

# USUARIOS
@app.get("/users")
def users(rol: Optional[str] = None):
    con = db()
    if rol:
        rows = con.execute("SELECT id, nombre, rol FROM users WHERE rol=? AND activo=1", (rol,)).fetchall()
    else:
        rows = con.execute("SELECT id, nombre, rol FROM users WHERE activo=1").fetchall()
    con.close()
    return [dict(r) for r in rows]

# NOTAS GENERALES
@app.get("/notas")
def get_notas():
    con = db()
    rows = con.execute("SELECT id, contenido, ts FROM notas_generales WHERE activo=1 ORDER BY id DESC LIMIT 50").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.post("/notas")
async def create_nota(payload: dict = Body(...), request: Request = None):
    con = db()
    cur = con.cursor()
    contenido = payload.get("contenido", "")
    cur.execute("INSERT INTO notas_generales(contenido) VALUES(?)", (contenido,))
    nid = cur.lastrowid
    con.commit()
    
    log_audit(action="CREATE", entity="notas", entity_id=nid, data={"contenido": contenido},
              ip=request.client.host if request.client else None)
    
    con.close()
    await hub.broadcast("kitchen", {"type": "new_nota", "id": nid})
    return {"ok": True, "id": nid}

@app.delete("/notas/{nota_id}")
async def delete_nota(nota_id: int, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE notas_generales SET activo=0, updated_at=datetime('now') WHERE id=?", (nota_id,))
    con.commit()
    
    log_audit(action="DELETE", entity="notas", entity_id=nota_id, ip=request.client.host if request.client else None)
    
    con.close()
    await hub.broadcast("kitchen", {"type": "nota_deleted", "id": nota_id})
    return {"ok": True}

# ESTADÍSTICAS
@app.get("/stats/today")
def stats_today():
    con = db()
    today = datetime.utcnow().date().isoformat()
    
    total_vendido = con.execute("""
        SELECT SUM(total) as total FROM orders 
        WHERE DATE(ts) = ? AND anulada=0
    """, (today,)).fetchone()["total"] or 0
    
    total_comandas = con.execute("""
        SELECT COUNT(*) as count FROM orders 
        WHERE DATE(ts) = ? AND anulada=0
    """, (today,)).fetchone()["count"]
    
    por_mesa = con.execute("""
        SELECT t.nombre as mesa, SUM(o.total) as total, COUNT(*) as comandas
        FROM orders o
        LEFT JOIN tables t ON t.id=o.table_id
        WHERE DATE(o.ts) = ? AND o.anulada=0
        GROUP BY o.table_id
        ORDER BY total DESC
    """, (today,)).fetchall()
    
    por_mozo = con.execute("""
        SELECT mozo_nombre as mozo, SUM(total) as total, COUNT(*) as comandas
        FROM orders
        WHERE DATE(ts) = ? AND o.anulada=0 AND mozo_nombre IS NOT NULL
        GROUP BY mozo_nombre
        ORDER BY total DESC
    """, (today,)).fetchall()
    
    top_productos = con.execute("""
        SELECT oi.product_nombre, SUM(oi.cantidad) as vendidos, 
               SUM(oi.product_precio * oi.cantidad) as ingresos
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE DATE(o.ts) = ? AND o.anulada=0
        GROUP BY oi.product_nombre
        ORDER BY vendidos DESC
        LIMIT 10
    """, (today,)).fetchall()
    
    por_estado = con.execute("""
        SELECT estado, COUNT(*) as count
        FROM orders
        WHERE DATE(ts) = ? AND anulada=0
        GROUP BY estado
    """, (today,)).fetchall()
    
    con.close()
    return {
        "fecha": today,
        "total_vendido": total_vendido,
        "total_comandas": total_comandas,
        "por_mesa": [dict(r) for r in por_mesa],
        "por_mozo": [dict(r) for r in por_mozo],
        "top_productos": [dict(r) for r in top_productos],
        "por_estado": [dict(r) for r in por_estado]
    }

# EXPORTAR
@app.get("/export/orders")
def export_orders(fecha: Optional[str] = None):
    con = db()
    if fecha:
        rows = con.execute("""
            SELECT o.id, o.ts, t.nombre as mesa, o.mozo_nombre, o.subtotal, 
                   o.descuento_total, o.total, o.estado, o.anulada
            FROM orders o
            LEFT JOIN tables t ON t.id=o.table_id
            WHERE DATE(o.ts) = ?
            ORDER BY o.id
        """, (fecha,)).fetchall()
    else:
        today = datetime.utcnow().date().isoformat()
        rows = con.execute("""
            SELECT o.id, o.ts, t.nombre as mesa, o.mozo_nombre, o.subtotal,
                   o.descuento_total, o.total, o.estado, o.anulada
            FROM orders o
            LEFT JOIN tables t ON t.id=o.table_id
            WHERE DATE(o.ts) = ?
            ORDER BY o.id
        """, (today,)).fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Fecha/Hora', 'Mesa', 'Mozo', 'Subtotal', 'Descuento', 'Total', 'Estado', 'Anulada'])
    
    for r in rows:
        writer.writerow([
            r['id'], r['ts'], r['mesa'], r['mozo_nombre'], 
            r['subtotal'], r['descuento_total'], r['total'], 
            r['estado'], 'SI' if r['anulada'] else 'NO'
        ])
    
    con.close()
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=comandas_{datetime.utcnow().date()}.csv"}
    )

# AUDIT LOG
@app.get("/audit")
def get_audit_log(limit: int = 100):
    con = db()
    rows = con.execute("""
        SELECT * FROM audit_log 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

# BACKUP AUTOMÁTICO
def backup_database():
    """Crea backup diario de la base de datos"""
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_name = f"mozo_backup_{datetime.utcnow().date()}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        if not os.path.exists(backup_path):
            shutil.copy2(DB, backup_path)
            print(f"✅ Backup creado: {backup_name}")
            
            # Limpiar backups antiguos (mantener últimos 7 días)
            for f in os.listdir(BACKUP_DIR):
                if f.startswith("mozo_backup_"):
                    file_path = os.path.join(BACKUP_DIR, f)
                    if os.path.getctime(file_path) < (datetime.now() - timedelta(days=7)).timestamp():
                        os.remove(file_path)
                        print(f"🗑️  Backup antiguo eliminado: {f}")
    except Exception as e:
        print(f"❌ Error en backup: {e}")

# STARTUP
@app.on_event("startup")
def on_startup():
    print("🚀 Iniciando El Café de los Pinos...")
    
    # Crear backup
    backup_database()
    
    # NO resetear comandas en producción
    # Comentar estas líneas cuando vayas a producción:
    # try:
    #     con = db()
    #     cur = con.cursor()
    #     cur.execute("DELETE FROM order_items")
    #     cur.execute("DELETE FROM orders")
    #     cur.execute("DELETE FROM notas_generales")
    #     con.commit()
    #     con.close()
    #     print("⚠️  Reset de comandas (MODO DESARROLLO)")
    # except Exception as e:
    #     print(f"WARN reset DB: {e}")
    
    print("✅ Sistema listo")

# WEBSOCKET
@app.websocket("/ws/kitchen")
async def ws_kitchen(ws: WebSocket):
    await hub.connect(ws, "kitchen")
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.remove(ws, "kitchen")

# MIDDLEWARE NO CACHE
@app.middleware("http")
async def add_nocache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

# ESTÁTICOS
STATIC_DIR = "."
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def root():
    return {
        "ok": True, 
        "app": "El Café de los Pinos",
        "version": "2.0",
        "endpoints": {
            "web": "/static/index.html",
            "docs": "/docs",
            "mozo": "/static/mozo.html",
            "cocina": "/static/cocina.html",
            "admin": "/static/admin.html"
        }
    }