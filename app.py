import os, json, secrets
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
DATA = Path("data"); UPLOADS = Path("static/uploads")
DATA.mkdir(exist_ok=True); UPLOADS.mkdir(parents=True, exist_ok=True)
PRODUCTS_FILE = DATA / "products.json"
ORDERS_FILE = DATA / "orders.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "UrbanSecure2026@#")
ALLOWED = {"png", "jpg", "jpeg", "webp", "gif"}

WILAYAS = [
("Adrar",1100,600),("Chlef",700,400),("Laghouat",900,500),("Oum El Bouaghi",800,400),("Batna",800,400),
("Béjaïa",700,400),("Biskra",900,500),("Béchar",1100,600),("Blida",500,250),("Bouira",650,400),
("Tamanrasset",1300,800),("Tébessa",800,500),("Tlemcen",800,400),("Tiaret",800,400),("Tizi Ouzou",650,400),
("Alger",400,200),("Djelfa",900,500),("Jijel",700,400),("Sétif",700,400),("Saïda",800,400),
("Skikda",700,400),("Sidi Bel Abbès",700,400),("Annaba",700,400),("Guelma",800,400),("Constantine",700,400),
("Médéa",600,400),("Mostaganem",700,400),("M'Sila",800,500),("Mascara",700,400),("Ouargla",1000,500),
("Oran",700,400),("El Bayadh",1000,500),("Illizi",1300,600),("Bordj Bou Arréridj",700,400),("Boumerdès",600,350),
("El Tarf",800,400),("Tindouf",1300,600),("Tissemsilt",800,400),("El Oued",900,500),("Khenchela",800,500),
("Souk Ahras",800,500),("Tipaza",600,350),("Mila",700,400),("Aïn Defla",600,400),("Naâma",1000,500),
("Aïn Témouchent",700,500),("Ghardaïa",1000,500),("Relizane",700,400),("Timimoun",1300,600),("Bordj Badji Mokhtar",1300,600),
("Ouled Djellal",900,500),("Béni Abbès",1300,0),("In Salah",1300,600),("In Guezzam",1300,600),("Touggourt",900,0),
("Djanet",1300,600),("El M'Ghair",900,0),("El Meniaa",1000,500)
]
# Commune names are deliberately entered by the customer to avoid presenting an incomplete or inaccurate list.
# This can be replaced with a verified official commune dataset for autocomplete.
def load_json(path):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return []
def save_json(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("admin"): return redirect(url_for("admin_login"))
        return fn(*a, **kw)
    return wrapper

@app.context_processor
def globals_for_templates():
    return {"wilayas": WILAYAS}

@app.route("/")
def home():
    products = load_json(PRODUCTS_FILE)
    return render_template("index.html", products=products)

@app.route("/order", methods=["POST"])
def order():
    data = {k: (request.form.get(k) or "").strip() for k in ["name","phone","wilaya","commune","delivery","address","note"]}
    if not data["name"] or not data["phone"] or not data["wilaya"] or not data["commune"] or data["delivery"] not in ("home","desk"):
        flash("Veuillez remplir les champs obligatoires.", "error")
        return redirect(url_for("home") + "#commande")
    order_id = secrets.token_hex(4).upper()
    orders = load_json(ORDERS_FILE)
    orders.append({"id":order_id, **data, "items":request.form.get("items",""), "created_at":__import__("datetime").datetime.now().isoformat(timespec="minutes"), "status":"Nouveau"})
    save_json(ORDERS_FILE, orders)
    return render_template("thanks.html", name=data["name"], order_id=order_id)

@app.route("/admin", methods=["GET","POST"])
def admin_login():
    if session.get("admin"): return redirect(url_for("dashboard"))
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password",""), ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("dashboard"))
        flash("Mot de passe incorrect.", "error")
    return render_template("login.html")

@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin/dashboard")
@admin_required
def dashboard():
    return render_template("dashboard.html", products=load_json(PRODUCTS_FILE), orders=load_json(ORDERS_FILE))

@app.route("/admin/product", methods=["POST"])
@admin_required
def add_product():
    name = (request.form.get("name") or "").strip()
    price = (request.form.get("price") or "").strip()
    description = (request.form.get("description") or "").strip()
    images = request.files.getlist("images")
    if not name or not price:
        flash("Le nom et le prix sont obligatoires.", "error")
        return redirect(url_for("dashboard"))
    saved = []
    for image in images[:8]:
        if image and image.filename and "." in image.filename:
            ext = image.filename.rsplit(".",1)[1].lower()
            if ext in ALLOWED:
                filename = secrets.token_hex(8) + "_" + secure_filename(image.filename)
                image.save(UPLOADS / filename)
                saved.append("/static/uploads/" + filename)
    products = load_json(PRODUCTS_FILE)
    products.append({"id":secrets.token_hex(5), "name":name, "price":price, "description":description, "images":saved})
    save_json(PRODUCTS_FILE, products)
    flash("Produit ajouté avec succès.", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin/product/<product_id>/delete", methods=["POST"])
@admin_required
def delete_product(product_id):
    products = load_json(PRODUCTS_FILE)
    save_json(PRODUCTS_FILE, [p for p in products if p["id"] != product_id])
    flash("Produit supprimé.", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin/order/<order_id>/status", methods=["POST"])
@admin_required
def update_order(order_id):
    orders = load_json(ORDERS_FILE)
    for o in orders:
        if o["id"] == order_id: o["status"] = request.form.get("status","Nouveau")
    save_json(ORDERS_FILE, orders)
    return redirect(url_for("dashboard"))

@app.route("/health")
def health(): return jsonify(status="ok")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
