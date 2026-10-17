from flask import Flask, render_template, request, redirect, session, flash, url_for
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "crochet_by_3_sisters_secret_key_2026"
app.jinja_env.globals.update(enumerate=enumerate)

# File upload configuration
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Database helpers
def get_products_db_connection():
    db_path = os.path.join(app.root_path, "products.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_users_db_connection():
    db_path = os.path.join(app.root_path, "users.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.context_processor
def inject_global_data():
    cart = session.get('cart', [])
    cart_count = sum(item.get('quantity', 1) for item in cart)
    country = session.get('country', 'India')
    return dict(cart_count=cart_count, current_country=country)

# Country Selector
@app.route('/set_country', methods=['POST'])
@app.route('/set_country/<country>', methods=['GET'])
def set_country(country=None):
    selected_country = country or request.form.get('country')
    if selected_country in ['India', 'UK']:
        session['country'] = selected_country
        session.modified = True
    return redirect(request.referrer or url_for('home'))

# Home Page
@app.route('/')
def home():
    return render_template("home.html")

# Meet the Makers
@app.route('/makers')
def makers():
    return render_template("makers.html")

# Category Listing
@app.route('/<category>')
def show_products(category):
    cat_clean = category.lower().strip()
    valid_categories = ['earrings', 'bracelets', 'keychains', 'flowers', 'accessories']
    
    if cat_clean not in valid_categories:
        # Fallback if someone hits an unknown URL
        return redirect('/')

    conn = get_products_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE LOWER(category) = ? ORDER BY id ASC", (cat_clean,))
    rows = cursor.fetchall()
    conn.close()

    user_country = session.get('country', 'India')
    products = []
    for row in rows:
        p = dict(row)
        if user_country == 'UK':
            p['display_price'] = f"£ {p['price_gbp']:.2f}"
            p['price'] = p['price_gbp']
        else:
            p['display_price'] = f"₹ {p['price_inr']:.2f}"
            p['price'] = p['price_inr']

        img = p['image1'] if p['image1'] else 'logo.jpg'
        p['image_filename'] = img.replace('static/', '').replace('static\\', '')
        products.append(p)

    category_titles = {
        'earrings': 'Handcrafted Earrings',
        'bracelets': 'Artisan Bracelets',
        'keychains': 'Crochet Keychains',
        'flowers': 'Flowers & Home Decor',
        'accessories': 'Hair & Fashion Accessories'
    }

    return render_template(
        "product_list.html",
        category=category_titles.get(cat_clean, cat_clean.title()),
        category_slug=cat_clean,
        products=products,
        country=user_country
    )

# Product Detail View
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_products_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        flash("Product not found.")
        return redirect('/')

    product = dict(row)
    user_country = session.get('country', 'India')
    if user_country == 'UK':
        product['display_price'] = f"£ {product['price_gbp']:.2f}"
        product['price'] = product['price_gbp']
    else:
        product['display_price'] = f"₹ {product['price_inr']:.2f}"
        product['price'] = product['price_inr']

    # Gallery images
    images = []
    for k in ['image1', 'image2', 'image3', 'image4']:
        if product.get(k):
            clean_name = product[k].replace('static/', '').replace('static\\', '')
            images.append(clean_name)
    if not images:
        images.append('logo.jpg')
    product['gallery_images'] = images
    product['primary_image'] = images[0]

    if product.get('video'):
        product['video_filename'] = product['video'].replace('static/', '').replace('static\\', '')
    else:
        product['video_filename'] = None

    # Related items
    cursor.execute("SELECT * FROM products WHERE category = ? AND id != ? LIMIT 3", (product['category'], product_id))
    related_rows = cursor.fetchall()
    conn.close()

    related_products = []
    for r in related_rows:
        rp = dict(r)
        if user_country == 'UK':
            rp['display_price'] = f"£ {rp['price_gbp']:.2f}"
        else:
            rp['display_price'] = f"₹ {rp['price_inr']:.2f}"
        img = rp['image1'] if rp['image1'] else 'logo.jpg'
        rp['image_filename'] = img.replace('static/', '').replace('static\\', '')
        related_products.append(rp)

    return render_template(
        "product_detail.html",
        product=product,
        related=related_products,
        country=user_country
    )

# Cart Management
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = request.form.get('product_id')
    try:
        quantity = int(request.form.get('quantity', 1))
        if quantity < 1:
            quantity = 1
    except ValueError:
        quantity = 1

    conn = get_products_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        flash("Product not found.")
        return redirect(request.referrer or '/')

    p = dict(row)
    if 'cart' not in session:
        session['cart'] = []

    cart = session['cart']
    found = False
    for item in cart:
        if item['id'] == int(product_id):
            item['quantity'] += quantity
            found = True
            break

    if not found:
        img = p['image1'] if p['image1'] else 'logo.jpg'
        cart.append({
            'id': p['id'],
            'name': p['name'],
            'category': p['category'],
            'price_inr': p['price_inr'],
            'price_gbp': p['price_gbp'],
            'image_filename': img.replace('static/', '').replace('static\\', ''),
            'quantity': quantity
        })

    session['cart'] = cart
    session.modified = True
    flash(f"Added {p['name']} to your cart!")
    return redirect('/cart')

@app.route('/cart')
def cart():
    cart = session.get('cart', [])
    country = session.get('country', 'India')

    total = 0.0
    for item in cart:
        if country == 'UK':
            item['unit_price'] = item['price_gbp']
            item['display_price'] = f"£ {item['price_gbp']:.2f}"
            item_total = item['price_gbp'] * item['quantity']
            item['total_display'] = f"£ {item_total:.2f}"
        else:
            item['unit_price'] = item['price_inr']
            item['display_price'] = f"₹ {item['price_inr']:.2f}"
            item_total = item['price_inr'] * item['quantity']
            item['total_display'] = f"₹ {item_total:.2f}"
        total += item_total

    currency_symbol = '£' if country == 'UK' else '₹'
    total_display = f"{currency_symbol} {total:.2f}"

    return render_template(
        "cart.html",
        cart=cart,
        total=total,
        total_display=total_display,
        country=country
    )

@app.route('/update_cart', methods=['POST'])
def update_cart():
    cart = session.get('cart', [])
    for i in range(len(cart)):
        qty_key = f'quantity_{i}'
        if qty_key in request.form:
            try:
                new_qty = int(request.form[qty_key])
                if new_qty > 0:
                    cart[i]['quantity'] = new_qty
            except ValueError:
                pass
    session['cart'] = cart
    session.modified = True
    return redirect('/cart')

@app.route('/remove_from_cart/<int:item_index>')
def remove_from_cart(item_index):
    cart = session.get('cart', [])
    if 0 <= item_index < len(cart):
        removed = cart.pop(item_index)
        flash(f"Removed '{removed['name']}' from cart.")
    session['cart'] = cart
    session.modified = True
    return redirect('/cart')

# Checkout Flow
@app.route('/checkout_address', methods=['GET', 'POST'])
def checkout_address():
    cart = session.get('cart', [])
    if not cart:
        flash("Your cart is empty.")
        return redirect('/')

    if request.method == 'POST':
        session['order_details'] = {
            "name": request.form.get('name', ''),
            "address": request.form.get('address', ''),
            "contact": request.form.get('contact', ''),
            "email": request.form.get('email', '')
        }
        return redirect('/payment')

    user_data = None
    if session.get('user'):
        conn = get_users_db_connection()
        user_data = conn.execute('SELECT * FROM users WHERE email = ?', (session['user'],)).fetchone()
        conn.close()

    country = session.get('country', 'India')
    return render_template('checkout_address.html', user=user_data, country=country)

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    cart = session.get('cart', [])
    if not cart:
        return redirect('/')

    country = session.get('country', 'India')
    total = sum((item['price_gbp'] if country == 'UK' else item['price_inr']) * item['quantity'] for item in cart)
    currency_symbol = '£' if country == 'UK' else '₹'
    total_display = f"{currency_symbol} {total:.2f}"

    return render_template(
        "payment.html",
        total=total,
        total_display=total_display,
        country=country
    )

@app.route('/payment_success', methods=['POST'])
def payment_success():
    txn_id = request.form.get('upi_txn', '').strip()
    if not txn_id:
        return redirect('/payment_fail')

    import time
    order_id = f"CB3S-{int(time.time())}"
    cart = session.get('cart', [])
    customer = session.get('order_details', {})
    user_email = session.get('user', customer.get('email', ''))

    # Clear order sessions
    session.pop('cart', None)
    session.pop('order_details', None)

    return render_template(
        "payment_success.html",
        order_id=order_id,
        txn_id=txn_id,
        customer=customer,
        email=user_email
    )

@app.route('/payment_fail')
def payment_fail():
    return render_template('payment_fail.html')

# User Authentication
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        contact = request.form.get('contact')
        email = request.form.get('email')
        address = request.form.get('address')
        password = request.form.get('password')

        conn = get_users_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ? OR contact = ?', (email, contact))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            flash("Account already exists. Please login.")
            return redirect('/login')

        hashed_password = generate_password_hash(password)
        cursor.execute(
            'INSERT INTO users (name, contact, email, address, password) VALUES (?, ?, ?, ?, ?)',
            (name, contact, email, address, hashed_password)
        )
        conn.commit()
        conn.close()

        session['user'] = email
        flash("Welcome to Crochet by 3 Sisters!")
        return redirect('/')

    return render_template("signup.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')

        conn = get_users_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ? OR contact = ?', (identifier, identifier))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user'] = user['email']
            session['is_admin'] = (user['email'] in ["crochetby3sisters@gmail.com", "flavia.more.fm@gmail.com"])
            flash("Logged in successfully!")
            return redirect('/')
        else:
            flash("Invalid credentials. Please check your email and password.")
            return redirect('/login')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect('/')

# Admin product creation
@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if not session.get('is_admin'):
        flash("Administrator access required.")
        return redirect('/')

    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        price_inr = float(request.form.get('price_inr', 0))
        price_gbp = float(request.form.get('price_gbp', 0))
        description = request.form.get('description')
        length = request.form.get('length')
        height = request.form.get('height')
        width = request.form.get('width')
        weight = request.form.get('weight')
        material = request.form.get('material')

        images = []
        if 'images' in request.files:
            for img in request.files.getlist('images'):
                if img.filename:
                    filename = secure_filename(img.filename)
                    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    img.save(filepath)
                    images.append(f"static/uploads/{filename}")

        conn = get_products_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (
                name, category, price_inr, price_gbp, description,
                length, height, width, weight, material,
                image1, image2, image3, image4, rating, rating_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 5.0, 1)
        """, (
            name, category, price_inr, price_gbp, description,
            length, height, width, weight, material,
            images[0] if len(images) > 0 else None,
            images[1] if len(images) > 1 else None,
            images[2] if len(images) > 2 else None,
            images[3] if len(images) > 3 else None
        ))
        conn.commit()
        conn.close()

        flash(f"✅ Product '{name}' added successfully!")
        return redirect(f"/{category}")

    return render_template("add_product.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
