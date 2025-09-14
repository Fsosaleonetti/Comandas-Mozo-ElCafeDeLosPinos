DELETE FROM users; DELETE FROM tables; DELETE FROM products;
INSERT INTO users(id,nombre,rol,pin) VALUES
 (1,'Cora','admin','1234'),
 (2,'Lucas','mozo',''),
 (3,'Sofi','mozo','');

INSERT INTO tables(id,nombre) VALUES
 (1,'Mesa 1'), (2,'Mesa 2'), (3,'Mesa 3'), (4,'Barra');

INSERT INTO products(id,nombre,precio,activo) VALUES
 (1,'Café espresso',1500,1),
 (2,'Capuccino',2200,1),
 (3,'Medialuna',900,1),
 (4,'Tostado jamón y queso',3500,1),
 (5,'Limonada 500ml',2500,1);
