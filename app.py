from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime
import os

# ===== Configuración básica =====
app = Flask(__name__)
CORS(app)  # Permite que tu frontend llame al backend desde otro dominio

DB_NAME = "tienda.db"

# ===== Crear base de datos y tablas si no existen =====
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        es_admin INTEGER DEFAULT 0
    )''')
    # Productos
    c.execute('''CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        categoria TEXT,
        precio REAL,
        stock INTEGER,
        talla TEXT,
        marca TEXT,
        img TEXT
    )''')
    # Pedidos
    c.execute('''CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        total REAL,
        fecha TEXT,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
    )''')
    # Pedidos-productos
    c.execute('''CREATE TABLE IF NOT EXISTS pedido_productos (
        pedido_id INTEGER,
        producto_id INTEGER,
        cantidad INTEGER,
        FOREIGN KEY(pedido_id) REFERENCES pedidos(id),
        FOREIGN KEY(producto_id) REFERENCES productos(id)
    )''')
    # Comentarios
    c.execute('''CREATE TABLE IF NOT EXISTS comentarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER,
        usuario_id INTEGER,
        texto TEXT,
        foto TEXT,
        FOREIGN KEY(producto_id) REFERENCES productos(id),
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
    )''')
    conn.commit()
    conn.close()

init_db()

# ===== Rutas API =====

# --- Registro de usuario ---
@app.route("/api/registrar", methods=["POST"])
def registrar():
    data = request.json
    nombre = data.get("nombre")
    email = data.get("email")
    password = data.get("password")
    es_admin = data.get("es_admin", 0)  # Solo tu puedes poner 1 para admin

    if not nombre or not email or not password:
        return jsonify({"error":"Faltan campos"}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO usuarios (nombre,email,password,es_admin) VALUES (?,?,?,?)",
                  (nombre,email,password,es_admin))
        conn.commit()
        return jsonify({"msg":"Usuario registrado"})
    except sqlite3.IntegrityError:
        return jsonify({"error":"Email ya registrado"}), 400
    finally:
        conn.close()

# --- Login ---
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id,nombre,email,es_admin FROM usuarios WHERE email=? AND password=?",(email,password))
    user = c.fetchone()
    conn.close()
    if user:
        return jsonify({"id":user[0],"nombre":user[1],"email":user[2],"es_admin":user[3]})
    else:
        return jsonify({"error":"Usuario o contraseña incorrecta"}), 401

# --- Obtener productos ---
@app.route("/api/productos", methods=["GET"])
def obtener_productos():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM productos")
    prods = c.fetchall()
    conn.close()
    lista = []
    for p in prods:
        lista.append({
            "id":p[0],
            "nombre":p[1],
            "categoria":p[2],
            "precio":p[3],
            "stock":p[4],
            "talla":p[5],
            "marca":p[6],
            "img":p[7]
        })
    return jsonify(lista)

# --- Subir producto (solo admin) ---
@app.route("/api/productos", methods=["POST"])
def subir_producto():
    data = request.json
    admin_id = data.get("admin_id")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT es_admin FROM usuarios WHERE id=?",(admin_id,))
    r = c.fetchone()
    if not r or r[0]==0:
        conn.close()
        return jsonify({"error":"No autorizado"}), 403

    c.execute('''INSERT INTO productos 
        (nombre,categoria,precio,stock,talla,marca,img) VALUES (?,?,?,?,?,?,?)''',
              (data["nombre"],data.get("categoria",""),data.get("precio",0),
               data.get("stock",0),data.get("talla",""),data.get("marca",""),data.get("img","")))
    conn.commit()
    conn.close()
    return jsonify({"msg":"Producto subido"})

# --- Crear pedido ---
@app.route("/api/pedidos", methods=["POST"])
def crear_pedido():
    data = request.json
    usuario_id = data.get("usuario_id")
    productos_pedido = data.get("productos")  # [{"id":1,"cantidad":2}, ...]
    total = sum([p.get("precio",0)*p.get("cantidad",1) for p in productos_pedido])
    fecha = datetime.datetime.now().isoformat()

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO pedidos (usuario_id,total,fecha) VALUES (?,?,?)",
              (usuario_id,total,fecha))
    pedido_id = c.lastrowid
    for p in productos_pedido:
        c.execute("INSERT INTO pedido_productos (pedido_id,producto_id,cantidad) VALUES (?,?,?)",
                  (pedido_id,p["id"],p.get("cantidad",1)))
    conn.commit()
    conn.close()
    return jsonify({"msg":"Pedido creado","total":total})

# --- Comentarios ---
@app.route("/api/comentarios", methods=["POST"])
def crear_comentario():
    data = request.json
    usuario_id = data.get("usuario_id")
    producto_id = data.get("producto_id")
    texto = data.get("texto","")
    foto = data.get("foto","")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO comentarios (producto_id,usuario_id,texto,foto) VALUES (?,?,?,?)",
              (producto_id,usuario_id,texto,foto))
    conn.commit()
    conn.close()
    return jsonify({"msg":"Comentario creado"})

@app.route("/api/comentarios/<int:producto_id>", methods=["GET"])
def obtener_comentarios(producto_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT c.texto,c.foto,u.nombre FROM comentarios c JOIN usuarios u ON c.usuario_id=u.id WHERE producto_id=?",(producto_id,))
    coms = [{"texto":x[0],"foto":x[1],"usuario":x[2]} for x in c.fetchall()]
    conn.close()
    return jsonify(coms)

# ===== Ejecutar app =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
