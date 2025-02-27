import os
from dotenv import load_dotenv
from flask import request, jsonify
from datetime import datetime
from uuid import uuid4
from app import app
from mongo import db
import hashlib
from app import swagger
import smtplib
from flasgger.utils import swag_from

load_dotenv()

env_var = dict()

try:
    salt = os.getenv("SALT")
    sudo_password = os.getenv("SUDO_PASSWORD")
    fortran_email = os.getenv("RESET_EMAIL")
    fortran_password = os.getenv("RESET_PASSWORD")
    host = os.getenv("HOST")
    env_var["host"] = host
    env_var["salt"] = salt
    env_var["sudo_password"] = sudo_password
    smtp = smtplib.SMTP('smtp.gmail.com', 587)
    smtp.starttls()
    smtp.login(fortran_email, fortran_password)

except KeyError as err:
    print("Add SALT to .env file")


def generate_uuid():
    while True:
        uuid = uuid4().hex
        user = db.users.find_one({"uuid": uuid})
        if not user:
            return uuid


@app.route("/auth/login", methods=["POST"])
@swag_from("documentation/login.yaml", methods=["POST"])
def login():
    salt = env_var["salt"]
    email = request.form.get("email")
    password = request.form.get("password")
    password += salt
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    user = db.users.find_one({"email": email, "password": hashed_password})

    if not user:
        return jsonify({"message": "Invalid email or password", "code": 401}), 401

    uuid = generate_uuid() if user["loggedCount"] == 0 else user["uuid"]

    user["loggedCount"] += 1

    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "loginAt": datetime.utcnow(),
                "uuid": uuid,
                "loggedCount": user["loggedCount"],
            }
        },
    )

    return (
        jsonify(
            {
                "message": "Login successful",
                "uuid": uuid,
                "code": 200,
                "username": user["username"],
            }
        ),
        200,
    )


@app.route("/auth/signup", methods=["POST"])
@swag_from("documentation/signup.yaml", methods=["POST"])
def signup():
    uuid = request.form.get("uuid")
    sudo_password = env_var["sudo_password"]
    salt = env_var["salt"]

    if not uuid:
        uuid = generate_uuid()

    username = request.form.get("username")
    email = request.form.get("email")
    email = email.lower()
    password = request.form.get("password")

    if not username:
        return jsonify({"message": "Username is required", "code": 400}), 400

    if not email:
        return jsonify({"message": "Email is required", "code": 400}), 400

    if not password:
        return jsonify({"message": "Password is required", "code": 400}), 400

    password += salt
    sudo_password += salt
    sudo_hashed_password = hashlib.sha256(sudo_password.encode()).hexdigest()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    registry_user = db.users.find_one(
        {"$or": [{"username": username}, {"email": email}]}
    )

    user = {
        "username": username,
        "email": email,
        "password": hashed_password,
        "lastLogout": None,
        "loginAt": datetime.utcnow(),
        "createdAt": datetime.utcnow(),
        "uuid": uuid,
        "loggedCount": 1,
    }

    if hashed_password == sudo_hashed_password:
        user["roles"] = ["admin"]
        forgot_password(email)
    else:
        user["roles"] = ["user"]

    if not registry_user:
        db.users.insert_one(user)

        return (
            jsonify(
                {
                    "message": "Signup successful",
                    "uuid": uuid,
                    "code": 200,
                    "username": user["username"],
                }
            ),
            200,
        )
    else:
        return (
            jsonify(
                {
                    "message": "A user with this email or username already exists",
                    "code": 400,
                }
            ),
            400,
        )


@app.route("/auth/logout", methods=["POST"])
@swag_from("documentation/logout.yaml", methods=["POST"])
def logout():
    uuid = request.form.get("uuid")
    if not uuid:
        return jsonify({"message": "User not found", "code": 404})

    user = db.users.find_one({"uuid": uuid})
    if not user:
        return jsonify({"message": "User not found", "code": 404})

    user["loggedCount"] -= 1

    uuid = "" if user["loggedCount"] == 0 else uuid

    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "lastLogout": datetime.utcnow(),
                "uuid": uuid,
                "loggedCount": user["loggedCount"],
            }
        },
    )

    return jsonify({"message": "Logout successful", "code": 200}), 200


@app.route("/auth/reset-password", methods=["POST"])
@swag_from("documentation/reset_password.yaml", methods=["POST"])
def reset_password():
    password = request.form.get("password")
    oldpassword = request.form.get("oldpassword")
    uuid = request.form.get("uuid")
    user = db.users.find_one({"uuid": uuid})
    salt = env_var["salt"]

    if not user:
        return jsonify({"message": "User not found", "code": 404}), 404

    if oldpassword:
        oldpassword += salt
        hashed_password = hashlib.sha256(oldpassword.encode()).hexdigest()
        if hashed_password != user["password"]:
            return jsonify({"message": "Invalid password", "code": 401}), 401

    password += salt
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    db.users.update_one(
        {"uuid": uuid},
        {"$set": {"password": hashed_password, "uuid": "", "loggedCount": 0}},
    )
    return jsonify({"message": "Password reset successful", "code": 200}), 200


@app.route("/auth/forgot-password", methods=["POST"])
@swag_from("documentation/forgot_password.yaml", methods=["POST"])
def forgot_password(*email):
    try:
        email = request.form.get("email") if request.form.get("email") else email[0]
    except:
        return jsonify({"message": "Email is required", "code": 400}), 400

    user = db.users.find_one({"email": email})

    if not user:
        return jsonify({"message": "User not found", "code": 404}), 404

    uuid = generate_uuid()
    db.users.update_one({"email": email}, {"$set": {"uuid": uuid, "loggedCount": 1}})

    message = f"""\n
    Dear {user['username']},

    We received a request to reset your password. To reset your password, please copy paste the link below in a new browser window:

    {env_var['host']}/account/reset-password/{uuid}

    Thank you,
    The Fortran-lang Team"""

    message = f'Subject: Password reset link\nTo: {email}\n{message}'
    
    # sending the mail
    smtp.sendmail(to_addrs=email, msg=message, from_addr=fortran_email)

    return (
        jsonify({"message": "Password reset link sent to your email", "code": 200}),
        200,
    )
