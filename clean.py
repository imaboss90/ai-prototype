from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv() 

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://<username>:<password>@cluster0.mongodb.net/Company?retryWrites=true&w=majority")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["Company"]
actors_collection = db["actors"]  # MongoDB collection for actors

def check_for_duplicates():
    """
    Check for duplicate names or duplicate user ID numbers in the actors collection.
    """
    try:
        all_actors = list(actors_collection.find())
        name_counts = {}
        user_id_counts = {}

        # Count occurrences of names and user IDs
        for actor in all_actors:
            name = actor.get("name", "")
            user_id = actor.get("user_id", None)

            if name:
                name_counts[name] = name_counts.get(name, 0) + 1
            if user_id is not None:
                user_id_counts[user_id] = user_id_counts.get(user_id, 0) + 1

        # Find duplicates
        duplicate_names = [name for name, count in name_counts.items() if count > 1]
        duplicate_user_ids = [user_id for user_id, count in user_id_counts.items() if count > 1]

        print("Duplicate Names:", duplicate_names)
        print("Duplicate User IDs:", duplicate_user_ids)

    except Exception as e:
        print(f"Error checking for duplicates: {str(e)}")

def clear_all_image_urls():
    """
    Replace every image_url in the actors collection with an empty string.
    """
    try:
        result = actors_collection.update_many({}, {"$set": {"image_url": ""}})
        print(f"Updated {result.modified_count} actors to clear image URLs.")
    except Exception as e:
        print(f"Error clearing image URLs: {str(e)}")

if __name__ == "__main__":
    # Example usage
    check_for_duplicates()
    clear_all_image_urls()
