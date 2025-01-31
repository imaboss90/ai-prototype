from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from pymongo import MongoClient
from PIL import Image
import os
import base64
import re
import io
import boto3
import json
from bson import ObjectId
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env


app = Flask(__name__)

# Set up OpenAI client using API key from .env
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://<username>:<password>@cluster0.mongodb.net/Company?retryWrites=true&w=majority")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["Company"]
scripts_collection = db["scripts"]  # MongoDB collection for scripts
actors_collection = db["actors"]
roles_collection = db["roles"]  

# S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

@app.route('/')
def home():
    return render_template('home.html')

def resize_image(image_data, max_width=300):
    """Resize image to reduce load time."""
    try:
        image = Image.open(io.BytesIO(image_data))
        width_percent = max_width / float(image.width)
        new_height = int((float(image.height) * float(width_percent)))
        image = image.resize((max_width, new_height), Image.LANCZOS)

        # Convert to JPEG
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="JPEG")
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"Error resizing image: {e}")
        return None

@app.route('/api/actor_image/<actor_id>')
def get_actor_image(actor_id):
    """Fetch and serve an actor's image from MongoDB."""
    try:
        actor = actors_collection.find_one({"_id": ObjectId(actor_id)}, {"image": 1})
        
        if not actor or "image" not in actor or "data" not in actor["image"]:
            print(f"❌ Image not found for actor ID: {actor_id}")
            return jsonify({"image": ""})  # Return empty response

        # Resize and convert image to Base64
        resized_image = resize_image(actor["image"]["data"])
        if not resized_image:
            return jsonify({"image": ""})

        image_base64 = base64.b64encode(resized_image).decode("utf-8")
        return jsonify({"image": f"data:image/jpeg;base64,{image_base64}"})
    
    except Exception as e:
        print(f"❌ Error processing image for actor {actor_id}: {e}")
        return jsonify({"image": ""})
    
@app.route('/find_actors')
def find_actors():
    """Fetch all actors and their S3 image URLs along with additional details."""
    actors = list(actors_collection.find({}, {
        "_id": 1, "name": 1, "gender": 1, "age": 1,
        "race": 1, "height": 1, "location": 1, "languages": 1,
        "roles": 1, "image_url": 1  # Keep stored S3 URL
    }))

    # Convert `_id` to string for JSON
    for actor in actors:
        actor['_id'] = str(actor['_id'])

    return render_template('find_actors.html', actors=actors)

@app.route('/generate_script', methods=['GET', 'POST'])
def generate_script():
    if request.method == 'GET':
        return render_template('generate_script.html')

    if request.method == 'POST':
        prompt = request.form.get('prompt', '').strip()

        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        try:
            # Generate a script using OpenAI with proper screenplay formatting
            completion = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional screenwriter. Write a well-structured, formatted screenplay in standard industry style."},
                    {"role": "user", "content": f"""
                        Write a screenplay based on the following prompt:

                        {prompt}

                        Use this format:
                        - No hashtags or asterisks.
                        - Use proper screenplay structure (FADE IN, INT./EXT., Character names in uppercase, dialogue centered, actions in plain text).
                        - Keep scene headings clear.
                        - Ensure dialogue is formatted correctly under character names.

                        Begin now:
                    """}
                ],
                max_tokens=3000,
                temperature=0.7
            )
            generated_script = completion.choices[0].message.content.strip()

            # Extract a title from the script
            title_completion = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You generate short, relevant titles for screenplays."},
                    {"role": "user", "content": f"Generate a short, relevant title for this screenplay:\n{generated_script}"}
                ],
                max_tokens=30,
                temperature=0.5
            )
            title = title_completion.choices[0].message.content.strip()

            # Save to MongoDB
            script_data = {
                "Prompt": prompt,
                "Script": generated_script,
                "Title": title,
                "Roles": 0,
                "Date": datetime.now(timezone.utc),
                "Complete": False
            }
            scripts_collection.insert_one(script_data)

            return render_template('generate_script.html', generated_script=script_data)

        except Exception as e:
            return jsonify({"error": str(e)}), 500

        
@app.route('/past_scripts')
def past_scripts():
    scripts = list(scripts_collection.find())

    for script in scripts:
        script_id = script['_id']
        roles = list(roles_collection.find({"script_id": script_id}))

        for role in roles:
            if 'actor_id' in role and role['actor_id']:
                actor = actors_collection.find_one(
                    {"_id": ObjectId(role['actor_id'])}, {"name": 1, "image_url": 1}
                )
                if actor:
                    role['actor_name'] = actor.get("name", "Unknown")
                    role['actor_image_url'] = actor.get("image_url", "/static/no-image.jpg")
                else:
                    role['actor_name'] = "Unknown"
                    role['actor_image_url'] = "/static/no-image.jpg"

        # ✅ Make sure all assigned roles appear in the script's `RolesList`
        script['RolesList'] = roles

    return render_template('past_scripts.html', scripts=scripts)

import re

