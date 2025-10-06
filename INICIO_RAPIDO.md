# 🚀 Inicio Rápido - El Café de los Pinos

## ⚡ Si es tu PRIMERA VEZ

### 1️⃣ Aplicar Migración (SOLO UNA VEZ)
```bash
python aplicar_migracion.py
```
Responde **"s"** cuando te pregunte.

### 2️⃣ Iniciar Servidor
```bash
START_SERVER.bat
```
O:
```bash
run_server_wifi.bat
```

**Se abrirá automáticamente el navegador** en http://localhost:8000/static/index.html

---

## 📋 Pasos Iniciales (Primera Configuración)

### Paso 1: Crear Categorías
1. Ve a **Admin** → Tab **"Categorías"**
2. Crea tus categorías (ej: Bebidas Calientes, Comidas, Postres)
3. Asigna orden (1, 2, 3...)

### Paso 2: Agregar Productos
1. Ve a **Admin** → Tab **"Productos"**
2. Completa: Nombre, Precio, Categoría
3. Clic en "Agregar Producto"

### Paso 3: Configurar Modificadores (opcional)
1. Ve a **Admin** → Tab **"Modificadores"**
2. Agrega modificadores (ej: "Sin azúcar", "Extra shot")
3. Asigna precio extra si corresponde

### Paso 4: Cambiar PIN Admin (recomendado)
```bash
sqlite3 mozo.db
UPDATE users SET pin='TU_NUEVO_PIN' WHERE rol='admin';
.exit
```

---

## 🌐 Usar desde Celular

### Ver tu IP:
El script **START_SERVER.bat** muestra automáticamente tus IPs.

O ejecuta:
```bash
show_ip.bat
```

### Conectar celular:
1. Conectá el celular a la **misma WiFi**
2. Abre: `http://TU_IP:8000/static/index.html`
3. Ejemplo: `http://192.168.1.176:8000/static/index.html`

### Instalar PWA (Mozo):
1. Abre `http://TU_IP:8000/static/mozo.html`
2. Chrome Android: Menú (⋮) → **"Añadir a pantalla de inicio"**
3. ¡Listo! Ya tenés la app instalada

---

## 🎯 Accesos Rápidos

| Vista | URL |
|-------|-----|
| **Principal** | http://localhost:8000/static/index.html |
| **Mozo** | http://localhost:8000/static/mozo.html |
| **Cocina** | http://localhost:8000/static/cocina.html |
| **Admin** | http://localhost:8000/static/admin.html |
| **API Docs** | http://localhost:8000/docs |

---

## ⌨️ Atajos de Teclado

### Calculadora en Cocina:
- **Números**: 0-9
- **Operadores**: + - * /
- **Calcular**: Enter o =
- **Limpiar**: Esc o C
- **Borrar**: Backspace
- **Punto decimal**: . o ,

### General:
- **Ctrl+F5**: Refrescar forzado (limpia cache)
- **F12**: Abrir DevTools (para debug)

---

## 🐛 Problemas Comunes

### "No puedo agregar categorías/productos"
✅ **ARREGLADO** - Reemplaza `admin.html` con la versión nueva

### "La calculadora no funciona con teclado"
✅ **ARREGLADO** - Reemplaza `cocina.html` con la versión nueva

### "El .bat no abre el navegador"
✅ **ARREGLADO** - Usa `START_SERVER.bat`

### "Error: no such column: estado"
```bash
python aplicar_migracion.py
```

### "No aparecen productos en el Mozo"
1. Verifica que creaste productos en Admin
2. Refresca la página (Ctrl+F5)

### "WebSocket desconectado"
- Normal si reiniciaste el servidor
- Refresca la página de Cocina

---

## 🔧 Comandos Útiles

### Ver productos:
```bash
sqlite3 mozo.db "SELECT * FROM products;"
```

### Ver categorías:
```bash
sqlite3 mozo.db "SELECT * FROM categories;"
```

### Ver comandas del día:
```bash
sqlite3 mozo.db "SELECT * FROM orders WHERE DATE(ts) = DATE('now');"
```

### Backup manual:
```bash
copy mozo.db backups\mozo_manual.db
```

### Limpiar comandas (testing):
```bash
sqlite3 mozo.db
DELETE FROM order_items;
DELETE FROM orders;
.exit
```

---

## 📊 Flujo de Trabajo Normal

### 1. Mozo toma pedido:
- Abre app Mozo
- Selecciona mesa
- Agrega productos
- Aplica modificadores (ej: "Sin azúcar")
- Envía pedido

### 2. Cocina recibe:
- Ve pedido en tiempo real
- Cambia estado: Pendiente → Listo
- Usa calculadora si necesita
- Agrega notas generales si necesita

### 3. Cobro:
- En Cocina: Click "💳 Pago"
- Selecciona método (efectivo, tarjeta, etc.)
- Registra monto
- Marca como "Cobrado"

### 4. Estadísticas:
- Admin → Tab "Estadísticas"
- Ver totales del día
- Exportar a CSV

---

## 🔒 Antes de Producción

- [ ] Cambiar PIN admin (default: 1234)
- [ ] Comentar reset automático en `app.py` (línea ~244)
- [ ] Configurar CORS en producción (línea ~20 de `app.py`)
- [ ] Probar todo el flujo completo
- [ ] Capacitar al personal

---

## 📞 Contacto y Soporte

Si algo no funciona:
1. Revisa esta guía
2. Lee `INSTALACION_FASE_1_Y_2.md`
3. Consulta logs del servidor (terminal donde corre uvicorn)
4. Verifica console del navegador (F12)

---

## ✅ Checklist Diario

**Al abrir:**
- [ ] Ejecutar `START_SERVER.bat`
- [ ] Verificar que abre el navegador
- [ ] Probar crear una comanda de prueba

**Al cerrar:**
- [ ] Detener servidor (Ctrl+C en la terminal)
- [ ] Opcional: Backup manual de mozo.db

**Semanal:**
- [ ] Revisar backups en carpeta `/backups`
- [ ] Exportar estadísticas de la semana
- [ ] Limpiar audit log si crece mucho

---

**Versión:** 2.0  
**Última actualización:** Octubre 2025  
**Sistema:** El Café de los Pinos