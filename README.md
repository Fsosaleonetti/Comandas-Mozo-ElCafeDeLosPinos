# 🌲 El De Los Pinos - Sistema de Comandas

Sistema completo de gestión de comandas para restaurantes con soporte offline, calculadora integrada y gestión de productos.

## 🚀 Características Principales

### 📱 Vista Mozo
- Menú de productos con categorías y precios
- Búsqueda y filtrado de productos
- Carrito de compras con notas personalizadas
- Opción de pedido libre (texto)
- **Funciona 100% offline** con cola de sincronización automática
- PWA instalable en celular

### 👨‍🍳 Vista Cocina
- Visualización en tiempo real de comandas
- Edición de comandas (cantidad, notas, mesa, mozo)
- **Calculadora integrada** con historial de operaciones
- **Notas generales** compartidas para todo el equipo
- Muestra precios y totales por comanda
- Anular/restaurar comandas
- WebSocket para actualizaciones en vivo

### ⚙️ Panel de Administración
- Gestión completa de productos (crear, editar, eliminar)
- Gestión de categorías con orden personalizado
- **Estadísticas del día** (ventas totales, comandas, por mesa, por mozo)
- **Exportar a CSV/Excel** comandas del día
- Interfaz intuitiva y moderna

## 📋 Requisitos

- Python 3.8+
- FastAPI
- SQLite3 (incluido en Python)
- Navegador moderno (Chrome, Firefox, Edge)

## 🔧 Instalación

### 1. Instalar dependencias

```bash
pip install fastapi uvicorn
```

### 2. Cargar datos iniciales (OPCIONAL)

Edita `seed.sql` con tus categorías y productos reales, luego:

```bash
sqlite3 mozo.db < seed.sql
```

O usa el panel de Administración para cargar productos desde la interfaz web.

### 3. Iniciar el servidor

**Opción A - Usando el .bat (Windows):**
```bash
run_server_wifi.bat
```

**Opción B - Comando manual:**
```bash
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 4. Ver tu IP local

```bash
show_ip.bat
```

O manualmente:
```bash
ipconfig  # Windows
ifconfig  # Mac/Linux
```

## 📱 Uso en Celular

1. Conecta el celular a la **misma Wi-Fi** que la PC
2. Abre `http://TU_IP:8000/static/index.html` (ej: `http://192.168.1.176:8000/static/index.html`)
3. En Chrome Android: Menú (⋮) → **Añadir a pantalla de inicio**
4. ¡Listo! Ya tenés la app instalada

## 🎯 Configuración Inicial

### Paso 1: Crear Categorías
1. Abre `http://TU_IP:8000/static/admin.html`
2. Ve a la pestaña **Categorías**
3. Agrega tus categorías (ej: "Bebidas Calientes", "Comidas", etc.)
4. Asigna un orden (1, 2, 3...) para controlar cómo aparecen

### Paso 2: Cargar Productos
1. En Admin, ve a la pestaña **Productos**
2. Para cada producto completa:
   - Nombre (ej: "Café con leche")
   - Precio (ej: 1800)
   - Categoría (selecciona de la lista)
3. Clic en **Agregar Producto**

### Paso 3: Configurar PIN de Admin
Por defecto el PIN es **1234**. Para cambiarlo:

```sql
sqlite3 mozo.db
UPDATE users SET pin='TU_NUEVO_PIN' WHERE rol='admin';
.exit
```

## 📖 Guía de Uso

### Para Mozos

1. Abre la app del Mozo
2. Selecciona la mesa
3. Escribe tu nombre (opcional)
4. **Opción A - Usar el menú:**
   - Filtra por categoría
   - Busca productos
   - Toca productos para agregarlos al carrito
   - Ajusta cantidades y agrega notas
   - Envía el pedido
5. **Opción B - Pedido libre:**
   - Cambia a la pestaña "Pedido Libre"
   - Escribe el pedido como texto
   - Envía

**Nota:** Si no hay internet, el pedido queda en cola y se envía automáticamente cuando vuelve la conexión.

### Para Cocina

1. Abre la vista de Cocina
2. Las comandas aparecen en tiempo real
3. Para editar una comanda:
   - Modifica cantidades, notas, mesa o mozo
   - Clic en **Guardar** (requiere PIN admin)
4. Usa la **calculadora** para cálculos rápidos
5. Usa **Notas Generales** para comunicaciones del equipo

### Para Administración

1. Abre el panel de Admin
2. **Estadísticas:** Ver ventas del día
3. **Exportar:** Descargar CSV con todas las comandas
4. **Productos/Categorías:** Gestionar el menú

## 🔒 Seguridad

- El PIN admin protege la edición de comandas en Cocina
- Cambia el PIN por defecto (1234) antes de usar en producción
- El sistema resetea comandas al iniciar el servidor (para testing)
- Para producción, comenta las líneas de reset en `app.py` (función `on_startup_reset`)

