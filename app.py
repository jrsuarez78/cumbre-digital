"""Servidor Flask de Cumbre Digital MX 2026: registro de asistentes en PostgreSQL (Supabase)."""
import os
import re

import psycopg
from dotenv import load_dotenv
from flask import Flask, g, redirect, render_template, request, url_for
from psycopg.rows import dict_row

# En local lee el archivo .env; en Render usa la variable de entorno del panel
load_dotenv()
# Se limpia el valor por si al pegarlo en Render quedó con espacios, saltos de línea,
# comillas o el prefijo "DATABASE_URL=" copiado del archivo .env
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip().strip("\"'").strip()
if DATABASE_URL.startswith("DATABASE_URL="):
    DATABASE_URL = DATABASE_URL[len("DATABASE_URL="):].strip().strip("\"'").strip()
if not DATABASE_URL:
    raise RuntimeError(
        "Falta la variable DATABASE_URL. Defínela en tu archivo .env (ver .env.example) "
        "o en las variables de entorno del servidor."
    )

AREAS = ["Tecnología", "Marketing", "Negocios", "Emprendimiento"]
REGEX_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")

app = Flask(__name__)


# ===== Base de datos =====
def obtener_bd():
    """Devuelve la conexión PostgreSQL de la petición actual."""
    if "bd" not in g:
        g.bd = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return g.bd


@app.teardown_appcontext
def cerrar_bd(_error):
    bd = g.pop("bd", None)
    if bd is not None:
        bd.close()


# ===== Utilidades =====
@app.template_filter("fecha")
def formato_fecha(fecha):
    """Muestra la fecha de registro como 23/10/2026 14:30."""
    return fecha.strftime("%d/%m/%Y %H:%M") if fecha else ""


def validar(datos):
    """Devuelve un diccionario {campo: mensaje} con los errores encontrados."""
    errores = {}
    if not datos["nombre"]:
        errores["nombre"] = "Ingresa tu nombre completo."
    if not REGEX_EMAIL.match(datos["email"]):
        errores["email"] = "Ingresa un correo electrónico válido (ej. nombre@dominio.com)."
    if not datos["empresa"]:
        errores["empresa"] = "Ingresa el nombre de tu empresa u organización."
    if datos["area"] not in AREAS:
        errores["area"] = "Selecciona un área de interés."
    return errores


# ===== Rutas =====
@app.get("/")
def inicio():
    return render_template("index.html", areas=AREAS, datos={}, errores={})


@app.post("/registrar")
def registrar():
    datos = {
        "nombre": request.form.get("nombre", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
        "empresa": request.form.get("empresa", "").strip(),
        "area": request.form.get("area", "").strip(),
    }
    errores = validar(datos)

    if not errores:
        bd = obtener_bd()
        try:
            # Se reserva el id primero para guardar también el número REG-0001
            id_nuevo = bd.execute(
                "SELECT nextval(pg_get_serial_sequence('asistentes', 'id')) AS id"
            ).fetchone()["id"]
            bd.execute(
                "INSERT INTO asistentes (id, nombre, email, empresa, area_interes, numero_registro) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (id_nuevo, datos["nombre"], datos["email"], datos["empresa"], datos["area"],
                 f"REG-{id_nuevo:04d}"),
            )
            bd.commit()
            return redirect(url_for("confirmacion", id_asistente=id_nuevo))
        except psycopg.errors.UniqueViolation as e:
            bd.rollback()
            if e.diag.constraint_name != "asistentes_email_key":
                raise
            errores["email"] = "Este correo ya está registrado en el evento."

    return render_template("index.html", areas=AREAS, datos=datos, errores=errores), 400


@app.get("/confirmacion/<int:id_asistente>")
def confirmacion(id_asistente):
    asistente = obtener_bd().execute(
        "SELECT id, nombre, numero_registro FROM asistentes WHERE id = %s", (id_asistente,)
    ).fetchone()
    if asistente is None:
        return pagina_error(404, "No encontramos ese registro."), 404
    return render_template("confirmacion.html", asistente=asistente)


@app.get("/admin")
def admin():
    bd = obtener_bd()
    asistentes = bd.execute("SELECT * FROM asistentes ORDER BY id DESC").fetchall()
    por_area = bd.execute(
        "SELECT area_interes, COUNT(*) AS total FROM asistentes GROUP BY area_interes"
    ).fetchall()
    return render_template("admin.html", asistentes=asistentes, por_area=por_area)


@app.get("/salud")
def salud():
    return {"estado": "ok"}


# ===== Errores =====
def pagina_error(codigo, mensaje):
    return render_template("error.html", codigo=codigo, mensaje=mensaje)


@app.errorhandler(404)
def no_encontrado(_e):
    return pagina_error(404, "La página que buscas no existe."), 404


@app.errorhandler(500)
def error_servidor(_e):
    return pagina_error(500, "Ocurrió un problema en el servidor. Intenta de nuevo en unos minutos."), 500


if __name__ == "__main__":
    app.run(debug=True)
