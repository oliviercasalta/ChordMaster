import os
import datetime
import requests

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required

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

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///tabs.db")

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of tabs"""

    # Go to the "Edit" menu to work on the selected song
    if request.method == "POST":

        # Set the time at the moment of the submission
        time = datetime.datetime.now()

        # Get the selected song from the user
        result = request.form.get("text")

        # Create a backlog table of all operations done of the song
        db.execute("INSERT INTO song_modif (user_id, song_name, time) VALUES (:user_id, :song_name, :time)",user_id=session["user_id"], song_name=result, time=time)

        # Get the name of the song to pass to the "Edit" menu
        song_name_list = db.execute("SELECT song_name FROM song_modif WHERE user_id = :user_id ORDER BY time DESC", user_id=session["user_id"])
        song_name=song_name_list[0]['song_name']

        song_complete = db.execute("SELECT * FROM :song_name ORDER BY bar ASC", song_name=song_name)

        new_line_dict = db.execute("SELECT count (bar) FROM :song_name", song_name=song_name)
        new_line = int(new_line_dict[0]['count (bar)'] / 4)
        return render_template("tabreader.html", song_name=song_name, song_complete=song_complete, new_line=new_line)

    else:
        # Get a list of dict
        slist = db.execute("SELECT * FROM song_list WHERE user_id = :user_id ORDER BY time DESC",user_id=session["user_id"])
        # Create temp dicts
        temp_dict ={}
        temp_dict2 ={}

        # Create the final list of dicts
        song_list = []

        for i in range(len(slist)):

            # Create a temp dict for the increment order of the future list of song
            temp_dict = {'order': i + 1}
            # Create a temp dict that get all data from SQL table
            temp_dict2 = slist[i]
            # Merge the 2x dicts
            temp_dict.update(temp_dict2)
            # Create a list of dict with append
            song_list.append(temp_dict)

        return render_template("index.html", song_list=song_list)

    return render_template("index.html")

@app.route("/tabeditor", methods=["GET", "POST"])
@login_required
def tabeditor():
    """Tab editor"""

    if request.method == "POST":

        # Write time in a variable called time
        time = datetime.datetime.now()

        # Get the song name from user input
        song_name = request.form.get("song_name")

        # Return an error message if the name of the song is already taken
        if db.execute("SELECT song_name FROM song_list WHERE song_name = :song_name",song_name=song_name):
            return apology("song name already taken", 403)

        # Update all the table of song list and create a new table for the new song
        db.execute("INSERT INTO song_list (user_id, song_name, time) VALUES (:user_id, :song_name, :time)",user_id=session["user_id"], song_name=song_name, time=time)
        db.execute("INSERT INTO song_modif (user_id, song_name, time) VALUES (:user_id, :song_name, :time)",user_id=session["user_id"], song_name=song_name, time=time)
        db.execute("CREATE TABLE :song_name (bar INTEGER PRIMARY KEY AUTOINCREMENT, chord TEXT)", song_name=song_name)
        return render_template("tabeditortab.html", song_name=song_name)
    else:
        return render_template("tabeditor.html")


@app.route("/tabeditortab", methods=["GET", "POST"])
@login_required
def tabeditortab():
    """Tab editor"""

    # Declare format argument for the table in html
    new_line = 0

    # Select the song that will be used to edit
    song_namelist = db.execute("SELECT song_name FROM song_modif ORDER BY time DESC")
    song_name = song_namelist[0]['song_name']

    # Create appropriate list and dict for the next operations
    
    song_complete = []

    if request.method == "POST":

        # Add Chord to the last bar
        if request.form.get("text") == 'Add Chord':

            # Get the chord from input
            chord = request.form.get("chord")

            # Create a new temp table / Drop the existing one in order to keep the bar increment in order if potential deleting
            t_chord = db.execute("SELECT chord FROM :song_name ORDER BY bar ASC", song_name=song_name)
            db.execute("CREATE TABLE temp_name (bar INTEGER PRIMARY KEY AUTOINCREMENT, chord TEXT)")
            for i in range(len(t_chord)):
                temp_chord = t_chord[i]
                db.execute("INSERT INTO temp_name (chord) VALUES (:chord)", chord=temp_chord['chord'])
            db.execute("DROP TABLE :song_name", song_name=song_name)
            db.execute("ALTER TABLE temp_name RENAME TO :song_name", song_name=song_name)

            # Add new chord at the end of the score
            db.execute("INSERT INTO :song_name (chord) VALUES (:chord)", song_name=song_name, chord=chord)

            # Select all the current chord/bar from the updated table
            song_complete = db.execute("SELECT * FROM :song_name ORDER BY bar ASC", song_name=song_name)

            # Create format arguments for the table in html
            new_line_dict = db.execute("SELECT count (bar) FROM :song_name", song_name=song_name)
            new_line = int(new_line_dict[0]['count (bar)'] / 4)

            return render_template("tabeditortab.html", song_complete=song_complete, new_line=new_line, song_name=song_name)

        # Replace a chord at the location specified in the bar input field
        elif request.form.get("text") == 'Replace Chord':
            bar = request.form.get("bar")
            chord = request.form.get("chord")

            # Update the chord
            db.execute("UPDATE :song_name SET chord=:chord WHERE bar=:bar", song_name=song_name, chord=chord, bar=bar)

            # Select all the current chord/bar from the updated table
            song_complete = db.execute("SELECT * FROM :song_name ORDER BY bar ASC", song_name=song_name)

            # Create format arguments for the table in html
            new_line_dict = db.execute("SELECT count (bar) FROM :song_name", song_name=song_name)
            new_line = int(new_line_dict[0]['count (bar)'] / 4)

            return render_template("tabeditortab.html", song_complete=song_complete, new_line=new_line, song_name=song_name)

        # Remove the last bar
        elif request.form.get("text") == 'Remove Last Chord':
            count = db.execute("SELECT count (bar) FROM :song_name", song_name=song_name)
            bar = int(count[0]['count (bar)'])

            # Create a new temp table / Drop the existing one in order to keep the bar increment for the new table
            t_chord = db.execute("SELECT chord FROM :song_name ORDER BY bar ASC", song_name=song_name)
            db.execute("CREATE TABLE temp_name (bar INTEGER PRIMARY KEY AUTOINCREMENT, chord TEXT)")
            for i in range(len(t_chord)):
                temp_chord = t_chord[i]
                db.execute("INSERT INTO temp_name (chord) VALUES (:chord)", chord=temp_chord['chord'])
            db.execute("DROP TABLE :song_name", song_name=song_name)
            db.execute("ALTER TABLE temp_name RENAME TO :song_name", song_name=song_name)
            db.execute("DELETE FROM :song_name WHERE bar=:bar", song_name=song_name, bar=bar)

            # Select all the current chord/bar from the updated table
            song_complete = db.execute("SELECT * FROM :song_name ORDER BY bar ASC", song_name=song_name)

            # Create format arguments for the table in html
            new_line_dict = db.execute("SELECT count (bar) FROM :song_name", song_name=song_name)
            new_line = int(new_line_dict[0]['count (bar)'] / 4)

            return render_template("tabeditortab.html", song_complete=song_complete, new_line=new_line, song_name=song_name)

        else:
            return render_template("tabeditortab.html", song_name=song_name, song_complete=song_complete, new_line=new_line)
    else:
        return render_template("tabeditortab.html", song_name=song_name, song_complete=song_complete, new_line=new_line)

@app.route("/tabreader", methods=["GET", "POST"])
@login_required
def tabreader():

    # Select the song that will be used to edit
    song_namelist = db.execute("SELECT song_name FROM song_modif ORDER BY time DESC")
    song_name = song_namelist[0]['song_name']

    # Select all chords from the song
    song_complete = db.execute("SELECT * FROM :song_name ORDER BY bar ASC", song_name=song_name)

    # Get the argument for the format
    new_line_dict = db.execute("SELECT count (bar) FROM :song_name", song_name=song_name)
    new_line = int(new_line_dict[0]['count (bar)'] / 4)

    if request.method == "POST":
        # Go to the TabEditor page if the user click on "Edit"
        if request.form.get("text") == 'Edit':
            return render_template("tabeditortab.html", song_name=song_name, song_complete=song_complete, new_line=new_line)

        # Delete the song and go to index menu
        elif request.form.get("text") == 'Delete':
            db.execute("DROP TABLE :song_name", song_name=song_name)
            db.execute("DELETE FROM song_list WHERE song_name = :song_name", song_name=song_name)
            return redirect("/")

        else:
            return render_template("tabreader.html", song_name=song_name, song_complete=song_complete, new_line=new_line)

    return render_template("tabreader.html", song_name=song_name, song_complete=song_complete, new_line=new_line)

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
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

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



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

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

        # Ensure password and password again match
        elif request.form.get("password") != request.form.get("passwordagain"):
            return apology("passwords did not match", 403)

        # Ensure the username is not already taken
        elif db.execute("SELECT username FROM users WHERE username = :username",username=request.form.get("username")):
            return apology("username already taken", 403)

        # Insert new user into the database
        passwordhash = generate_password_hash(request.form.get("password"))
        new_user = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"), hash=passwordhash)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
