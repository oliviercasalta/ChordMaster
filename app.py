import os
import datetime
import requests
import pymysql
import sqlalchemy

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, MetaData, Sequence, asc, desc, update, DateTime
from sqlalchemy.sql import select, func

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

# Connecting to GCloud SQL database "tab"
engine = create_engine('mysql+pymysql://root:root@127.0.0.1/tab')

# Defining metadata woth SQLAlchemy
metadata = MetaData()

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

################ INDEX #################
@app.route("/", methods=["GET", "POST"])
@login_required
def index():

    # Reflecting metadata 
    metadata = MetaData(bind=engine, reflect=True)
    song_list = metadata.tables["song_list"]
    song_modif = metadata.tables["song_modif"]

    # Go to the "Edit" menu to work on the selected song
    if request.method == "POST":

        # Set the time at the moment of the submission
        time = datetime.datetime.now()

        # Get the selected song from the user
        song_name = request.form.get("text")

        # Create a backlog table of all operations
        with engine.connect() as conn:
            
            # Insert new modif
            ins = song_modif.insert().values(user_id=session["user_id"], song_name=song_name, time=time)
            conn.execute(ins)
            
            # Select all the current chord/bar from the updated table
            s = song_modif.select().where(song_modif.c.user_id==session["user_id"]).order_by(song_modif.c.time.desc())
            song_name_list = conn.execute(s).fetchall()
            
            # Get the name of the current song
            song_name=song_name_list[0]['song_name']
            
            # Select all the current chord/bar from the updated table
            song_table = metadata.tables[song_name]
            sc = song_table.select().order_by(song_table.c.bar.asc())
            song_complete = conn.execute(sc).fetchall()
            
            # Create format arguments for the table in html
            new_line_dict = conn.execute(select([func.count(song_table.c.bar)])).fetchone()

        # Create format arguments for the table in html
        new_line = int(new_line_dict[0]) / 4

        return render_template("tabreader.html", song_name=song_name, song_complete=song_complete, new_line=new_line)
    else:
        # Return the list of song
        with engine.connect() as conn:
            s = song_list.select().where(song_list.c.user_id==session["user_id"]).order_by(song_list.c.time.desc())
            list_of_song = conn.execute(s).fetchall()

        return render_template("index.html", song_list=list_of_song)

    return render_template("index.html")

################# EDITOR (1)  ###################
@app.route("/tabeditor", methods=["GET", "POST"])
@login_required
def tabeditor():
    
    # Reflecting metadata 
    metadata = MetaData(bind=engine, reflect=True)
    song_list = metadata.tables["song_list"]
    song_modif = metadata.tables["song_modif"]
    
    if request.method == "POST":

        # Write time in a variable called time
        time = datetime.datetime.now()

        # Get the song name from user input
        song_name = request.form.get("song_name")

        
        with engine.connect() as conn:
            
            # Return an error message if the name of the song is already taken
            s = song_list.select().where(song_list.c.song_name==song_name)
            duplicate = conn.execute(s).fetchone()
            if duplicate:
                return apology("song name already taken", 403)
            
            # Update the table of song list
            ins = song_list.insert().values(user_id=session["user_id"], song_name=song_name, time=time)
            conn.execute(ins)   
            
            # Update the table of song modi
            ins = song_modif.insert().values(user_id=session["user_id"], song_name=song_name, time=time)
            conn.execute(ins)
        
        # Create a new metadata table
        song_table = Table(song_name, metadata,
        Column('count', Integer, primary_key=True),
        Column('bar', Integer),
        Column('chord', String(50)))
        song_table.create(engine)

        return render_template("tabeditortab.html", song_name=song_name)
    
    else:
        return render_template("tabeditor.html")

