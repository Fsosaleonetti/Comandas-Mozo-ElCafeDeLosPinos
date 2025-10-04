-- Limpiar datos existentes
DELETE FROM order_items;
DELETE FROM orders;
DELETE FROM products;
DELETE FROM categories;
DELETE FROM users;
DELETE FROM tables;
DELETE FROM notas_generales;

-- Usuarios
INSERT INTO users(id, nombre, rol, pin) VALUES
 (1, 'Admin', 'admin', '1234'),
 (2, 'Lucas', 'mozo', ''),
 (3, 'Sofi', 'mozo', ''),
 (4, 'Fabri', 'mozo', '');

-- Mesas
INSERT INTO tables(id, nombre) VALUES
 (1, 'Mesa 1'),
 (2, 'Mesa 2'),
 (3, 'Mesa 3'),
 (4, 'Mesa 4'),
 (5, 'Mesa 5'),
 (6, 'Mesa 6'),
 (7, 'Mesa 7'),
 (8, 'Mesa 8'),
 (9, 'Mesa 9'),
 (10, 'Mesa 10');

-- Categorías (ajusta según tu menú)
-- Orden: menor número aparece primero
INSERT INTO categories(id, nombre, orden) VALUES
 (1, 'Bebidas Calientes', 1),
 (2, 'Bebidas Frías', 2),
 (3, 'Desayunos y Meriendas', 3),
 (4, 'Comidas', 4),
 (5, 'Postres', 5);

-- Productos de ejemplo (AJUSTA SEGÚN TU MENÚ REAL)
-- Bebidas Calientes
INSERT INTO products(nombre, precio, category_id, activo) VALUES
 ('Café espresso', 1500, 1, 1),
 ('Café con leche', 1800, 1, 1),
 ('Capuccino', 2200, 1, 1),
 ('Té negro', 1400, 1, 1),
 ('Té verde', 1400, 1, 1),
 ('Chocolate caliente', 2500, 1, 1);

-- Bebidas Frías
INSERT INTO products(nombre, precio, category_id, activo) VALUES
 ('Coca-Cola 500ml', 2000, 2, 1),
 ('Sprite 500ml', 2000, 2, 1),
 ('Agua mineral 500ml', 1500, 2, 1),
 ('Jugo de naranja natural', 2800, 2, 1),
 ('Limonada', 2500, 2, 1),
 ('Cerveza Quilmes', 3000, 2, 1);

-- Desayunos y Meriendas
INSERT INTO products(nombre, precio, category_id, activo) VALUES
 ('Medialuna simple', 900, 3, 1),
 ('Medialuna c/dulce de leche', 1200, 3, 1),
 ('Tostado jamón y queso', 3500, 3, 1),
 ('Tostado completo', 4000, 3, 1),
 ('Panqueques c/dulce de leche', 3800, 3, 1);

-- Comidas
INSERT INTO products(nombre, precio, category_id, activo) VALUES
 ('Milanesa napolitana', 6500, 4, 1),
 ('Hamburguesa completa', 5500, 4, 1),
 ('Pizza muzzarella', 4500, 4, 1),
 ('Ensalada César', 4800, 4, 1),
 ('Papas fritas', 3000, 4, 1);

-- Postres
INSERT INTO products(nombre, precio, category_id, activo) VALUES
 ('Flan con dulce de leche', 2800, 5, 1),
 ('Tiramisú', 3500, 5, 1),
 ('Helado 2 bochas', 2500, 5, 1),
 ('Brownie c/helado', 3800, 5, 1);

-- NOTAS:
-- 1. Este archivo es solo un EJEMPLO con precios y productos ficticios
-- 2. DEBES modificar las categorías y productos según tu menú real
-- 3. Los precios son orientativos (en pesos argentinos)
-- 4. Para cargar este archivo: sqlite3 mozo.db < seed.sql
-- 5. O copia/pega el contenido en un cliente SQL