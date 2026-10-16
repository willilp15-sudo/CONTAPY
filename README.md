# Wiltech ContaPY Web — base de migración V1.3

**Estado: base web implementada, NO sistema tributario completo ni apto para presentación ante DNIT.**

## Incluido
Flask + SQLAlchemy, PostgreSQL, migración Alembic inicial, autenticación con contraseñas hasheadas, roles admin/contador, acceso por contribuyente, protección CSRF, auditoría de altas, alta manual de compras/ventas, obligaciones configurables, resumen mensual, CSV de control y PDF A4 horizontal. UI responsive. Migrador opcional SQLite V1.3 → PostgreSQL.

## No incluido
Importación XML SIFEN validada, padrón DNIT integrado, archivos RG 90, cálculo definitivo IVA/IRE/IRP, asientos de partida doble, conciliación, 2FA, rate limiting, restauración automatizada, pruebas de seguridad independientes. **No presentar los CSV/PDF como declaraciones.**

## Desarrollo local
1. Instalar Python 3.11+ y PostgreSQL 15+; crear base y usuario con privilegios limitados.
2. `python -m venv .venv` y activar entorno.
3. `pip install -r requirements.txt`.
4. Copiar `.env.example` a `.env` y cargar variables en el entorno (`python-dotenv` no sustituye una configuración segura de producción).
5. `flask --app app db upgrade`.
6. `ADMIN_USERNAME=admin ADMIN_PASSWORD='contraseña-larga-unica' flask --app app create-admin` (en Windows usar variables de entorno PowerShell).
7. `flask --app app run` para desarrollo solamente.

## Render y GitHub
1. Crear repositorio privado GitHub; subir solo archivos del proyecto. **Nunca subir `.env`, claves o bases de datos.**
2. En Render, crear Blueprint desde el repositorio usando `render.yaml`. Confirmar disponibilidad/precio de los planes indicados antes de desplegar.
3. Render creará web + PostgreSQL. La variable `SECRET_KEY` se genera, `DATABASE_URL` proviene de PostgreSQL, HTTPS está gestionado por Render.
4. En consola Shell/Job de Render, configurar temporalmente `ADMIN_USERNAME` y `ADMIN_PASSWORD` seguros y ejecutar `flask --app app create-admin`. Retirar `ADMIN_PASSWORD` después.
5. Probar accesos, roles, CSRF, aislamiento por empresa y backups antes de datos reales.

**IMPORTANTE:** Render no necesariamente incluye Shell en todos los planes. Si no hay Shell, ejecutar el comando de administración como Job de una sola ejecución con credenciales configuradas de forma segura; no exponer una ruta web de creación de admin.

## Migración de SQLite V1.3
1. Respaldar `contapy.db` (cerrar app local y usar copia consistente de SQLite).
2. Ejecutar `flask --app app db upgrade` en destino.
3. Desde entorno seguro con `DATABASE_URL` de PostgreSQL, ejecutar `python scripts/import_legacy.py /ruta/contapy.db`.
4. Comparar recuentos y totales por contribuyente, períodos y tipos. El script omite comprobantes con claves duplicadas, pero no hace una conciliación fiscal completa. No migra contraseñas ni historial de auditoría original.
5. Mantener el SQLite original en archivo cifrado. No subirlo a GitHub.

## Seguridad operativa pendiente antes de producción
Configurar copias automáticas y ensayar restauración, monitoreo, control de intentos de login, MFA, segregación de roles por operación, validación fiscal y auditoría de ediciones. La implementación actual permite que cualquier usuario asignado registre documentos en su empresa. Evitar datos reales hasta finalizar controles.
