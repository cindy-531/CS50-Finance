import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Create lists containing values for the table
    symbols = []
    names = []
    shares = []
    totals = []
    prices = []

    # Query database for the current amount of cash and stocks
    cash =  db.execute("SELECT cash FROM users WHERE id = :username", username=session["user_id"] )[0]["cash"]
    stocks = db.execute("SELECT * FROM summary WHERE id = :username", username=session["user_id"] )
    grand = cash

    # Append to the lists from the database
    for item in stocks:
        symbol = item["symbol"]
        symbols.append(symbol)
        names.append(lookup(symbol)["name"])
        share = db.execute("SELECT shares FROM summary WHERE id = :username AND symbol= :symbol", username=session["user_id"], symbol=symbol)[0]["shares"]
        shares.append(share)
        prices.append(lookup(symbol)["price"])
        total = int(share) * lookup(symbol)["price"]
        totals.append(total)
        grand += total

    # Obtain list length
    length = len(symbols)

    # Direct users to the index page
    return render_template("index.html", symbols = symbols, length = length, cash=cash, names = names, shares = shares, totals = totals, prices = prices, grand = grand)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure stock symbol and share validity
        if lookup(request.form.get("symbol")) == None:
            return apology("invalid stock symbol", 403)
        elif int(request.form.get("shares")) < 1:
            return apology("must purchase at least one stock", 403)

        # Compute the value of the purchase
        price = lookup(request.form.get("symbol"))["price"]
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])[0]["cash"]
        total = price * int(request.form.get("shares"))

        # Ensure the user has enough cash to pay for the stocks
        if total > cash:
            return apology("not enough cash to purchase", 403)

        # Insert into database that is used to retrieve history
        db.execute("INSERT INTO purchase (id, symbol, shares, price, created_at) VALUES(:id,:symbol,:shares,:value, datetime('now'))", id=session["user_id"], symbol=request.form.get("symbol"), shares=request.form.get("shares"), value=price)

        # Insert into database that is used for the index page
        number = db.execute("SELECT COUNT(*) FROM purchase WHERE id=:id AND symbol=:symbol", id=session["user_id"], symbol=request.form.get("symbol"))[0]["COUNT(*)"]

        # Insert into database if the current stock has not been purchased before
        if number == 1:
            db.execute("INSERT INTO summary (id, symbol, shares, price) VALUES(:id,:symbol,:shares,:value)", id=session["user_id"], symbol=request.form.get("symbol"), shares=request.form.get("shares"), value=price)

        # Update database if the stock has been purchased before
        else:
            share = db.execute("SELECT SUM(shares) FROM purchase WHERE id = :username AND symbol= :symbol", username=session["user_id"], symbol=request.form.get("symbol"))[0]["SUM(shares)"]
            db.execute("UPDATE summary SET shares= :shares WHERE (id = :username AND symbol= :symbol)", shares=share, username=session["user_id"], symbol=request.form.get("symbol"))
        db.execute("UPDATE users SET cash = :new", new = cash - total)

        # Redirect users to the index page
        return redirect("/")

    # User reached route via GET (as by submitting a form via GET)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    symbols = []
    shares = []
    prices = []
    times = []

    purchases = db.execute("SELECT * FROM purchase WHERE id = :username", username=session["user_id"])
    length = len(purchases)

    for item in purchases:
        symbols.append(item["symbol"])
        shares.append(item["shares"])
        prices.append(item["price"])
        times.append(item["created_at"])

    return render_template("history.html", symbols = symbols, shares = shares, prices = prices, times = times, length = length)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Obtain symbol that user inputted
        stock_info = lookup(request.form.get("symbol"))

        # Ensure symbol validity
        if stock_info == None:
            return apology("invalid stock symbol", 403)

        # Direct users to quoted page
        return render_template("quoted.html", stock_info = stock_info)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Select row in database for the inputted username
        row = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username") )

        # Check the validity of the username
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif len(row) != 0:
            return apology("username already taken", 403)

        # Check the validity of the password
        if not request.form.get("password"):
            return apology("must provide password", 403)
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 403)
        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("passwords do not match", 403)

        # Register user into the database
        db.execute("INSERT INTO users (username, hash) VALUES(:username, :password)",
        username = request.form.get("username"), password = generate_password_hash(request.form.get("password")) )

        # Redirect users to login page
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Obtain the symbol and shares that the user inputted
        stock = request.form.get("symbol")
        sold = request.form.get("shares")

        # Compute the number of shares in the account
        shares = db.execute("SELECT shares FROM summary WHERE id = :username AND symbol= :symbol", username=session["user_id"], symbol=stock)[0]["shares"]
        update = int(shares) - int(sold)

        # Ensure stock validity
        if stock == "":
            return apology("must select a stock", 403)
        elif int(shares) == 0:
            return apology("stock not owned", 403)

        # Ensure an appropriate amount of shares is requested
        if int(sold) < 0:
            return apology("invalid stock shares", 403)
        elif int(shares) < int(sold):
            return apology("not enough shares owned", 403)

        # Insert updated information into database
        db.execute("INSERT INTO purchase (id, symbol, shares, price, created_at) VALUES(:id,:symbol,:shares,:value, datetime('now'))", id=session["user_id"], symbol=stock, shares="-"+sold, value=lookup(stock)["price"])
        db.execute("UPDATE summary SET shares= :value WHERE (id = :username AND  symbol= :symbol)", value=str(update), username = session["user_id"], symbol=stock)

        # Update the amount of cash in account
        cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])[0]["cash"]
        db.execute("UPDATE users SET cash = :new", new = cash + (int(sold) * lookup(stock)["price"]) )

        # Redirect users to login page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        symbols = []

        stocks = db.execute("SELECT * FROM summary WHERE id = :username", username = session["user_id"])

        # Create a list of stocks that the user owns and can sell
        for item in stocks:
            symbol = item["symbol"]
            symbols.append(symbol)

        return render_template("sell.html", symbols = symbols)

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Add cash to account"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Compute current cash balance
        cash = float(request.form.get("amount"))
        total = cash + db.execute("SELECT cash FROM users WHERE id =:id", id = session["user_id"])[0]["cash"]

        # Update database with new cash value
        db.execute("UPDATE users SET cash= :value WHERE id = :username", value = total, username = session["user_id"])
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("deposit.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
