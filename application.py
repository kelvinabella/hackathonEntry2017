from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
import sqlite3
import json
import requests

from helpers import login_required

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

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route("/")
@login_required
def index():
    """Homepage."""
    
    # get user id
    id = session["user_id"]
	
    with sqlite3.connect('inteliqas.db') as conn:
	    c = conn.cursor()
	    
	    c.execute("""SELECT *
	    			FROM producer_table 
	    			ORDER BY timestamp 
	    			DESC LIMIT 1""")
	    rows_producer = c.fetchall()
	    row_producer = rows_producer[0]
	    voltage_consumption = row_producer[3]
	    current_consumption = row_producer[4]
	    voltage_distribution = row_producer[5]
	    current_distribution = row_producer[6]
	    
	    c.execute("""SELECT *
	    			FROM consumer_table 
	    			ORDER BY timestamp 
	    			DESC LIMIT 1""")
	    rows_consumer = c.fetchall()
	    row_consumer = rows_consumer[0]
	    voltage_consumption_c = row_consumer[7]
	    current_consumption_c = row_consumer[8]
	    power_distribution = voltage_distribution*voltage_distribution
	    power_consumption = voltage_consumption*voltage_consumption
	    power_consumption_c = voltage_consumption_c*current_consumption_c
		
	    return render_template('index.html', 
    	    voltage_distribution=voltage_distribution, 
    	    current_distribution=current_distribution,
    		voltage_consumption=voltage_consumption, 
    		current_consumption=current_consumption,
    		voltage_consumption_c=voltage_consumption_c, 
    		current_consumption_c=current_consumption_c,
    		power_distribution=power_distribution,
    		power_consumption=power_consumption,
    		power_consumption_c=power_consumption_c)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        with sqlite3.connect('inteliqas.db') as conn:
            c = conn.cursor()    
        
            rows = c.execute("SELECT * FROM users_table WHERE username = ?", (request.form.get("username"),))
            
            rows = c.fetchall()
            error = None
            # ensure username exists and password is correct
            if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0][2]):
                # alert user for successful transaction
                error = "Invalid credentials"
                return render_template("login.html", error=error)
                
            else:    
                # remember which user has logged in
                session["user_id"] = rows[0][0]
                
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
    
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # hash password, just because
        hash = pwd_context.encrypt(request.form.get("password"))
        
        # query database for username
        
        with sqlite3.connect('inteliqas.db') as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users_table (username, hash) VALUES (?, ?)"
                            , (request.form.get("username"), hash))
    
            # query database for username
            c.execute("SELECT id, hash FROM users_table WHERE username = ?", (request.form.get("username"),))
            
            rows = c.fetchall()
            
            # ensure username exists and password is correct
            if len(rows[0]) != 1 or not pwd_context.verify(request.form.get("password"), rows[0][1]):
                flash("invalid username and/or password")
    
            # remember which user has logged in
            session["user_id"] = rows[0][0]
            
            # redirect user to home page
            return redirect(url_for("login"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
        
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy energy."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        with sqlite3.connect('inteliqas.db') as conn:
            c = conn.cursor()
            
            # query database for username
            c.execute("SELECT reference_code FROM consumer_table WHERE consumer_id = ?", (session["user_id"],))
            rows = c.fetchall()
            
            c.execute("""UPDATE consumer_table 
			SET reference_code = ?
			WHERE consumer_id = ?
			""",(int(rows[0][0])+6, session["user_id"]))
            
            c.execute("SELECT mobile_id, reference_code, token FROM consumer_table WHERE consumer_id = ?", (session["user_id"],))
            rows = c.fetchall()
            
            payload = {
                "amount": round(float(request.form.get("quantity")),2)*0,
                "description": "sample inteliqas payment",
                "endUserId": str(rows[0][0]),
                "referenceCode": "5051" + str(rows[0][1]),
                "transactionOperationStatus": "Charged"
            }
    
            headers = {
                "Content-Type": "application/json"
            }
            
            url = "https://devapi.globelabs.com.ph/payment/v1/transactions/amount?access_token="
            
            print(json.dumps(payload))
            token = rows[0][2]
    
            resp = requests.post(url + token, data=json.dumps(payload), headers=headers)
            
            print(resp.status_code, resp.text)
            
            if int(resp.status_code) != 201:
                flash("Error has occured. Please try again.")
            else:
                # alert user for successful transaction
                c.execute("""UPDATE producer_table 
				SET switch = 1
				WHERE timestamp = (SELECT timestamp
				FROM producer_table 
				ORDER BY timestamp 
				DESC LIMIT 1)
				""")
                flash("Energy was bought successfully!")
            
            # redirect user to home page
            return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")
        
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """Settings."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        with sqlite3.connect('inteliqas.db') as conn:
            c = conn.cursor()
            c.execute("""UPDATE consumer_table 
			SET mobile_id = ?, reference_code = 2000000
			WHERE consumer_id = ?
			""", (request.form.get("number"), session["user_id"]))
            
            # alert user for successful transaction
            flash("Payment settings updated successfully!")
            
            # redirect user to home page
            return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("settings.html")

@app.route("/monitor", methods=["GET", "POST"])
@login_required
def monitor():
    """Settings."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "GET":

        with sqlite3.connect('inteliqas.db') as conn:
            c = conn.cursor()
            c.execute("""SELECT branch1,
                branch2,
				branch3,
				branch4
				FROM consumer_table 
				WHERE consumer_id = ?""", 
				(session["user_id"],))
            rows = c.fetchall()
            row = rows[0]
            print(row)
            return render_template("monitor.html", b1=row[0],b2=row[1],b3=row[2],b4=row[3])

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("monitor.html", b1=None,b2=None,b3=None,b4=None)
        
        
@app.route('/payment', methods=['GET', 'POST'])
def payment():
		if request.method == 'GET':
		    with sqlite3.connect('inteliqas.db') as conn:
		        c = conn.cursor()
		        c.execute("""UPDATE consumer_table 
    			SET token = ?
    			WHERE mobile_id = ?
    			""", (request.args.get("access_token"), request.args.get("subscriber_number")))
			
		    return "OK"
		
		elif request.method == 'POST':
		    return "OK"
		    
@app.route('/branch', methods=['GET', 'POST'])
def branch():
		if request.method == 'POST':
		    return 'Please use GET request only'
		elif request.method == 'GET':
		    branch = request.args.get("b")
		    value = request.args.get("v")
		    
		    user = session["user_id"]
		    
		    if branch == "b1":
		        col = "branch1"
		    elif branch == "b2":
		        col = "branch2"
		    elif branch == "b3":
		        col = "branch3"
		    elif branch == "b4":
		        col = "branch4"
		        
		    with sqlite3.connect('inteliqas.db') as conn:
		        c = conn.cursor()
		        c.execute("""UPDATE consumer_table 
    			SET {} = ?
    			WHERE consumer_id = ?
    			""".format(col), (value, user))
			
		    return jsonify({"res": "ok"})
	    
# for esp
@app.route('/esprequestproducer', methods=['GET', 'POST'])
def esprequestproducer():
		if request.method == 'GET':
		    return 'Please use POST request only'
		elif request.method == 'POST':
			"""
			 {
			  "espid": 1,
		      "consumption": {
		          "voltage": 1,
		          "current": 1
		      },
		      "distribution": {
		          "voltage": 1,
		          "current": 1
		      },
			  "switch": false,
		      "timestamp": "timestamp"
		    }
			"""
			
			esp_data = request.get_json()
			
			eps_id = esp_data["espid"]
			consumption = esp_data["consumption"]
			distribution = esp_data["distribution"]
			switch = esp_data["switch"]
			
			insert_stmt = """INSERT INTO producer_table 
								(esp_id,
								voltage_consumption,
								current_consumption,
								voltage_distribution,
								current_distribution,
								switch) 
							VALUES (?, ?, ?, ?, ?, ?)"""
			values = (eps_id, 
						consumption["voltage"],
						consumption["current"],
						distribution["voltage"],
						distribution["current"],
						switch,
			)
								
			with sqlite3.connect('inteliqas.db') as conn:
				c = conn.cursor()
				c.execute("""SELECT count(*) FROM producer_table""")
				count_rows = c.fetchall()
				count_row = count_rows[0]
				if int(count_row[0]) == 0:
					c.execute(insert_stmt, values)
					return "INITIAL INSERT"			
				else:
					c.execute("""SELECT (julianday(CURRENT_TIMESTAMP) - julianday(timestamp)) * 1440 
									FROM producer_table 
									ORDER BY timestamp 
									DESC LIMIT 1""")			
					time_rows = c.fetchall()
					time_row = time_rows[0]
					if round(float(time_row[0])) > 2:
						c.execute(insert_stmt, values)
					c.execute("""SELECT esp_id,
									switch
									FROM producer_table 
									ORDER BY timestamp 
									DESC LIMIT 1""")			
					rows = c.fetchall()
					row = rows[0]
					json_response = {
						"espid": row[0],
						"switch": row[1]
					}
					return jsonify(json_response)
			
@app.route('/esprequestconsumer', methods=['GET', 'POST'])
def esprequestconsumer():
		if request.method == 'GET':
			with sqlite3.connect('inteliqas.db') as conn:
				c = conn.cursor()
					
				if request.args.get("update") == "update":
					c.execute("""UPDATE consumer_table 
						SET branch1 = ?
						WHERE timestamp = (SELECT timestamp
						FROM producer_table 
						ORDER BY timestamp 
						DESC LIMIT 1)
						""", (request.args.get("pin")))
				c.execute("""SELECT branch1
					FROM consumer_table 
					ORDER BY timestamp 
					DESC LIMIT 1""")			
				rows = c.fetchall()
				row = rows[0]
				json_response = {
					"branch1": row[0]
				}
		
			return jsonify(json_response)
			
		elif request.method == 'POST':
			"""
			 {
			  "espid": 1,
		      "consumption": {
		          "voltage": 1,
		          "current": 1
		      },
		      "distribution": {
		          "voltage": 1,
		          "current": 1
		      },
		      "branch1": false,
		      "branch2": false,
		      "branch3": false,
		      "branch4": true,
		      "timestamp": "timestamp"
		    }
			"""
			
			esp_data = request.get_json()
			
			eps_id = esp_data["espid"]
			consumption = esp_data["consumption"]
			branch1 = esp_data["branch1"]
			branch2 = esp_data["branch2"]
			branch3 = esp_data["branch3"]
			branch4 = esp_data["branch4"]
			
			insert_stmt = """INSERT INTO producer_table 
								(esp_id,
								voltage_consumption,
								current_consumption,
								branch1,
								branch2,
								branch3,
								branch4) 
							VALUES (?, ?, ?, ?, ?, ?, ?)"""
			values = (eps_id, 
						consumption["voltage"],
						consumption["current"],
						branch1,
						branch2,
						branch3,
						branch4,
			)
								
			with sqlite3.connect('inteliqas.db') as conn:
				c = conn.cursor()
				c.execute("""SELECT count(*) FROM producer_table""")
				count_rows = c.fetchall()
				count_row = count_rows[0]
				if int(count_row[0]) == 0:
					c.execute(insert_stmt, values)
					return "INITIAL INSERT"			
				else:
					c.execute("""SELECT (julianday(CURRENT_TIMESTAMP) - julianday(timestamp)) * 1440 
									FROM producer_table 
									ORDER BY timestamp 
									DESC LIMIT 1""")			
					time_rows = c.fetchall()
					time_row = time_rows[0]
					if round(float(time_row[0])) > 1:
						c.execute(insert_stmt, values)
					c.execute("""SELECT esp_id,
									branch1,
									branch2,
									branch3,
									branch4
									FROM producer_table 
									ORDER BY timestamp 
									DESC LIMIT 1""")			
					rows = c.fetchall()
					row = rows[0]
					json_response = {
						"espid": row[0],
						"branch1": row[1],
						"branch2": row[2],
						"branch3": row[3],
						"branch4": row[4],
					}
					return jsonify(json_response)
