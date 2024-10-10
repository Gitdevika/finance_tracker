from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import calendar


app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL Configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '12345'
app.config['MYSQL_DB'] = 'finance_tracker'

mysql = MySQL(app)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Gmail's SMTP server
app.config['MAIL_PORT'] = 587  # Port used for TLS
app.config['MAIL_USE_TLS'] = True  # Enable TLS (Transport Layer Security)
app.config['MAIL_USERNAME'] = 'devthedev38@gmail.com'  # Your email address
app.config['MAIL_PASSWORD'] = 'devika@ashadam'  # Your email account password
app.config['MAIL_DEFAULT_SENDER'] = 'financetrackeradmin@gmail.com'  # The email address you want to send from


mail = Mail(app)

# Register Route
@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Insert into database
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (email, username, password) VALUES (%s, %s, %s)", (email, username, hashed_password))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('login_register'))

# Login Route
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE username = %s", [username])
    user = cur.fetchone()
    cur.close()

    if user and check_password_hash(user[3], password):
        session['username'] = username
        session['email'] = user[1]  # Store email in session for notifications
        return redirect(url_for('welcome'))
    else:
        return "Invalid username or password"

# Route to display both login and register forms
@app.route('/')
@app.route('/login_register')
def login_register():
    return render_template('login_register.html')

