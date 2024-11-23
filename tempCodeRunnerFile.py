from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
import sqlite3
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
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

# Home Route (Login)
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

# Dashboard Route
@app.route('/dashboard')
@login_required
def dashboard():
    # Display the list of generated bills
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM bills")
    bills = c.fetchall()
    conn.close()
    
    return render_template('dashboard.html', bills=bills)

# Inventory Route
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

        # Redirect back to the inventory page to see the new item
        return redirect(url_for('inventory'))
    
    # Fetch all items from the inventory table
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM inventory")
    items = c.fetchall()
    conn.close()
    
    return render_template('inventory.html', items=items)



@app.route('/inventory/edit', methods=['POST'])
@login_required
def edit_inventory():
    item_id = request.form['item_id']
    name = request.form['name']
    barcode = request.form['barcode']
    price = request.form['price']
    quantity = request.form['quantity']
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Update the inventory item with the new data
    c.execute("UPDATE inventory SET name=?, barcode=?, price=?, quantity=? WHERE id=?",
              (name, barcode, price, quantity, item_id))
    conn.commit()
    conn.close()
    
    flash("Item updated successfully!", "success")
    return redirect(url_for('inventory'))

# Billing Route
@app.route('/billing', methods=['GET', 'POST'])
@login_required
def billing():
    if request.method == 'POST':
        customer_name = request.form['customer_name']
        customer_number = request.form['customer_number']
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO bills (customer_name, customer_number, total) VALUES (?, ?, ?)", (customer_name, customer_number, 0))
        bill_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return redirect(url_for('generate_bill', bill_id=bill_id))
    
    return render_template('billing.html')

# Generate PDF Bill Route
@app.route('/generate_bill/<int:bill_id>')
@login_required
def generate_bill(bill_id):
    # Fetch the bill details from the database
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM bills WHERE id=?", (bill_id,))
    bill = c.fetchone()
    conn.close()

    if not bill:
        flash("Bill not found.", "danger")
        return redirect(url_for('dashboard'))

    customer_name = bill[1]
    customer_number = bill[2]
    
    # Fetch the items in the bill (if you have a relation to products or inventory)
    c.execute("SELECT * FROM bill_items WHERE bill_id=?", (bill_id,))
    items = c.fetchall()
    
    # Create PDF
    pdf_path = f"generated_bills/bill_{bill_id}.pdf"
    if not os.path.exists('generated_bills'):
        os.makedirs('generated_bills')

    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(100, 750, f"Invoice for Customer: {customer_name}")
    c.drawString(100, 730, f"Customer Number: {customer_number}")
    
    y_position = 710  # starting y position for the table
    c.drawString(100, y_position, "ID | Name | Price | Quantity | Total")
    y_position -= 20
    
    total_amount = 0
    for item in items:
        item_id, item_name, item_price, item_quantity = item[1], item[2], item[3], item[4]
        total = item_price * item_quantity
        c.drawString(100, y_position, f"{item_id} | {item_name} | {item_price} | {item_quantity} | {total}")
        total_amount += total
        y_position -= 20
    
    c.drawString(100, y_position - 20, f"Total Amount: {total_amount}")
    
    # Save the PDF
    c.save()

    # Return the PDF file for download
    return send_file(pdf_path, as_attachment=True)


# Logout Route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

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

# Function to create the database tables (users, inventory, etc.)
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
    
    conn.commit()
    conn.close()

# Run this once to initialize the database
create_tables()

if __name__ == '__main__':
    app.run(debug=True)
