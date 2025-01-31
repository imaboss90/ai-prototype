import boto3
import os
import base64
import io
from PIL import Image
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

# AWS Credentials
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["Company"]
actors_collection = db["actors"]

# Create an S3 client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

def resize_image(image_data, max_width=150):
    """Resize image before uploading to S3."""
    try:
        image = Image.open(io.BytesIO(image_data))
        width_percent = max_width / float(image.width)
        new_height = int(float(image.height) * width_percent)
        image = image.resize((max_width, new_height), Image.LANCZOS)

        # Convert to JPEG
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="JPEG", quality=75)
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"❌ Error resizing image: {e}")
        return None

def upload_image_to_s3(actor_id, image_data):
    """Upload an image to S3 and return the public URL."""
    try:
        s3_filename = f"actors/{actor_id}.jpg"

        print(f"🔹 Uploading to S3 Bucket: {AWS_S3_BUCKET}")

        s3_client.upload_fileobj(
            io.BytesIO(image_data),
            AWS_S3_BUCKET,
            s3_filename,
            ExtraArgs={"ContentType": "image/jpeg"}  # ✅ No ACL here
        )

        return f"https://{AWS_S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_filename}"

    except Exception as e:
        print(f"❌ S3 Upload Error for Actor ID {actor_id}: {e}")
        return None

def migrate_images():
    """Find all actors with binary images, upload to S3, and update MongoDB."""
    actors = actors_collection.find({"image.data": {"$exists": True}})

    for actor in actors:
        actor_id = str(actor["_id"])
        image_data = actor["image"]["data"]

        print(f"📤 Uploading image for Actor ID: {actor_id}...")

        # Upload image to S3
        s3_url = upload_image_to_s3(actor_id, image_data)
        if s3_url:
            # Update MongoDB with the new S3 URL
            actors_collection.update_one(
                {"_id": ObjectId(actor_id)},
                {"$set": {"image_url": s3_url}, "$unset": {"image": ""}}  # Remove binary image field
            )
            print(f"✅ Image uploaded for Actor ID {actor_id}: {s3_url}")
        else:
            print(f"❌ Failed to upload image for Actor ID {actor_id}")

if __name__ == "__main__":
    migrate_images()
