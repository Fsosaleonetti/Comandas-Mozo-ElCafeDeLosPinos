# app.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
import sqlite3, json, os

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
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY, nombre TEXT, precio REAL, activo INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        table_id INTEGER,
        user_id INTEGER,
        mozo_nombre TEXT,
        anulada INTEGER DEFAULT 0,
        ts TEXT
    );
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY, order_id INTEGER, product_id INTEGER,
        cantidad INTEGER, notas TEXT
    );
    """)
    # Migración segura: agregar columna si no existe
    try:
        cur.execute("ALTER TABLE orders ADD COLUMN mozo_nombre TEXT")
    except sqlite3.OperationalError:
        pass
    con.commit(); con.close()

init_db()

# --- Pydantic ---
class ItemIn(BaseModel):
    product_id: Optional[int] = None      # permite item libre
    cantidad: int = 1
    notas: Optional[str] = None

class OrderIn(BaseModel):
    table_id: int
    user_id: Optional[int] = Field(default=None)
    user_name: Optional[str] = Field(default=None)
    items: List[ItemIn]

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
def products():
    con=db(); cur=con.cursor()
    rows = cur.execute("SELECT id,nombre,precio FROM products WHERE activo=1 ORDER BY nombre").fetchall()
    con.close(); return [dict(r) for r in rows]

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
    cur.execute("""INSERT INTO orders(table_id,user_id,mozo_nombre,anulada,ts)
                   VALUES(?,?,?,?,?)""",
                (payload.table_id,
                 payload.user_id if payload.user_id is not None else None,
                 payload.user_name if payload.user_name else None,
                 0, now))
    order_id = cur.lastrowid
    for it in payload.items:
        cur.execute("""INSERT INTO order_items(order_id,product_id,cantidad,notas)
                       VALUES(?,?,?,?)""",
                    (order_id, it.product_id, it.cantidad, it.notas))
    con.commit(); con.close()
    await hub.broadcast("kitchen", {"type":"new_order","order_id":order_id})
    return {"ok": True, "order_id": order_id}

@app.get("/orders")
def list_orders(anuladas: int = 0):
    con=db(); cur=con.cursor()
    rows = cur.execute("""SELECT o.id, o.table_id, o.user_id, o.mozo_nombre, o.anulada, o.ts,
                                 t.nombre AS mesa, u.nombre AS mozo
                          FROM orders o
                          LEFT JOIN tables t ON t.id=o.table_id
                          LEFT JOIN users u ON u.id=o.user_id
                          WHERE o.anulada=?
                          ORDER BY o.id DESC""", (anuladas,)).fetchall()
    data=[]
    for r in rows:
        it = con.execute("""
            SELECT oi.id,
                   COALESCE(p.nombre,'Pedido libre') AS nombre,
                   oi.cantidad, oi.notas
            FROM order_items oi
            LEFT JOIN products p ON p.id=oi.product_id
            WHERE oi.order_id=?""", (r["id"],)).fetchall()
        mozo_final = r["mozo_nombre"] if r["mozo_nombre"] else (r["mozo"] or r["user_id"])
        base = {**dict(r)}
        base["mozo"] = mozo_final
        data.append({**base, "items":[dict(x) for x in it]})
    con.close(); return data

@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id:int):
    con=db(); cur=con.cursor()
    # Elimina la verificación de PIN
    cur.execute("UPDATE orders SET anulada=1 WHERE id=?", (order_id,))
    con.commit(); con.close()
    return {"ok": True, "order_id": order_id, "anulada": 1}

@app.put("/orders/{order_id}")
def update_order(order_id: int, payload: dict = Body(...)):
    """
    Actualizar una comanda desde cocina.
    payload = {
      "admin_pin": "1234",
      "table_id": 1,
      "mozo_nombre": "Fabri",
      "items": [
        {"id": 10, "cantidad": 2, "notas": "sin azúcar"},
        {"id": 11, "delete": true}
      ]
    }
    - Si viene delete:true se elimina ese item de la comanda.
    - Si cantidad es 0, también elimina el item.
    """
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
    con.commit()
    # Devolver la comanda actualizada
    rows = cur.execute("""SELECT o.id, o.table_id, o.user_id, o.mozo_nombre, o.anulada, o.ts,
                                 t.nombre AS mesa, u.nombre AS mozo
                          FROM orders o
                          LEFT JOIN tables t ON t.id=o.table_id
                          LEFT JOIN users u ON u.id=o.user_id
                          WHERE o.id=?""", (order_id,)).fetchall()
    data=[]
    for r in rows:
        it = con.execute("""
            SELECT oi.id,
                   COALESCE(p.nombre,'Pedido libre') AS nombre,
                   oi.cantidad, oi.notas
            FROM order_items oi
            LEFT JOIN products p ON p.id=oi.product_id
            WHERE oi.order_id=?""", (r[0],)).fetchall()
        base = { "id": r[0], "table_id": r[1], "user_id": r[2], "mozo_nombre": r[3], "anulada": r[4], "ts": r[5], "mesa": r[6], "mozo": r[7] }
        data.append({**base, "items":[{"id":x[0],"nombre":x[1],"cantidad":x[2],"notas":x[3]} for x in it]})
    con.close()
    return {"ok": True, "order": data[0] if data else None}


@app.post("/orders/{order_id}/uncancel")
def uncancel_order(order_id:int):
    con=db(); cur=con.cursor()
    row = cur.execute("SELECT id FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        con.close(); raise HTTPException(status_code=404, detail="Pedido no existe")
    cur.execute("UPDATE orders SET anulada=0 WHERE id=?", (order_id,))
    con.commit(); con.close()
    # Avisar a cocina por WS
    try:
        import anyio
        anyio.from_thread.run(hub.broadcast, {"type":"order_restored","order_id":order_id})
    except Exception:
        pass
    return {"ok": True, "order_id": order_id, "anulada": 0}


# --- Reset al iniciar: limpia comandas y sube versión de SW (Mozo) ---
@app.on_event("startup")
def on_startup_reset():
    try:
        con = db(); cur = con.cursor()
        cur.execute("DELETE FROM order_items")
        cur.execute("DELETE FROM orders")
        con.commit(); con.close()
        print("Reset de comandas OK")
    except Exception as e:
        print("WARN reset DB:", e)

    # Forzar actualización de la PWA de Mozo cambiando el nombre del caché en el SW
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


# --- No cache para estáticos (evita 304/caché agresiva) ---
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
    return {"ok": True, "msg": "API lista. /static/mozo.html /static/cocina.html /docs"}
