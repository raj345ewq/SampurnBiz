from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
import sqlite3
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey123'  # Replace with a secure random key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# User Model for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        return User(id=user[0], username=user[1], password=user[2])
    return None

# Function to create the database tables and insert the default admin user
def create_tables():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Create Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    password TEXT NOT NULL)''')
    
    # Create Bills table
    c.execute('''CREATE TABLE IF NOT EXISTS bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name TEXT NOT NULL,
                    customer_number TEXT NOT NULL,
                    total REAL NOT NULL)''')
    
    # Create Inventory table
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    barcode TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL)''')
    
    # Insert default user if not exists
    c.execute("SELECT * FROM users WHERE username=? AND password=?", ("admin", "admin123"))
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", "admin123"))
        print("Default user (admin/admin123) created.")
    
    conn.commit()
    conn.close()

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Connect to the database to check for user
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        
        if user:
            user_obj = User(id=user[0], username=user[1], password=user[2])
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials, please try again.', 'danger')
    
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Fetch bills for dashboard display
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM bills")
    bills = c.fetchall()
    conn.close()
    
    return render_template('dashboard.html', bills=bills)

@app.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    if request.method == 'POST':
        name = request.form['name']
        barcode = request.form['barcode']
        price = request.form['price']
        quantity = request.form['quantity']
        
        # Insert the new item into the inventory table
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO inventory (name, barcode, price, quantity) VALUES (?, ?, ?, ?)", 
                  (name, barcode, price, quantity))
        conn.commit()
        conn.close()

        return redirect(url_for('inventory'))
    
    # Fetch all items from the inventory table
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM inventory")
    items = c.fetchall()
    conn.close()
    
    return render_template('inventory.html', items=items)

@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if request.method == 'POST':
        name = request.form['editProductName']
        barcode = request.form['editProductBarcode']
        price = request.form['editProductPrice']
        quantity = request.form['editProductQuantity']
        
        # Update the product details
        c.execute("UPDATE inventory SET name=?, barcode=?, price=?, quantity=? WHERE id=?", 
                  (name, barcode, price, quantity, id))
        conn.commit()
        conn.close()

        return redirect(url_for('inventory'))

    # Fetch the product to be edited
    c.execute("SELECT * FROM inventory WHERE id=?", (id,))
    product = c.fetchone()
    conn.close()

    return render_template('edit_product.html', product=product)

@app.route('/billing', methods=['GET', 'POST'])
@login_required
def billing():
    if request.method == 'POST':
        customer_name = request.form['customer_name']
        customer_number = request.form['customer_number']
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO bills (customer_name, customer_number, total) VALUES (?, ?, ?)", 
                  (customer_name, customer_number, 0))
        bill_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return redirect(url_for('generate_bill', bill_id=bill_id))
    
    return render_template('billing.html')

@app.route('/generate_bill/<int:bill_id>')
@login_required
def generate_bill(bill_id):
    # Fetch the bill details
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM bills WHERE id=?", (bill_id,))
    bill = c.fetchone()

    if not bill:
        flash("Bill not found.", "danger")
        return redirect(url_for('dashboard'))

    customer_name, customer_number = bill[1], bill[2]
    pdf_path = f"generated_bills/bill_{bill_id}.pdf"

    if not os.path.exists('generated_bills'):
        os.makedirs('generated_bills')

    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.drawString(100, 750, f"Invoice for {customer_name}")
    c.save()

    conn.close()

    return send_file(pdf_path, as_attachment=True)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Initialize database and start Flask app
if __name__ == '__main__':
    create_tables()
    app.run(debug=True)