## 🗂️ Estructura de Archivos

```
El_Cafe_De_Los_Pinos/
├── app.py                      # Backend FastAPI
├── mozo.db                     # Base de datos SQLite
├── seed.sql                    # Datos de ejemplo
├── mozo.html                   # Vista Mozo (PWA)
├── cocina.html                 # Vista Cocina
├── admin.html                  # Panel Administración
├── index.html                  # Página principal
├── sw-mozo.js                  # Service Worker (offline)
├── manifest.mozo.webmanifest   # PWA manifest
├── run_server_wifi.bat         # Iniciar servidor (Windows)
├── show_ip.bat                 # Ver IP local
├── stop_servers.bat            # Detener servidores
└── icons/                      # Iconos PWA
    ├── mozo-192.png
    └── mozo-512.png
```

## 🎨 Personalización

### Cambiar Colores
Edita las variables CSS en cada archivo HTML:
- `#3b82f6` - Azul principal
- `#10b981` - Verde (precios, success)
- `#ef4444` - Rojo (eliminar, cancelar)

### Agregar Más Mesas
En `mozo.html` y `cocina.html`, edita el `<select id="mesa">` y agrega opciones.

O mejor aún, modifica `seed.sql` para agregar mesas en la base de datos.

### Modificar Productos
Todo se hace desde el Panel de Administración, ¡no necesitas tocar código!

## 🐛 Solución de Problemas

### El Mozo no funciona offline
1. Verifica que el Service Worker esté registrado (F12 → Application → Service Workers)
2. Asegúrate de estar usando HTTPS o localhost
3. Limpia caché y recarga (Ctrl+Shift+R)

### No aparecen los productos en el Mozo
1. Verifica que agregaste productos en Admin
2. Asegúrate de que `activo=1` en la tabla `products`
3. Refresca la página del Mozo

### La calculadora no guarda historial al cerrar
Es normal, el historial es temporal (solo en sesión). Si querés persistencia, avísame.

### Comandas no se actualizan en tiempo real
1. Verifica que el WebSocket esté conectado (debe decir "escuchando pedidos...")
2. Revisa la consola del navegador (F12) por errores
3. Reinicia el servidor

### Error "PIN inválido" al editar comanda
El PIN por defecto es `1234`. Si lo cambiaste, usa el nuevo.

## 📊 Base de Datos

### Estructura Principal

**users** - Usuarios del sistema
- `id`, `nombre`, `rol` (admin/mozo), `pin`

**tables** - Mesas del restaurante
- `id`, `nombre`

**categories** - Categorías de productos
- `id`, `nombre`, `orden`

**products** - Productos del menú
- `id`, `nombre`, `precio`, `category_id`, `activo`

**orders** - Comandas
- `id`, `table_id`, `user_id`, `mozo_nombre`, `total`, `anulada`, `ts`

**order_items** - Items de cada comanda
- `id`, `order_id`, `product_id`, `product_nombre`, `product_precio`, `cantidad`, `notas`

**notas_generales** - Notas compartidas (sesión)
- `id`, `contenido`, `ts`

### Consultas Útiles

```sql
-- Ver ventas del día
SELECT DATE(ts) as fecha, SUM(total) as total
FROM orders
WHERE anulada=0
GROUP BY DATE(ts);

-- Top 10 productos más vendidos
SELECT product_nombre, SUM(cantidad) as vendidos
FROM order_items
WHERE order_id IN (SELECT id FROM orders WHERE anulada=0)
GROUP BY product_nombre
ORDER BY vendidos DESC
LIMIT 10;

-- Ver comandas por mozo
SELECT mozo_nombre, COUNT(*) as comandas, SUM(total) as total
FROM orders
WHERE anulada=0 AND DATE(ts) = DATE('now')
GROUP BY mozo_nombre;
```

## 🚀 Próximas Mejoras (Opcional)

- [ ] Sistema de impresión de comandas
- [ ] Múltiples turnos y cierres de caja
- [ ] Reportes avanzados (gráficos)
- [ ] Sistema de reservas
- [ ] Integración con impresora térmica
- [ ] App móvil nativa
- [ ] Multi-restaurante

## 🤝 Soporte

Para consultas o problemas, contacta al desarrollador del sistema.

## 📝 Notas Importantes

1. **Backup:** Hace backup regular de `mozo.db`
2. **Testing:** El servidor resetea comandas al iniciar (línea 244 en app.py)
3. **Producción:** Comenta el reset automático antes de usar en vivo
4. **WiFi:** Asegúrate de que todos los dispositivos estén en la misma red
5. **Firewall:** Puede que necesites abrir el puerto 8000 en Windows Firewall

## 📄 Licencia

Sistema desarrollado para El De Los Pinos. Uso interno.