# Welcome route (check if income has been submitted for the current month)
@app.route('/welcome')
def welcome():
    if 'username' in session:
        username = session['username']
        
        # Get the current month
        current_month = datetime.datetime.now().strftime("%B")

        # Check if income is already submitted for the current month
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT income_amount FROM income 
            INNER JOIN users ON income.user_id = users.user_id 
            WHERE users.username = %s AND income.month = %s
        """, (username, current_month))
        
        income_record = cur.fetchone()
        cur.close()

        # If income is already submitted, redirect to expenses page
        if income_record:
            return redirect(url_for('expenses'))

        # Otherwise, ask for income input
        return render_template('welcome.html', username=username)
    else:
        return redirect(url_for('login_register'))

# Handle income submission with automatic month detection
@app.route('/add_income', methods=['POST'])
def add_income():
    if 'username' not in session:
        return redirect(url_for('login_register'))
    
    income_amount = request.form['income_amount']
    
    # Automatically get the current month
    current_month = datetime.datetime.now().strftime("%B")
    
    # Get user_id from session (fetch from DB using username)
    cur = mysql.connection.cursor()
    cur.execute("SELECT user_id FROM users WHERE username = %s", [session['username']])
    user = cur.fetchone()
    user_id = user[0]
    
    # Insert income into income table
    cur.execute("INSERT INTO income (user_id, income_amount, month) VALUES (%s, %s, %s)", (user_id, income_amount, current_month))
    mysql.connection.commit()
    cur.close()

    # Redirect to the expenses page
    return redirect(url_for('expenses'))

# Expenses Route to display calendar and buttons
@app.route('/expenses')
def expenses():
    # Get the current date
    now = datetime.datetime.now()
    current_year = now.year
    current_month = now.month

    # Get the month name and number of days in the current month
    month_name = calendar.month_name[current_month]
    _, num_days = calendar.monthrange(current_year, current_month)

    # Pass the month name and number of days to the template
    return render_template('calendar.html', month_name=month_name, num_days=num_days)

# Route to handle the addition of expenses
@app.route('/add_expense/<int:day>', methods=['GET', 'POST'])
def add_expense(day):
    if 'username' not in session:
        return redirect(url_for('login_register'))
    
    if request.method == 'POST':
        amount = request.form['amount']
        category = request.form['category']
        selected_date = f"{datetime.datetime.now().year}-{datetime.datetime.now().month:02d}-{day:02d}"

        # Get the current user's user_id
        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM users WHERE username = %s", [session['username']])
        user = cur.fetchone()
        user_id = user[0]

        # Insert the expense data into the expense table
        cur.execute("INSERT INTO expenses (user_id, amount, category, date) VALUES (%s, %s, %s, %s)", 
                    (user_id, amount, category, selected_date))
        mysql.connection.commit()

        # Check if budget exists for this category and notify if limits are reached
        cur.execute("SELECT budget_amount FROM budgets WHERE user_id = %s AND category = %s", (user_id, category))
        budget = cur.fetchone()

        if budget:
            # Fetch total spent in the current category
            cur.execute("SELECT SUM(amount) FROM expenses WHERE user_id = %s AND category = %s", (user_id, category))
            total_spent = cur.fetchone()[0]

            if total_spent and budget:
                budget_amount = budget[0]
                # Check if total_spent exceeds percentage of budget and send email
                percentage_spent = (total_spent / budget_amount) * 100

                if percentage_spent >= 90:
                    send_email(session['email'], '90% Budget Warning', f'You have spent 90% of your budget for {category}.')
                elif percentage_spent >= 75:
                    send_email(session['email'], '75% Budget Warning', f'You have spent 75% of your budget for {category}.')
                elif percentage_spent >= 50:
                    send_email(session['email'], '50% Budget Warning', f'You have spent 50% of your budget for {category}.')

        cur.close()

        return redirect(url_for('expenses'))

    # Render the expense entry page for the selected date
    return render_template('expense_entry.html', day=day)

# Function to send email notifications
def send_email(recipient, subject, body):
    msg = Message(subject, recipients=[recipient])
    msg.body = body
    mail.send(msg)

# Route to set budget for categories
@app.route('/set_budget', methods=['GET', 'POST'])
def set_budget():
    if 'username' not in session:
        return redirect(url_for('login_register'))
    
    if request.method == 'POST':
        category = request.form['category']
        budget_amount = request.form['budget_amount']
        savings_goal = request.form['savings_goal']

        # Get the current user's user_id
        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM users WHERE username = %s", [session['username']])
        user = cur.fetchone()
        user_id = user[0]

        # Insert or update budget data for the category
        cur.execute(""" 
            INSERT INTO budgets (user_id, budget_amount, savings_goal, category) 
            VALUES (%s, %s, %s, %s) 
            ON DUPLICATE KEY UPDATE budget_amount=%s, savings_goal=%s 
        """, (user_id, budget_amount, savings_goal, category, budget_amount, savings_goal))
        
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('expenses'))
    
    # If GET request, render the budget setting form
    return render_template('set_budget.html')  # Ensure this template exists


# Route to show the pie chart
from flask import jsonify

from decimal import Decimal  # Ensure you have this import at the top of your file

@app.route('/show_pie_chart')
def show_pie_chart():
    if 'username' not in session:
        return redirect(url_for('login_register'))

    # Get the current user's user_id
    cur = mysql.connection.cursor()
    cur.execute("SELECT user_id FROM users WHERE username = %s", [session['username']])
    user = cur.fetchone()
    user_id = user[0]

    # Fetch the total income of the user
    cur.execute("SELECT SUM(income_amount) FROM income WHERE user_id = %s", [user_id])
    total_income = cur.fetchone()[0] or Decimal(0)  # Default to 0 if no income is found

    # Fetch expenses data for the user and aggregate by category
    cur.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id = %s GROUP BY category", [user_id])
    expenses = cur.fetchall()
    
    # Monthly expenses for trend analysis
    cur.execute("SELECT MONTH(date) AS month, SUM(amount) FROM expenses WHERE user_id = %s GROUP BY month", [user_id])
    monthly_expenses = cur.fetchall()

    cur.close()

    # Prepare data for the pie chart
    categories = []
    amounts = []
    total_expenses = Decimal(0)  # Use Decimal to maintain precision
    highest_expense_category = ''
    highest_expense_amount = Decimal(0)  # Use Decimal for amounts

    for expense in expenses:
        categories.append(expense[0])  # Category name
        amount = Decimal(expense[1])  # Convert to Decimal for consistency
        amounts.append(float(amount))  # Append float to amounts for chart
        total_expenses += amount
        
        # Determine highest expense category
        if amount > highest_expense_amount:
            highest_expense_amount = amount
            highest_expense_category = expense[0]

    # Calculate analytics
    savings_rate = ((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0
    budget_utilization = (total_expenses / total_income * 100) if total_income > 0 else 0

    # Create a dictionary for monthly expenses
    monthly_trends = {}
    for month, amount in monthly_expenses:
        monthly_trends[month] = float(amount)  # Convert to float for display

    # Budget feedback
    budget_status = ''
    if total_expenses > total_income:
        budget_status = "You are overspending your budget."
    elif total_expenses == total_income:
        budget_status = "You are on track with your budget."
    else:
        budget_status = "You are under your budget, which is great!"

    return render_template('pie_chart.html', 
                           categories=categories, 
                           amounts=amounts, 
                           total_income=float(total_income),  # Convert to float for display
                           total_expenses=float(total_expenses),  # Convert to float for display
                           highest_expense_category=highest_expense_category,
                           highest_expense_amount=float(highest_expense_amount),  # Convert to float for display
                           budget_status=budget_status,
                           savings_rate=savings_rate,
                           budget_utilization=budget_utilization,
                           monthly_trends=monthly_trends)


if __name__ == '__main__':
    app.run(debug=True)
