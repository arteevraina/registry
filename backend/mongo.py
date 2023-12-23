import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
from gridfs import GridFS
from app import app
from flask import jsonify
import subprocess

load_dotenv()
database_name = os.environ["MONGO_DB_NAME"]
try:
    mongo_uri = os.environ["MONGO_URI"]
    mongo_username = os.environ["MONGO_USER_NAME"]
    mongo_password = os.environ["MONGO_PASSWORD"]
    client = MongoClient(mongo_uri)
except KeyError as err:
    print("Add MONGO_URI to .env file")

db = client[database_name]
file_storage = GridFS(db, collection="tarballs")


@app.route("/registry/archives", methods=["GET"])
def clone():
    folder_path = "static"
    file_list = os.listdir(folder_path)
    return jsonify(
        {"message": "Successfully Fetched Archives", "archives": file_list, "code": 200}
    )