################# EDITOR (2)  #####################
@app.route("/tabeditortab", methods=["GET", "POST"])
@login_required
def tabeditortab():
    """Tab editor"""

    # Reflecting metadata 
    metadata = MetaData(bind=engine, reflect=True)
    song_modif = metadata.tables["song_modif"]

    # Declare format argument for the table in html
    new_line = 0

    # Select current song data
    with engine.connect() as conn:
        s = song_modif.select().order_by(song_modif.c.time.desc())
        song_name_list = conn.execute(s).fetchall()

    # Select the song that will be used to edit
    song_name = song_name_list[0]['song_name']
    song_table = metadata.tables[song_name]

    # Create appropriate dict for the next operations
    song_complete = []

    if request.method == "POST":

        # Add Chord to the last bar
        if request.form.get("text") == 'Add Chord':

            # Get the chord from input
            chord = request.form.get("chord")

            with engine.connect() as conn:

                # Add new chord at the end of the score
                ins = song_table.insert(None).values(chord=chord)
                conn.execute(ins)

                # Select all the chord form a song
                s = select([song_table.c.chord]).order_by(song_table.c.count.asc())
                all_chords = conn.execute(s).fetchall()

                # Insert every chord of the song in the temp table
                for i in range(len(all_chords)):
                    temp_chord = all_chords[i]
                    conn.execute(song_table.insert(None), bar=(i+1), chord=temp_chord[0])

                s = song_table.select().where(song_table.c.bar == None)
                row_to_del = conn.execute(s).fetchall()

                # Delete chord at the end of the score
                conn.execute(song_table.delete().where(song_table.c.count <=row_to_del[0][0]))
                
                # Select all the current chord/bar from the updated table
                s = song_table.select().order_by(song_table.c.bar.asc())
                song_complete = conn.execute(s).fetchall()
  
                # Create format arguments for the table in html
                new_line_dict = conn.execute(select([func.count(song_table.c.bar)])).fetchone()

            # Create format arguments for the table in html
            new_line = int(new_line_dict[0]) / 4
            return render_template("tabeditortab.html", song_complete=song_complete, new_line=new_line, song_name=song_name)

        # Remove the last bar
        elif request.form.get("text") == 'Remove Last Chord':
        
            with engine.connect() as conn:
                # Select the last bar of the score
                s = select([song_table.c.bar]).order_by(song_table.c.bar.desc()).limit(1)
                last = conn.execute(s).fetchone()
                last_bar = last[0]

                # Delete chord at the end of the score
                conn.execute(song_table.delete().where(song_table.c.bar==last_bar))
            
                # Select all the current chord/bar from the updated table
                s = song_table.select().order_by(song_table.c.bar.asc())
                song_complete = conn.execute(s).fetchall()

                # Create format arguments for the table in html
                new_line_dict = conn.execute(select([func.count(song_table.c.bar)])).fetchone()

            # Create format arguments for the table in html
            new_line = int(new_line_dict[0]) / 4
            
            return render_template("tabeditortab.html", song_complete=song_complete, new_line=new_line, song_name=song_name)
        
        # Replace a chord at the location specified in the bar input field
        elif request.form.get("text") == 'Replace Chord':
            bar = request.form.get("bar")
            chord = request.form.get("chord")

            with engine.connect() as conn:
                # Update the chord
                stmt = song_table.update().where(song_table.c.bar==bar).values(chord=chord)
                conn.execute(stmt)
            
            with engine.connect() as conn:
                # Select all the current chord/bar from the updated table
                s = song_table.select().order_by(song_table.c.bar.asc())
                song_complete = conn.execute(s).fetchall()

                # Create format arguments for the table in html
                new_line_dict = conn.execute(select([func.count(song_table.c.bar)])).fetchone()

            # Create format arguments for the table in html
            new_line = int(new_line_dict[0]) / 4

            return render_template("tabeditortab.html", song_complete=song_complete, new_line=new_line, song_name=song_name)
        else:
            return render_template("tabeditortab.html", song_name=song_name, song_complete=song_complete, new_line=new_line)
    else:
        return render_template("tabeditortab.html", song_name=song_name, song_complete=song_complete, new_line=new_line)

#################### READER  ####################
@app.route("/tabreader", methods=["GET", "POST"])
@login_required
def tabreader():

    # Reflecting metadata 
    metadata = MetaData(bind=engine, reflect=True)
    song_modif = metadata.tables["song_modif"]
    song_list = metadata.tables["song_list"]

    with engine.connect() as conn:
        # Select current song data
        s = song_modif.select().order_by(song_modif.c.time.desc())
        song_name_list = conn.execute(s).fetchall()

        # Select the song that will be used to edit
        song_name = song_name_list[0]['song_name']
        song_table = metadata.tables[song_name]

        # Select all the current chord/bar from the updated table
        s = song_table.select().order_by(song_table.c.bar.asc())
        song_complete = conn.execute(s).fetchall()

        # Create format arguments for the table in html
        new_line_dict = conn.execute(select([func.count(song_table.c.bar)])).fetchone()

    # Create format arguments for the table in html
    new_line = int(new_line_dict[0]) / 4

    if request.method == "POST":
        
        # Go to the TabEditor page if the user click on "Edit"
        if request.form.get("text") == 'Edit':
            return render_template("tabeditortab.html", song_name=song_name, song_complete=song_complete, new_line=new_line)

        # Delete the song and go to index menu
        elif request.form.get("text") == 'Delete':
            
            # Drop the current table
            song_table.drop(engine)
            
            # Delete the song from the current list
            with engine.connect() as conn:
                conn.execute(song_list.delete().where(song_list.c.song_name==song_name))

            return redirect("/")

        else:
            return render_template("tabreader.html", song_name=song_name, song_complete=song_complete, new_line=new_line)

    return render_template("tabreader.html", song_name=song_name, song_complete=song_complete, new_line=new_line)

################## LOGIN  ###################
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # Reflecting metadata 
    metadata = MetaData(bind=engine, reflect=True)
    users = metadata.tables['users']

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        else:
            # Ensure username exists and password is correct
            with engine.connect() as conn:
                s = users.select().where(users.c.username==request.form.get("username"))
                result = conn.execute(s).fetchall()
            
            if len(result) != 1 or not check_password_hash(result[0]["hash"], request.form.get("password")):
                return apology("invalid username and/or password", 403)

            # Remember which user has logged in
            session["user_id"] = result[0]["id"]

            # Redirect user to home page
            return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

################## LOGOUT ###################
@app.route("/logout")
def logout():

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

################## REGISTER  ###################
@app.route("/register", methods=["GET", "POST"])
def register():

    # Forget any user_id
    session.clear()

    # Reflecting metadata
    metadata = MetaData(bind=engine, reflect=True)
    users = metadata.tables['users']

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Connecting to mysql database
        with engine.connect() as conn:
            s = users.select().where(users.c.username==request.form.get("username"))
            result = conn.execute(s).fetchall()

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
        elif result:
            return apology("username already taken", 403)

        # Insert new user into the database
        passwordhash = generate_password_hash(request.form.get("password"))

        # Create new record
        with engine.connect() as conn:
            ins = users.insert().values(username=request.form.get("username"), hash=passwordhash)
            conn.execute(ins)
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