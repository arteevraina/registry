import os
from dotenv import load_dotenv
import hashlib
from app import app
from mongo import db
from flask import request, jsonify
from app import swagger
from flasgger.utils import swag_from
from auth import forgot_password

load_dotenv()

try:
    salt = os.getenv("SALT")
except KeyError as err:
    print("Add SALT to .env file")


@app.route("/users/<username>", methods=["GET"])
@swag_from("documentation/user.yaml", methods=["GET"])
def profile(username):
    user = db.users.find_one({"username": username})
    if user:
        packages = db.packages.find(
            {"$or": [{"author": user["_id"]}, {"maintainers": user["_id"]}]},
        )

        response_packages = []
        if packages:
            for package in packages:
                # Get namespace from namespace id.
                namespace = db.namespaces.find_one({"_id": package["namespace"]})
                user = db.users.find_one({"_id": package["author"]})
                namespace = db.namespaces.find_one({"_id": package["namespace"]})
                response_packages.append(
                    {
                        "name": package["name"],
                        "namespace": namespace["namespace"],
                        "description": package["description"],
                        "updatedAt": package["updatedAt"],
                        "author": user["username"],
                    }
                )
        user_account = {
            "username": user["username"],
            "email": user["email"],
            "createdAt": user["createdAt"],
            "packages": response_packages,
        }
        return (
            jsonify(
                {
                    "message": "User found",
                    "user": user_account,
                    "packages": response_packages,
                    "code": 200,
                }
            ),
            200,
        )
    else:
        return jsonify({"message": "User not found", "code": 404}), 404


@app.route("/users/delete", methods=["POST"])
@swag_from("documentation/delete_user.yaml", methods=["POST"])
def delete_user():
    uuid = request.form.get("uuid")
    password = request.form.get("password")
    username = request.form.get("username")

    if not uuid:
        return jsonify({"message": "Unauthorized", "code": 401}), 401
    else:
        user = db.users.find_one({"uuid": uuid})

    if not user:
        return "Invalid email or password", 401

    if password:
        password += salt
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        if hashed_password != user["password"]:
            return jsonify({"message": "Invalid email or password", "code": 401}), 401
        else:
            db.users.delete_one({"uuid": uuid})
            return jsonify({"message": "User deleted", "code": 200}), 200

    elif username and "admin" in user["roles"]:
        delete_user = db.users.find_one({"username": username})
        if delete_user:
            db.users.delete_one({"username": username})
            return jsonify({"message": "User deleted", "code": 200}), 200
        else:
            return jsonify({"message": "User not found", "code": 404}), 404

    else:
        return jsonify({"message": "Unauthorized", "code": 401}), 401


@app.route("/users/account", methods=["POST"])
@swag_from("documentation/account.yaml", methods=["POST"])
def account():
    uuid = request.form.get("uuid")
    if not uuid:
        return jsonify({"message": "Unauthorized", "code": 401}), 401
    else:
        user = db.users.find_one({"uuid": uuid})

    if not user:
        return jsonify({"message": "User not found", "code": 404}), 404

    user_account = {
        "username": user["username"],
        "email": user["email"],
        "createdAt": user["createdAt"],
        "loginAt": user["loginAt"],
        "lastLogout": user["lastLogout"],
    }
    return jsonify({"message": "User Found", "user": user_account, "code": 200}), 200


@app.route("/users/admin", methods=["POST"])
@swag_from("documentation/admin.yaml", methods=["POST"])
def admin():
    uuid = request.form.get("uuid")
    if not uuid:
        return jsonify({"message": "Unauthorized", "code": 401}), 401
    else:
        user = db.users.find_one({"uuid": uuid})

    if not user:
        return jsonify({"message": "User not found", "code": 404}), 404
    
    if "admin" not in user["roles"]:
        return jsonify({"message": "Unauthorized", "code": 401}), 401
    else:
        return (
            jsonify({"message": "User is admin", "isAdmin": "true", "code": 200}),
            200,
        )


@app.route("/users/admin/transfer", methods=["POST"])
@swag_from("documentation/admin.yaml", methods=["POST"])
def transfer_account():
    uuid = request.form.get("uuid")
    if not uuid:
        return jsonify({"message": "Unauthorized", "code": 401}), 401
    else:
        user = db.users.find_one({"uuid": uuid})

    if not user:
        return jsonify({"message": "User not found", "code": 404}), 404

    if "admin" not in user["roles"]:
        return jsonify({"message": "Unauthorized", "code": 401}), 401
    else:
        old_user = request.form.get("old_username")
        new_user = request.form.get("new_username")
        new_email = request.form.get("new_email")
        db.users.update_one(
            {"username": old_user},
            {
                "$set": {
                    "email": new_email,
                    "username": new_user,
                    "uuid": "",
                    "loggedCount": 0,
                    "loginAt": None,
                    "lastLogout": None,
                }
            },
        )
        forgot_password(new_email)
        return (
            jsonify(
                {
                    "message": "Account Transfer Successful and Password reset request sent.",
                    "code": 200,
                }
            ),
            200,
        )

@app.route("/users/<username>/maintainer", methods=["GET", "POST"])
@swag_from('documentation/maintainer_invites_get.yaml', methods=["GET"])
@swag_from('documentation/maintainer_invites_post.yaml', methods=["POST"])
def maintainer_requests(username):
    uuid = request.cookies.get("uuid")
    if not uuid:
        return jsonify({"message": "Unauthorized", "code": 403})

    # Get the user from the database using uuid.
    user = db.users.find_one({"uuid": uuid})

    # If the user is not found or user name does not match. Just return unauthorized.
    if not user or user["name"] != username:
        return jsonify({"message": "Unauthorized", "code": 403})

    if request.method == "GET": 
        # Extract the pending_requests list from the user document.
        # pending_requests list contains the package_id's of the package's that
        # author has received the request to join in as maintainer.
        pending_requests = user.get("pending_requests")
        pending_requests_response = []

        for package_id in pending_requests:
            # Get package using package_id from the database.
            package = db.packages.find_one({"_id": package_id})

            # Get the author using _id from the database.
            author = db.users.find_one({"_id": package["author"]})

            pending_requests_response.append({
                "package_name": package["name"],
                "author_name": author["name"],
                "package_id": package["_id"]
            })

        return jsonify({"data": pending_requests_response, "code": 200}) 
    
    else:
        # Extract whether the request is approve or decline from json payload.
        data = request.get_json()

        if 'status' in data and 'package_id' in data:
            active_package_id = data['package_id']
            status = data['status']
            if status == 'approved':
                
                # Add user's _id to the package maintainer's field.
                db.packages.update_one(
                    {"_id": active_package_id}, 
                    {"$push": {"maintainers": user["_id"]}}
                )
                # package_id gets added to the maintainerOf list in user document.
                db.users.update_one(
                    {"_id": user["_id"]}, 
                    {"$push": {"maintainerOf": active_package_id}}
                )
                db.users.update_one(
                    {"_id": user["_id"]}, 
                    {"$pull": {"pending_requests": {"$eq": active_package_id}}}
                )    

                return jsonify({"message": "Invite accepted", "code": 200})
            elif status == 'declined':
                db.users.update_one(
                    {"_id": user["_id"]}, 
                    {"$pull": {"pending_requests": {"$eq": active_package_id}}}
                )
                return jsonify({"message": "Invite declined", "code": 200})    
        else:
            return jsonify({"message": "Both fields status and package_id are required", "code": 400})
