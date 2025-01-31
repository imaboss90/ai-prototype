from pymongo import MongoClient
import openai
import os
from dotenv import load_dotenv
import random
import json

load_dotenv()  # Load environment variables from .env

# Set up MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://<username>:<password>@cluster0.mongodb.net/Company?retryWrites=true&w=majority")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["Company"]
actors_collection = db["actors"]  # MongoDB collection for actors

openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_actors_bulk():
    prompt = (
    "Generate exactly 7 diverse actors in a JSON array format. Each actor must have:\n"
    "- user_id: A unique number between 21 and 10000.\n"
    "- name: A unique and realistic full name.\n"
    "- age: A number between 18 and 70.\n"
    "- gender: One of ['Male', 'Female', 'Other'].\n"
    "- race: A realistic race or ethnicity.\n"
    "- height: A realistic height in feet and inches (e.g., '5'9\").\n"
    "- location: A city and country (e.g., 'New York, USA').\n"
    "- languages: A list of 1-3 languages the actor speaks.\n"
    "- roles: A list of 1-5 roles they've played.\n"
    "- image_url: A placeholder URL for the actor's image.\n"
    "Ensure that:\n"
    "- The output strictly follows valid JSON format.\n"
    "- The array contains exactly 50 actors.\n"
    "- There are no comments, ellipses, or placeholder text like '...'.\n"
    "- No explanation is provided—only return the raw JSON array."
)

    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant that generates data in JSON format."},
            {"role": "user", "content": prompt}
        ]

        response = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=7800
        )

        # Access response content
        raw_response = response.choices[0].message.content
        print(raw_response)  # Debugging: Print the raw response

        # Parse the content as JSON
        actors = json.loads(raw_response)
        return actors

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {str(e)}")
        print("Raw response:", raw_response)
        return None
    except Exception as e:
        print(f"Error generating actors: {str(e)}")
        return None

# Check for duplicate or similar names
def is_duplicate_or_similar(actor_name, existing_names):
    for name in existing_names:
        # Check for exact match or similar names (case insensitive)
        if actor_name.lower() == name.lower() or actor_name.split()[0].lower() == name.split()[0].lower():
            return True
    return False

# Store the generated actors in MongoDB
def store_actors_in_db(actors):
    if actors:
        existing_names = [actor["name"] for actor in actors_collection.find({}, {"name": 1, "_id": 0})]

        for actor in actors:
            if is_duplicate_or_similar(actor["name"], existing_names):
                print(f"Skipped duplicate or similar actor: {actor['name']}")
                continue

            # Add a placeholder image URL if not present
            actor["image_url"] = actor.get("image_url", "https://placeholder.com/image.jpg")

            try:
                # Insert each actor into the MongoDB collection
                actors_collection.insert_one(actor)
                existing_names.append(actor["name"])
                print(f"Actor {actor['name']} added to the database.")
            except Exception as e:
                print(f"Error inserting actor into MongoDB: {str(e)}")

if __name__ == "__main__":
    actors = generate_actors_bulk()
    if actors:
        store_actors_in_db(actors)