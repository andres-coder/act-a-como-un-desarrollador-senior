# Bemba POS

Bemba es un sistema POS profesional para restaurantes construido con Python, Django, Django REST Framework, JWT, Bootstrap, JavaScript y MySQL.

## Módulos incluidos

- Login y autenticación con usuario personalizado.
- Roles: administrador, gerente, cajero, mesero y cocina.
- Dashboard administrativo responsive.
- Gestión de zonas y mesas.
- Punto de venta con ticket visual.
- Pedidos con estados operativos.
- Cocina y comandas.
- Inventario con recetas, movimientos y consumo automático por venta.
- Reportes web y PDF.
- API REST protegida con JWT.

## Instalación

1. Crear entorno virtual:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. Crear base de datos MySQL:

```powershell
mysql -u root -p < database.sql
```

4. Configurar variables:

```powershell
copy .env.example .env
```

5. Ejecutar migraciones:

```powershell
python manage.py migrate
```

6. Crear superusuario:

```powershell
python manage.py createsuperuser
```

7. Iniciar servidor:

```powershell
python manage.py runserver
```

## URLs principales

- Web: `http://127.0.0.1:8000/`
- Login: `http://127.0.0.1:8000/accounts/login/`
- Admin: `http://127.0.0.1:8000/admin/`
- API: `http://127.0.0.1:8000/api/`
- JWT token: `http://127.0.0.1:8000/api/auth/token/`
- Reporte PDF: `http://127.0.0.1:8000/reports/sales.pdf`

## Arquitectura

El proyecto está separado por dominios:

- `accounts`: usuarios, roles, permisos y autenticación.
- `restaurant`: zonas y mesas.
- `inventory`: categorías, productos, ingredientes, recetas y stock.
- `sales`: pedidos, detalle de pedido, pagos, tickets y consumo automático de inventario.
- `kitchen`: comandas.
- `reports`: reportes HTML/PDF.
- `dashboard`: panel administrativo.

## Flujo operativo

1. El mesero crea un pedido desde POS y selecciona mesa/productos.
2. El pedido se envía a cocina y se genera una comanda.
3. Cocina cambia el estado operativo de preparación.
4. Caja registra el pago.
5. Al pagar, el pedido queda cerrado, la mesa pasa a limpieza y el inventario se descuenta con base en la receta de cada producto.

## Próximos pasos recomendados

- Añadir pruebas automatizadas de flujo POS completo.
- Crear formularios CRUD HTML completos además de la API.
- Incorporar multi-tenant real para SaaS por restaurante/sucursal.
- Agregar impresión térmica ESC/POS.
- Añadir WebSockets para cocina en tiempo real.
