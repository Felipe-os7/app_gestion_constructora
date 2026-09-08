# Migración de SQLite a MySQL — app_gestion

## Qué se cambió

1. **`app_gestion/settings.py`**
   - `DATABASES` ahora usa `django.db.backends.mysql` en vez de `sqlite3`.
   - Las credenciales (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`) y el `SECRET_KEY`/`DEBUG` se leen desde variables de entorno (archivo `.env`), en vez de estar escritas directamente en el código.
   - Se agregó `charset: utf8mb4` para soportar tildes, ñ y emojis correctamente.

2. **`requirements.txt`**
   - Se reemplazó `psycopg2-binary` (driver de PostgreSQL, no se usaba) por `mysqlclient` (driver de MySQL).
   - Se agregó `python-dotenv` para cargar el archivo `.env`.

3. **Archivos nuevos**
   - `.env.example`: plantilla de variables de entorno. Cópialo como `.env` y completa tus datos reales.
   - `.gitignore`: evita subir `.env` y `db.sqlite3` al repositorio.
   - `datadump.json`: **volcado de tus datos actuales** (38 registros: usuarios, proyectos, cuadrillas, integrantes, cambios y solicitudes de reasignación), exportado desde tu `db.sqlite3` original, listo para cargar en MySQL.
   - `db.sqlite3.backup`: respaldo de tu base SQLite original, por si necesitas volver atrás.

No fue necesario tocar `models.py` ni ninguna vista: el proyecto no usaba SQL crudo, `JSONField` ni nada específico de SQLite, así que es 100% compatible con MySQL tal cual estaba.

## Pasos para completar la migración

### 1. Instalar dependencias del sistema (driver MySQL)

`mysqlclient` necesita las librerías de desarrollo de MySQL/MariaDB antes de compilarse:

```bash
# Ubuntu/Debian
sudo apt-get install -y python3-dev default-libmysqlclient-dev build-essential pkg-config

# macOS (con Homebrew)
brew install mysql-client pkg-config
```

### 2. Crear la base de datos en MySQL

```sql
CREATE DATABASE app_gestion CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'app_gestion_user'@'localhost' IDENTIFIED BY 'tu_password_segura';
GRANT ALL PRIVILEGES ON app_gestion.* TO 'app_gestion_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Configurar el archivo `.env`

```bash
cp .env.example .env
```

Edita `.env` con tus datos reales:

```
DJANGO_SECRET_KEY=genera-una-clave-nueva-y-segura
DJANGO_DEBUG=True
DB_NAME=app_gestion
DB_USER=app_gestion_user
DB_PASSWORD=tu_password_segura
DB_HOST=localhost
DB_PORT=3306
```

Puedes generar un `SECRET_KEY` nuevo con:
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4. Instalar dependencias de Python

```bash
pip install -r requirements.txt
```

### 5. Crear las tablas en MySQL

```bash
python manage.py migrate
```

### 6. Cargar tus datos existentes

```bash
python manage.py loaddata datadump.json
```

Verifica que todo llegó bien:
```bash
python manage.py shell -c "from core.models import Proyecto, Cuadrilla, Integrante; print(Proyecto.objects.count(), Cuadrilla.objects.count(), Integrante.objects.count())"
```

### 7. Probar la aplicación

```bash
python manage.py runserver
```

Revisa el login, el dashboard y que los datos de proyectos/cuadrillas/integrantes se vean correctamente.

## Notas para producción (Render u otro hosting)

- En el panel de variables de entorno de tu hosting, define `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` y `DJANGO_SECRET_KEY` con los valores del proveedor de MySQL que uses (por ejemplo PlanetScale, un MySQL gestionado en Render, RDS de AWS, etc.). No hace falta tocar el código.
- Pon `DJANGO_DEBUG=False` en producción.
- Si tu proveedor de MySQL exige SSL, agrega en `settings.py`, dentro de `OPTIONS`, algo como `'ssl': {'ca': '/ruta/al/cert.pem'}` (el proveedor te da el certificado).
- Elimina o no subas `db.sqlite3.backup` a producción.