@app.route('/find_roles', methods=['GET', 'POST'])
def find_roles():
    """Find roles from an existing script in the database."""
    scripts = list(scripts_collection.find({}, {"_id": 1, "Title": 1}))

    roles = None
    matches = {}

    if request.method == 'POST':
        script_id = request.form.get("script_id")

        if not script_id:
            return jsonify({"error": "Please select a script"}), 400

        script_id = ObjectId(script_id)

        # ✅ Check if roles already exist for this script
        existing_roles = list(roles_collection.find({"script_id": script_id}))

        if existing_roles:
            print("⚠️ Roles already exist, using existing data.")
            roles = existing_roles  # Use existing roles
        else:
            # ✅ Fetch script content
            script = scripts_collection.find_one({"_id": script_id}, {"Script": 1})

            if not script:
                return jsonify({"error": "Script not found"}), 404

            script_text = script["Script"]

            # 🏆 Extract roles using OpenAI (Now includes race & languages)
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert script analyst trained to extract character roles for casting."},
                    {"role": "user", "content": f"""
                        Analyze this script and return a JSON list of roles.
                        Use this exact format:

                        {{
                          "roles": [
                            {{
                              "role_name": "John",
                              "gender": "Male",
                              "age_range": "30-40",
                              "race": "Caucasian",
                              "languages_spoken": ["English", "French"],
                              "physical_traits": "Tall, muscular",
                              "personality_traits": "Serious, determined",
                              "notable_characteristics": "Always carries a notebook"
                            }}
                          ]
                        }}

                        Script:
                        {script_text}

                        - If a role does not specify race, return "N/A".
                        - If a role does not specify languages, return ["N/A"].
                        - **If the script provides an approximate age like "30s", "40s", or "mid-20s", you must convert it to an exact age or range.**
                        - Example: "30s" → Use either **"30-40"** or pick a specific number like **"32"**.
                        - Example: "mid-20s" → Convert to **"24-28"**.
                        - Example: "early 40s" → Convert to **"40-45"**.
                        - Do **NOT** use vague terms like **"20s" or "mid-30s"**.
                    """}
                ],
                max_tokens=4000,
                temperature=0.7
            )

            # 🔍 Process OpenAI response
            cleaned_json = re.sub(r"```json|```", "", response.choices[0].message.content.strip())
            roles_data = json.loads(cleaned_json)

            if "roles" not in roles_data:
                raise ValueError("OpenAI response does not contain 'roles' key")

            roles = roles_data["roles"]

            # ✅ Save extracted roles into MongoDB with the script_id
            for role in roles:
                role["script_id"] = script_id  # Link role to script
                roles_collection.insert_one(role)

            # ✅ Store role count in the script collection
            role_count = len(roles)
            scripts_collection.update_one(
                {"_id": script_id},
                {"$set": {"role_numbers": role_count}}
            )

        # 🏆 Match actors to roles
        matches = match_actors_to_roles(script_id)

        return render_template('find_roles.html', scripts=scripts, roles=roles, script_id=script_id, matches=matches)

    return render_template('find_roles.html', scripts=scripts, roles=roles or [], matches=matches)



def match_actors_to_roles(script_id):
    """Matches actors to roles using optimized filtering (no OpenAI)."""

    roles = list(roles_collection.find({"script_id": script_id}, {
        "_id": 0, "role_name": 1, "gender": 1, "age_range": 1, "race": 1, "languages_spoken": 1
    }))

    matches = {}

    for role in roles:
        role_name = role["role_name"]
        role_gender = role.get("gender", "").strip().lower()
        role_age_range = role.get("age_range", "N/A").strip().lower()
        role_race = role.get("race", "N/A").strip().lower()
        role_languages = role.get("languages_spoken", ["N/A"])  # Ensure list format

        # ✅ Handle missing or vague age ranges
        role_min_age, role_max_age = 0, 100  # Default range for unspecified values
        if role_age_range.isdigit():  # If only one number is provided (e.g., "12")
            role_min_age = int(role_age_range)
            role_max_age = role_min_age + 2  # Small range for accuracy
        elif "-" in role_age_range:  # Proper range format like "30-40"
            try:
                role_min_age, role_max_age = map(int, role_age_range.split("-"))
            except ValueError:
                role_min_age, role_max_age = 25, 40  # Default range if parsing fails
        elif "under" in role_age_range or "below" in role_age_range:
            role_min_age, role_max_age = 0, int(re.search(r"\d+", role_age_range).group())  # Extract number
        elif "over" in role_age_range or "above" in role_age_range:
            role_min_age, role_max_age = int(re.search(r"\d+", role_age_range).group()), 100  # Extract number

        print(f"🔍 Role: {role_name} | Age: {role_min_age}-{role_max_age} | Gender: {role_gender} | Race: {role_race} | Languages: {role_languages}")

        # ✅ Gender Filtering
        gender_filter = {} if role_gender in ["unspecified", "", "n/a"] else {
            "gender": {"$regex": f"^{role_gender}$", "$options": "i"}  # Case-insensitive match
        }

        # ✅ Race Filtering
        race_filter = {} if role_race in ["n/a", "unspecified", ""] else {
            "race": {"$regex": f"^{role_race}$", "$options": "i"}
        }

        # ✅ Language Filtering (Matches if actor speaks at least one of the required languages)
        language_filter = {} if "n/a" in [lang.lower() for lang in role_languages] else {
            "languages": {"$in": role_languages}  # Matches if at least one language exists
        }

        # ✅ Use MongoDB to filter actors **before fetching**
        actors_cursor = actors_collection.find({
            **gender_filter,
            **race_filter,
            **language_filter,
            "age": {"$gte": role_min_age, "$lte": role_max_age}
        }, {"_id": 1, "name": 1, "age": 1, "gender": 1, "race": 1, "languages": 1, "location": 1, "image_url": 1})

        # ✅ Convert cursor to a list of actor dictionaries
        best_matches = [
            {
                "_id": str(actor["_id"]),  # Convert `_id` to string
                "name": actor["name"],
                "age": actor["age"],
                "gender": actor["gender"],
                "race": actor.get("race", "Unknown"),
                "languages": actor.get("languages", ["Unknown"]),
                "location": actor.get("location", "Unknown"),
                "image_url": actor.get("image_url", "/static/no-image.jpg")  # Default image if missing
            }
            for actor in actors_cursor
        ]

        matches[role_name] = best_matches if best_matches else ["No matching actors found."]

    return matches

