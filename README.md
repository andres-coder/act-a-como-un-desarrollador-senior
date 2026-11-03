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

3. Para desarrollo local se usa SQLite y no hace falta crear MySQL. En el entorno de despliegue, crea la base MySQL y configura sus credenciales en `.env`:

```powershell
mysql -u root -p < database.sql
```

4. Configurar variables:

```powershell
copy .env.example .env
```

5. Ejecutar migraciones locales:

```powershell
python manage.py migrate --settings bemba.settings_dev
```

6. Crear superusuario local:

```powershell
python manage.py createsuperuser --settings bemba.settings_dev
```

7. Iniciar servidor local con la configuración de desarrollo (SQLite y HTTP):

```powershell
python manage.py runserver --settings bemba.settings_dev
```

La configuración predeterminada (`bemba.settings`) es para despliegue detrás de HTTPS: requiere `DJANGO_SECRET_KEY`, `DEBUG=False`, HTTPS y cookies seguras. No uses `.env.example` como secreto de producción; genera una clave privada y configura los hosts y la base de datos del entorno.

Para desplegar, usa `bemba.settings` en todos los comandos de administración y el servidor WSGI/ASGI, con MySQL, una clave secreta aleatoria, hosts reales y HTTPS configurados.

## Pruebas y revisión de despliegue

```powershell
python manage.py test --settings bemba.settings_test
python manage.py check --deploy
```

`settings_test` usa SQLite en memoria para que la suite no modifique la base local. Antes de desplegar, configura las variables de entorno reales y ejecuta `check --deploy` en el mismo entorno de producción.

Para probar perfiles manualmente en la base SQLite de desarrollo, aplica migraciones con `bemba.settings_dev` y ejecuta:

```powershell
python manage.py create_demo_profiles --settings bemba.settings_dev
```

El comando crea un propietario de restaurante, gerente, cajero, mesero y cocinero de prueba, además de datos demo para cocina/caja. No borra usuarios existentes ni crea otro superadministrador. La contraseña local predeterminada es `BembaDemo2026!`; puedes cambiarla mediante `BEMBA_DEMO_PASSWORD` antes de ejecutar el comando. No uses estas cuentas en producción.

| Perfil | Área inicial y alcance |
| --- | --- |
| Superadministrador | Panel global de Django y todos los restaurantes |
| Propietario (`admin`) | Panel del restaurante y su plan/suscripción |
| Gerente | Panel y datos de su sucursal; administra personal operativo |
| Cajero | Lista de pedidos listos para cobrar en su sucursal |
| Mesero | Mesas y POS para crear/enviar pedidos |
| Cocina (`chef`) | Comandas de su sucursal |

| Requisitos | Evidencia automatizada |
| --- | --- |
| RF-01, RF-02, RF-03, RF-15, RNF-01 | Token JWT, API protegida y restricción por rol (`accounts/tests.py`) |
| RF-05, RF-06, RNF-07 | Rechazo de mesas de otro restaurante, pago atómico e inventario sin movimientos duplicados (`sales/tests.py`) |
| RF-07, RF-08 | Cambio de estado de pedido y comanda por cocina (`kitchen/tests.py`) |
| RF-09, RF-10, RF-11, RF-12 | Monto exacto, estado cobrable, cierre, cambio de mesa y reversión si falta inventario (`sales/tests.py`) |
| RF-14, RNF-06 | Reporte limitado al restaurante y generación de PDF (`reports/tests.py`) |

RF-04 y RF-13 aún requieren casos específicos de administración de mesas e inventario. RNF-02 requiere ejecutar las migraciones y pruebas de integración contra una instancia MySQL del entorno destino; la suite local usa SQLite en memoria.

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

- Crear formularios CRUD HTML completos además de la API.
- Incorporar multi-tenant real para SaaS por restaurante/sucursal.
- Agregar impresión térmica ESC/POS.
- Añadir WebSockets para cocina en tiempo real.
