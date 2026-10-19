"""Servidor Flask de Cumbre Digital MX 2026: registro de asistentes en SQLite."""
import os
import re
import sqlite3

from flask import Flask, g, redirect, render_template, request, url_for

# La base de datos vive en la raíz del proyecto
RUTA_BD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evento.db")

AREAS = ["Tecnología", "Marketing", "Negocios", "Emprendimiento"]
REGEX_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")

app = Flask(__name__)


# ===== Base de datos =====
def obtener_bd():
    """Devuelve la conexión SQLite de la petición actual."""
    if "bd" not in g:
        g.bd = sqlite3.connect(RUTA_BD)
        g.bd.row_factory = sqlite3.Row
    return g.bd


@app.teardown_appcontext
def cerrar_bd(_error):
    bd = g.pop("bd", None)
    if bd is not None:
        bd.close()


def iniciar_bd():
    """Crea la tabla de asistentes si todavía no existe."""
    with sqlite3.connect(RUTA_BD) as bd:
        bd.execute(
            """
            CREATE TABLE IF NOT EXISTS asistentes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre         TEXT NOT NULL,
                email          TEXT NOT NULL UNIQUE,
                empresa        TEXT NOT NULL,
                area_interes   TEXT NOT NULL CHECK (area_interes IN
                               ('Tecnología','Marketing','Negocios','Emprendimiento')),
                fecha_registro TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


iniciar_bd()


# ===== Utilidades =====
@app.template_filter("numero_registro")
def numero_registro(id_asistente):
    """Convierte el id en el formato REG-0001."""
    return f"REG-{id_asistente:04d}"


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
        try:
            bd = obtener_bd()
            cursor = bd.execute(
                "INSERT INTO asistentes (nombre, email, empresa, area_interes) VALUES (?, ?, ?, ?)",
                (datos["nombre"], datos["email"], datos["empresa"], datos["area"]),
            )
            bd.commit()
            return redirect(url_for("confirmacion", id_asistente=cursor.lastrowid))
        except sqlite3.IntegrityError:
            errores["email"] = "Este correo ya está registrado en el evento."

    return render_template("index.html", areas=AREAS, datos=datos, errores=errores), 400


@app.get("/confirmacion/<int:id_asistente>")
def confirmacion(id_asistente):
    asistente = obtener_bd().execute(
        "SELECT id, nombre FROM asistentes WHERE id = ?", (id_asistente,)
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