@app.route('/ask_ai', methods=['POST'])
def ask_ai():
    """Use OpenAI to determine the best actor match for a role and provide reasoning."""
    data = request.json
    role_name = data.get('role_name')
    selected_actors = data.get('actors')

    if not role_name or not selected_actors:
        return jsonify({"error": "Missing role or actors"}), 400

    # Retrieve role details from MongoDB
    role = roles_collection.find_one({"role_name": role_name}, {
        "_id": 0, "gender": 1, "age_range": 1, "race": 1, "languages_spoken": 1,
        "physical_traits": 1, "personality_traits": 1, "notable_characteristics": 1
    })

    if not role:
        return jsonify({"error": "Role not found"}), 404

    role_description = f"""
    Role Name: {role_name}
    Gender: {role.get('gender', 'N/A')}
    Age Range: {role.get('age_range', 'N/A')}
    Race: {role.get('race', 'N/A')}
    Languages Spoken: {', '.join(role.get('languages_spoken', ['N/A']))}
    Physical Traits: {role.get('physical_traits', 'N/A')}
    Personality Traits: {role.get('personality_traits', 'N/A')}
    Notable Characteristics: {role.get('notable_characteristics', 'N/A')}
    """

    # Prepare actor descriptions
    actor_descriptions = "\n".join([f"- {actor}" for actor in selected_actors])

    # Call OpenAI
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are an expert in talent casting. Analyze the given role and selected actors to determine the best fit and provide reasoning."},
            {"role": "user", "content": f"""
                Based on the following role description and selected actors, return the best fit actor and provide reasoning.

                Role Description:
                {role_description}

                Selected Actors:
                {actor_descriptions}

                Response format:
                {{
                    "best_actor": "Actor Name",
                    "reasoning": "Explain why this actor is the best choice."
                }}
            """}
        ],
        max_tokens=200,
        temperature=0.7
    )

    # Extract JSON response from OpenAI
    import json
    result = json.loads(response.choices[0].message.content.strip())

    return jsonify({
        "best_actor": result.get("best_actor", "No selection made"),
        "reasoning": result.get("reasoning", "No explanation provided")
    })
@app.route('/assign_actor', methods=['POST'])
def assign_actor():
    """Assigns an actor to a role in the correct script."""
    data = request.json
    role_name = data.get("role_name")
    actor_id = data.get("actor_id")

    if not role_name or not actor_id:
        return jsonify({"error": "Missing role name or actor ID"}), 400

    try:
        actor_object_id = ObjectId(actor_id)
    except Exception:
        return jsonify({"error": "Invalid actor ID"}), 400

    # Find the exact role in the script
    role = roles_collection.find_one({"role_name": role_name, "actor_id": {"$exists": False}})

    if not role:
        return jsonify({"error": "Role not found or already assigned"}), 404

    script_id = role.get("script_id")

    if not script_id:
        return jsonify({"error": "Script ID not found for role"}), 404

    # ✅ Ensure an actor isn't assigned to multiple roles in the same script
    existing_assignment = roles_collection.find_one({
        "script_id": script_id,
        "actor_id": actor_object_id
    })
    if existing_assignment:
        return jsonify({"error": "Actor is already assigned to a role in this script"}), 400

    # ✅ Assign the actor to the specific role within the script
    roles_collection.update_one(
        {"_id": role["_id"]},
        {"$set": {"actor_id": actor_object_id}}
    )

    # ✅ Check if all roles in the script are assigned
    total_roles = scripts_collection.find_one({"_id": script_id}, {"role_numbers": 1}).get("role_numbers", 0)
    assigned_roles_count = roles_collection.count_documents({"script_id": script_id, "actor_id": {"$exists": True}})

    if assigned_roles_count == total_roles:
        scripts_collection.update_one({"_id": script_id}, {"$set": {"complete": True}})

    return jsonify({"success": True})


if __name__ == '__main__':
    app.run(debug=True)
