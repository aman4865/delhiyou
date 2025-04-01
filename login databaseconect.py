from flask import Flask, request, jsonify, session
from flask_mysqldb import MySQL
from flask_socketio import SocketIO, emit
import hashlib
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for session storage
CORS(app, supports_credentials=True)  # Allow frontend access

socketio = SocketIO(app, cors_allowed_origins="*")

# MySQL Configuration
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "1234"
app.config["MYSQL_DB"] = "user_auth"

mysql = MySQL(app)

# Function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# User Registration
@app.route("/register", methods=["POST"])
def register_user():
    data = request.json
    full_name = data["full_name"]
    email = data["email"]
    mobile_number = data["mobile_number"]
    password = hash_password(data["password"])

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("INSERT INTO users (full_name, email, mobile_number, password_hash) VALUES (%s, %s, %s, %s)", 
                       (full_name, email, mobile_number, password))
        mysql.connection.commit()
        return jsonify({"message": "Registration successful!"})
    except:
        return jsonify({"error": "Email or mobile number already registered."}), 400
    finally:
        cursor.close()

# User Login
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data["email"]
    password = hash_password(data["password"])

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM users WHERE email = %s AND password_hash = %s", (email, password))
    user = cursor.fetchone()
    cursor.close()

    if user:
        session["username"] = user[1]  # Store username in session
        return jsonify({"message": "Login successful!", "username": user[1]})
    return jsonify({"error": "Invalid email or password."}), 401

# Get Messages
@app.route("/messages", methods=["GET"])
def get_messages():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM messages ORDER BY created_at DESC")
    messages = cursor.fetchall()
    cursor.close()
    return jsonify([{"id": row[0], "username": row[1], "message": row[2], "created_at": row[3]} for row in messages])

# WebSocket: Send Message
@socketio.on("send_message")
def handle_message(data):
    username = session.get("username", data.get("username"))  # Get session username
    message = data.get("message")

    if not username or not message:
        emit("error", {"error": "Invalid message data"}, broadcast=False)
        return

    # Validate if user exists before storing messages
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM users WHERE full_name = %s", (username,))
    user = cursor.fetchone()

    if not user:
        emit("error", {"error": "Unauthorized user"}, broadcast=False)
        return

    # Store message in MySQL
    cursor.execute("INSERT INTO messages (username, message) VALUES (%s, %s)", (username, message))
    mysql.connection.commit()
    cursor.close()

    # Send the message to all clients
    emit("receive_message", {"username": username, "message": message}, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)

