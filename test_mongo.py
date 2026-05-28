import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.environ.get("MONGO_URI")

print("MONGO_URI found:", bool(uri))

if uri:
    print("URI starts with:", uri[:20])
    print("Cluster part:", uri.split("@")[-1])

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    print("✅ MongoDB Atlas connected successfully!")
except Exception as e:
    print("❌ MongoDB connection failed:")
    print(e)