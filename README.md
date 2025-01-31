# 🎭 Talent Casting AI

**Talent Casting AI** is a Flask-based web application designed to streamline talent casting for film and TV productions. It leverages AI to generate scripts, match actors to roles, and suggest the best casting choices.

## 📌 Features
- 🎬 **AI-Powered Script Generation** – Uses OpenAI to create formatted screenplays.
- 🔎 **Find and Match Actors** – Search actors by attributes and match them to roles.
- 🏆 **AI Role Suggestions** – Get AI-recommended actors based on role requirements.
- 💾 **MongoDB Integration** – Store and manage scripts, actors, and roles.
- 📂 **AWS S3 Image Storage** – Securely store and retrieve actor images.

---

## 🚀 Installation Guide

### **1️⃣ Clone the Repository**
```sh
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

### **2️⃣ Set Up the Virtual Environment**
#### **For macOS/Linux:**
```sh
python -m venv .venv
source .venv/bin/activate
```
#### **For Windows:**
```sh
python -m venv .venv
.venv\Scripts\activate
```

### **3️⃣ Install Dependencies**
```sh
pip install -r requirements.txt
```

### **4️⃣ Configure Environment Variables**
1. Create a `.env` file:
   ```sh
   touch .env
   ```
2. Add the following keys (replace with your actual credentials):
   ```
   OPENAI_API_KEY=your-openai-api-key
   MONGO_URI=your-mongodb-uri
   AWS_ACCESS_KEY_ID=your-aws-access-key
   AWS_SECRET_ACCESS_KEY=your-aws-secret-key
   AWS_REGION=us-east-1
   AWS_S3_BUCKET=actor-images-ai
   ```

### **5️⃣ Run the Application**
```sh
flask run
```
The app will start at **http://127.0.0.1:5000/** 🎉

---

## 📂 Project Structure
```
📦 Talent Casting AI
 ┣ 📂 static/              # CSS, JavaScript, Images
 ┣ 📂 templates/           # HTML templates
 ┣ 📂 models/              # Database models
 ┣ 📜 app.py               # Main Flask app
 ┣ 📜 requirements.txt      # Dependencies
 ┣ 📜 README.md            # Project info
 ┣ 📜 .gitignore           # Ignored files (e.g., .venv, .env, node_modules)
 ┗ 📜 .env.example         # Example of environment variables
```

## 🛠 Tech Stack
- **Backend:** Flask (Python)
- **Database:** MongoDB (with PyMongo)
- **AI Integration:** OpenAI API (GPT-4 Turbo)
- **Cloud Storage:** AWS S3
