# app.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
import sqlite3, json, os, io, csv

DB = "mozo.db"
app = FastAPI(title="Mozo-Cocina MVP")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --- DB helpers ---
def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db(); cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, nombre TEXT, rol TEXT, pin TEXT
    );
    CREATE TABLE IF NOT EXISTS tables (
        id INTEGER PRIMARY KEY, nombre TEXT
    );
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY, nombre TEXT, orden INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY, 
        nombre TEXT, 
        precio REAL, 
        category_id INTEGER,
        activo INTEGER DEFAULT 1,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        table_id INTEGER,
        user_id INTEGER,
        mozo_nombre TEXT,
        total REAL DEFAULT 0,
        anulada INTEGER DEFAULT 0,
        ts TEXT
    );
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY, 
        order_id INTEGER, 
        product_id INTEGER,
        product_nombre TEXT,
        product_precio REAL,
        cantidad INTEGER, 
        notas TEXT
    );
    CREATE TABLE IF NOT EXISTS notas_generales (
        id INTEGER PRIMARY KEY,
        contenido TEXT,
        ts TEXT
    );
    """)
    # Migraciones seguras
    try:
        cur.execute("ALTER TABLE orders ADD COLUMN mozo_nombre TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE orders ADD COLUMN total REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE order_items ADD COLUMN product_nombre TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE order_items ADD COLUMN product_precio REAL")
    except sqlite3.OperationalError:
        pass
    con.commit(); con.close()

init_db()

# --- Pydantic ---
class ItemIn(BaseModel):
    product_id: Optional[int] = None
    cantidad: int = 1
    notas: Optional[str] = None

class OrderIn(BaseModel):
    table_id: int
    user_id: Optional[int] = Field(default=None)
    user_name: Optional[str] = Field(default=None)
    items: List[ItemIn]

class ProductIn(BaseModel):
    nombre: str
    precio: float
    category_id: Optional[int] = None

class CategoryIn(BaseModel):
    nombre: str
    orden: int = 0

# --- WebSocket Hub ---
class Hub:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {"kitchen": []}
    async def connect(self, ws: WebSocket, room: str):
        await ws.accept(); self.rooms[room].append(ws)
    def remove(self, ws: WebSocket, room: str):
        if ws in self.rooms[room]: self.rooms[room].remove(ws)
    async def broadcast(self, room: str, message: dict):
        dead=[]
        for ws in list(self.rooms[room]):
            try: await ws.send_text(json.dumps(message))
            except: dead.append(ws)
        for d in dead: self.remove(d, room)

hub = Hub()

# --- API ---
@app.get("/products")
def products(category_id: Optional[int] = None):
    con=db(); cur=con.cursor()
    if category_id:
        rows = cur.execute("""SELECT p.id, p.nombre, p.precio, p.category_id, c.nombre as categoria
                              FROM products p 
                              LEFT JOIN categories c ON c.id = p.category_id
                              WHERE p.activo=1 AND p.category_id=? 
                              ORDER BY p.nombre""", (category_id,)).fetchall()
    else:
        rows = cur.execute("""SELECT p.id, p.nombre, p.precio, p.category_id, c.nombre as categoria
                              FROM products p 
                              LEFT JOIN categories c ON c.id = p.category_id
                              WHERE p.activo=1 
                              ORDER BY p.nombre""").fetchall()
    con.close(); return [dict(r) for r in rows]

@app.post("/products")
def create_product(payload: ProductIn):
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO products(nombre, precio, category_id) VALUES(?,?,?)",
                (payload.nombre, payload.precio, payload.category_id))
    con.commit()
    pid = cur.lastrowid
    con.close()
    return {"ok": True, "id": pid}

@app.delete("/products/{product_id}")
def delete_product(product_id: int):
    con=db(); cur=con.cursor()
    cur.execute("UPDATE products SET activo=0 WHERE id=?", (product_id,))
    con.commit(); con.close()
    return {"ok": True}

@app.get("/categories")
def categories():
    con=db(); cur=con.cursor()
    rows = cur.execute("SELECT id, nombre, orden FROM categories ORDER BY orden, nombre").fetchall()
    con.close(); return [dict(r) for r in rows]

@app.post("/categories")
def create_category(payload: CategoryIn):
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO categories(nombre, orden) VALUES(?,?)", (payload.nombre, payload.orden))
    con.commit()
    cid = cur.lastrowid
    con.close()
    return {"ok": True, "id": cid}

@app.delete("/categories/{category_id}")
def delete_category(category_id: int):
    con=db(); cur=con.cursor()
    cur.execute("DELETE FROM categories WHERE id=?", (category_id,))
    con.commit(); con.close()
    return {"ok": True}

@app.get("/tables")
def tables():
    con=db(); cur=con.cursor()
    rows = cur.execute("SELECT id,nombre FROM tables ORDER BY id").fetchall()
    con.close(); return [dict(r) for r in rows]

@app.get("/users")
def users(rol: Optional[str] = None):
    con=db(); cur=con.cursor()
    if rol:
        rows = cur.execute("SELECT id,nombre,rol FROM users WHERE rol=?", (rol,)).fetchall()
    else:
        rows = cur.execute("SELECT id,nombre,rol FROM users").fetchall()
    con.close(); return [dict(r) for r in rows]

@app.post("/orders")
async def create_order(payload: OrderIn):
    if not payload.items:
        raise HTTPException(400, "Pedido sin items")
    con=db(); cur=con.cursor()
    now = datetime.utcnow().isoformat()
    
    # Calcular total
    total = 0
    items_data = []
    for it in payload.items:
        if it.product_id:
            prod = cur.execute("SELECT nombre, precio FROM products WHERE id=?", (it.product_id,)).fetchone()
            if prod:
                nombre = prod["nombre"]
                precio = prod["precio"]
                total += precio * it.cantidad
            else:
                nombre = "Producto desconocido"
                precio = 0
        else:
            nombre = "Pedido libre"
            precio = 0
        items_data.append((nombre, precio, it.cantidad, it.notas))
    
    cur.execute("""INSERT INTO orders(table_id,user_id,mozo_nombre,total,anulada,ts)
                   VALUES(?,?,?,?,?,?)""",
                (payload.table_id,
                 payload.user_id if payload.user_id is not None else None,
                 payload.user_name if payload.user_name else None,
                 total, 0, now))
    order_id = cur.lastrowid
    
    for nombre, precio, cantidad, notas in items_data:
        cur.execute("""INSERT INTO order_items(order_id,product_id,product_nombre,product_precio,cantidad,notas)
                       VALUES(?,?,?,?,?,?)""",
                    (order_id, None, nombre, precio, cantidad, notas))
    
    con.commit(); con.close()
    await hub.broadcast("kitchen", {"type":"new_order","order_id":order_id})
    return {"ok": True, "order_id": order_id}

@app.get("/orders")
def list_orders(anuladas: int = 0):
    con=db(); cur=con.cursor()
    rows = cur.execute("""SELECT o.id, o.table_id, o.user_id, o.mozo_nombre, o.total, o.anulada, o.ts,
                                 t.nombre AS mesa, u.nombre AS mozo
                          FROM orders o
                          LEFT JOIN tables t ON t.id=o.table_id
                          LEFT JOIN users u ON u.id=o.user_id
                          WHERE o.anulada=?
                          ORDER BY o.id DESC""", (anuladas,)).fetchall()
    data=[]
    for r in rows:
        it = con.execute("""
            SELECT oi.id, oi.product_nombre as nombre, oi.product_precio as precio,
                   oi.cantidad, oi.notas
            FROM order_items oi
            WHERE oi.order_id=?""", (r["id"],)).fetchall()
        mozo_final = r["mozo_nombre"] if r["mozo_nombre"] else (r["mozo"] or r["user_id"])
        base = {**dict(r)}
        base["mozo"] = mozo_final
        data.append({**base, "items":[dict(x) for x in it]})
    con.close(); return data

@app.post("/orders/{order_id}/cancel")
async def cancel_order(order_id:int):
    con=db(); cur=con.cursor()
    cur.execute("UPDATE orders SET anulada=1 WHERE id=?", (order_id,))
    con.commit(); con.close()
    await hub.broadcast("kitchen", {"type":"order_cancelled","order_id":order_id})
    return {"ok": True, "order_id": order_id, "anulada": 1}

@app.put("/orders/{order_id}")
async def update_order(order_id: int, payload: dict = Body(...)):
    con=db(); cur=con.cursor()
    admin_pin = payload.get("admin_pin")
    admin = cur.execute("SELECT id FROM users WHERE rol='admin' AND pin=?", (admin_pin,)).fetchone()
    if not admin:
        con.close()
        raise HTTPException(status_code=403, detail="PIN inválido")
    row = cur.execute("SELECT id, anulada FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        con.close(); raise HTTPException(status_code=404, detail="Pedido no existe")
    
    if "table_id" in payload:
        cur.execute("UPDATE orders SET table_id=? WHERE id=?", (payload["table_id"], order_id))
    if "mozo_nombre" in payload:
        cur.execute("UPDATE orders SET mozo_nombre=? WHERE id=?", (payload["mozo_nombre"], order_id))
    
    items = payload.get("items") or []
    for it in items:
        iid = it.get("id")
        if not iid: continue
        if it.get("delete") or it.get("cantidad", 1) == 0:
            cur.execute("DELETE FROM order_items WHERE id=? AND order_id=?", (iid, order_id))
            continue
        if "cantidad" in it or "notas" in it:
            cur.execute("UPDATE order_items SET cantidad=COALESCE(?, cantidad), notas=COALESCE(?, notas) WHERE id=? AND order_id=?",
                        (it.get("cantidad"), it.get("notas"), iid, order_id))
    
    # Recalcular total
    total = cur.execute("""SELECT SUM(product_precio * cantidad) as total 
                          FROM order_items WHERE order_id=?""", (order_id,)).fetchone()["total"] or 0
    cur.execute("UPDATE orders SET total=? WHERE id=?", (total, order_id))
    
    con.commit(); con.close()
    await hub.broadcast("kitchen", {"type":"order_updated","order_id":order_id})
    return {"ok": True, "order_id": order_id}

@app.post("/orders/{order_id}/uncancel")
async def uncancel_order(order_id:int):
    con=db(); cur=con.cursor()
    row = cur.execute("SELECT id FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        con.close(); raise HTTPException(status_code=404, detail="Pedido no existe")
    cur.execute("UPDATE orders SET anulada=0 WHERE id=?", (order_id,))
    con.commit(); con.close()
    await hub.broadcast("kitchen", {"type":"order_restored","order_id":order_id})
    return {"ok": True, "order_id": order_id, "anulada": 0}

# --- Notas Generales ---
@app.get("/notas")
def get_notas():
    con=db(); cur=con.cursor()
    rows = cur.execute("SELECT id, contenido, ts FROM notas_generales ORDER BY id DESC LIMIT 50").fetchall()
    con.close(); return [dict(r) for r in rows]

@app.post("/notas")
async def create_nota(payload: dict = Body(...)):
    con=db(); cur=con.cursor()
    contenido = payload.get("contenido", "")
    now = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO notas_generales(contenido, ts) VALUES(?,?)", (contenido, now))
    con.commit()
    nid = cur.lastrowid
    con.close()
    await hub.broadcast("kitchen", {"type":"new_nota","id":nid})
    return {"ok": True, "id": nid}

@app.delete("/notas/{nota_id}")
async def delete_nota(nota_id: int):
    con=db(); cur=con.cursor()
    cur.execute("DELETE FROM notas_generales WHERE id=?", (nota_id,))
    con.commit(); con.close()
    await hub.broadcast("kitchen", {"type":"nota_deleted","id":nota_id})
    return {"ok": True}

# --- Exportar a Excel (CSV) ---
@app.get("/export/orders")
def export_orders(fecha: Optional[str] = None):
    con=db(); cur=con.cursor()
    if fecha:
        rows = cur.execute("""
            SELECT o.id, o.ts, t.nombre as mesa, o.mozo_nombre, o.total, o.anulada
            FROM orders o
            LEFT JOIN tables t ON t.id=o.table_id
            WHERE DATE(o.ts) = ?
            ORDER BY o.id
        """, (fecha,)).fetchall()
    else:
        today = datetime.utcnow().date().isoformat()
        rows = cur.execute("""
            SELECT o.id, o.ts, t.nombre as mesa, o.mozo_nombre, o.total, o.anulada
            FROM orders o
            LEFT JOIN tables t ON t.id=o.table_id
            WHERE DATE(o.ts) = ?
            ORDER BY o.id
        """, (today,)).fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Fecha/Hora', 'Mesa', 'Mozo', 'Total', 'Anulada'])
    
    for r in rows:
        writer.writerow([r['id'], r['ts'], r['mesa'], r['mozo_nombre'], r['total'], 'SI' if r['anulada'] else 'NO'])
    
    con.close()
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=comandas_{datetime.utcnow().date()}.csv"}
    )

# --- Estadísticas ---
@app.get("/stats/today")
def stats_today():
    con=db(); cur=con.cursor()
    today = datetime.utcnow().date().isoformat()
    
    total_vendido = cur.execute("""
        SELECT SUM(total) as total FROM orders 
        WHERE DATE(ts) = ? AND anulada=0
    """, (today,)).fetchone()["total"] or 0
    
    total_comandas = cur.execute("""
        SELECT COUNT(*) as count FROM orders 
        WHERE DATE(ts) = ? AND anulada=0
    """, (today,)).fetchone()["count"]
    
    por_mesa = cur.execute("""
        SELECT t.nombre as mesa, SUM(o.total) as total, COUNT(*) as comandas
        FROM orders o
        LEFT JOIN tables t ON t.id=o.table_id
        WHERE DATE(o.ts) = ? AND o.anulada=0
        GROUP BY o.table_id
        ORDER BY total DESC
    """, (today,)).fetchall()
    
    por_mozo = cur.execute("""
        SELECT mozo_nombre as mozo, SUM(total) as total, COUNT(*) as comandas
        FROM orders
        WHERE DATE(ts) = ? AND anulada=0 AND mozo_nombre IS NOT NULL
        GROUP BY mozo_nombre
        ORDER BY total DESC
    """, (today,)).fetchall()
    
    con.close()
    return {
        "fecha": today,
        "total_vendido": total_vendido,
        "total_comandas": total_comandas,
        "por_mesa": [dict(r) for r in por_mesa],
        "por_mozo": [dict(r) for r in por_mozo]
    }

# --- Reset al iniciar ---
@app.on_event("startup")
def on_startup_reset():
    try:
        con = db(); cur = con.cursor()
        cur.execute("DELETE FROM order_items")
        cur.execute("DELETE FROM orders")
        cur.execute("DELETE FROM notas_generales")
        con.commit(); con.close()
        print("Reset de comandas OK")
    except Exception as e:
        print("WARN reset DB:", e)

    try:
        import re, time, pathlib
        ts = str(int(time.time()))
        p = pathlib.Path("sw-mozo.js")
        if p.exists():
            s = p.read_text(encoding="utf-8")
            s2 = re.sub(r"CACHE\s*=\s*'mozo-cache-[^']+'", f"CACHE = 'mozo-cache-{ts}'", s)
            if s2 != s:
                p.write_text(s2, encoding="utf-8")
                print("SW mozo cache bump ->", ts)
    except Exception as e:
        print("WARN bump SW:", e)

# --- WebSockets ---
@app.websocket("/ws/kitchen")
async def ws_kitchen(ws: WebSocket):
    await hub.connect(ws, "kitchen")
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.remove(ws, "kitchen")

# --- No cache ---
@app.middleware("http")
async def add_nocache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

# --- Estáticos ---
STATIC_DIR = "."
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def root():
    return {"ok": True, "msg": "API lista. /static/index.html /docs"}