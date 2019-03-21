from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():

    # Extracts stocks and their total quantities from the user's database
    rows = db.execute("SELECT stock, sum(quantity) AS quantities FROM portfolio WHERE user_id = :user_id GROUP BY stock ORDER BY stock", user_id=session["user_id"])

    # Making empty lists for the current price and the total of the shares
    prices = []
    total = []
    finaltotal = 0

    # lookup current prices, calculate the total and add to the list
    for row in rows:
        quote = lookup(row["stock"])
        preprice = quote["price"]
        pretotal = preprice * row["quantities"]
        prices.append(usd(preprice))
        total.append(usd(pretotal))
        finaltotal += pretotal


    # Pulling user's cash amount from the database
    rows2 = db.execute("SELECT cash FROM users where id = :user_id", user_id=session["user_id"])
    cash = usd(rows2[0]["cash"])

    # Calculating total cash amount
    finaltotal += rows2[0]["cash"]

    return render_template("index.html", rows=rows, prices=prices, total=total, cash=cash, finaltotal=usd(finaltotal))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure user inputs a stock symbol
        #if not request.form.get("symbol"):
            #return apology("missing symbol")

        # ensure user inputs the number of shares
       # if not request.form.get("shares"):
            #return apology("missing shares")

        # calculate total cost of shares the user wants to buy
        quote = lookup(request.form.get("symbol"))

        # if user enters invalid symbol
        if not quote:
            return apology("invalid symbol")

        cost = quote["price"] * int(request.form.get("shares"))

        # checking the user's cash
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        # if user can't afford
        if cost > cash[0]["cash"]:
            return apology("can't afford")

        # else go ahead and buy the shares
        else:

            # adding shares to the database
            db.execute("INSERT INTO portfolio (user_id, stock, quantity, price) VALUES (:id, :stock, :quantity, :price)", id=session["user_id"], stock=quote["symbol"], quantity=request.form.get("shares"), price=quote["price"])

            # updating the user's cash
            db.execute("UPDATE users SET cash = cash - :cost WHERE id = :id", cost=cost, id=session["user_id"])

            # flash message
            flash ("Bought")

            # redirect user to home page
            return redirect(url_for("index"))

    # else if user reached route via GET (by clicking a link or by redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""

    # Pull the history from the database
    rows = db.execute("SELECT stock, quantity, price, time FROM portfolio WHERE user_id = :user_id ORDER BY time DESC", user_id=session["user_id"])

    return render_template("history.html", rows=rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        #if not request.form.get("username"):
        #    return apology("must provide username")

        # ensure password was submitted
        #elif not request.form.get("password"):
        #    return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # flash message
        flash ("Logged in")
        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # lookup the symbol provided by the user
        quote = lookup(request.form.get("symbol"))

        # apology is symbol is invalid
        if not quote:
            return apology("invalid symbol")

        # else render the quote
        else:
            return render_template("quoted.html", share=quote["symbol"], price=usd(quote["price"]))

    # if user reached route via GET (as in by clicking on a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    # forget any user id
    session.clear()

    # if user reached route via POST as in by submitting a form via POST
    if request.method == "POST":

        # ensure username is not blank
        #if not request.form.get("username"):
         #   return apology("must provide username")

        # ensure password is not blank
        #elif not request.form.get("password"):
         #   return apology("must provide password")

        # ensure password matches the password confirmation
        if request.form.get("password") != request.form.get("passwordconfirmation"):
            return apology("passwords do not match")

        # hash the password
        hash = pwd_context.hash(request.form.get("password"))

        # insert new user into database
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"),hash=hash)

        # if username exists
        if not result:
            return apology("username already exists")

        # redirect user to login page
        return redirect(url_for("login"))

    # else if user reached via GET as in by clicking a link or via redirect
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Pulling up the selected stock from the database
        rows = db.execute("SELECT sum(quantity) AS quantities FROM portfolio WHERE user_id = :user_id AND stock = :stock", user_id=session["user_id"], stock=request.form.get("symbol"))

        # if user tries to sell more shares than he owns
        if (rows[0]["quantities"] < int(request.form.get("shares"))):
            return apology("too many shares")

        # else sell the shares and update the user's cash and portfolio
        else:
            quote = lookup(request.form.get("symbol"))
            db.execute("INSERT INTO portfolio (user_id, stock, quantity, price) VALUES (:user_id, :stock, :quantity, :price)", user_id=session["user_id"], stock=request.form.get("symbol"), quantity=(-1 * int(request.form.get("shares"))), price=quote["price"])
            db.execute("UPDATE users SET cash = cash - :cost WHERE id = :user_id", cost=(-1 * quote["price"]), user_id=session["user_id"])
            flash("Sold")
            return redirect(url_for("index"))


    # if user reached route via GET as in by clicking a link or via redirect
    else:
        # Pulling user's stocks from database to display in the drop down menu.
        rows = db.execute("SELECT stock, sum(quantity) AS quantities FROM portfolio WHERE user_id = :user_id GROUP BY stock ORDER BY stock", user_id=session["user_id"])

        return render_template("sell.html", rows=rows)

@app.route("/changepassword", methods=["GET", "POST"])
@login_required
def changepassword():
    """Change user's password"""

    # if user reached route via POST as by submitting a form
    if request.method == "POST":

        # ensure password matches the password confirmation
        if request.form.get("newpassword") != request.form.get("newpasswordconfirmation"):
            return apology("new passwords do not match")

        # pulling hash of current user from the database
        rows = db.execute("SELECT hash FROM users WHERE id = :user_id", user_id=session["user_id"])

        # ensure old password matches the password on file
        if not pwd_context.verify(request.form.get("oldpassword"), rows[0]["hash"]):
            return apology("invalid old password")

        # store the new password in file
        db.execute("UPDATE users SET hash = :hash WHERE id = :user_id", hash=pwd_context.hash(request.form.get("newpassword")), user_id=session["user_id"])

        flash("Password Changed")
        return redirect(url_for("index"))

    # if user reached route via GET as by clicking a link
    else:
        return render_template("changepassword.html")

@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():

    # if user reached route via POST as by submitting a form
    if request.method == "POST":

        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash=int(request.form.get("cash")), user_id=session["user_id"])

        flash("Cash Added")
        return redirect(url_for("index"))

    # if user reached route via GET as by clicking a link
    else:
        return render_template("addcash.html")