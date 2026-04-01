from flask import Flask, request, render_template, redirect, session
from supabase import create_client
from dotenv import load_dotenv
import os
import uuid

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_IN_PRODUCTION"


# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect("/login-page")


# ---------------- REGISTER PAGE ----------------
@app.route("/register-page")
def register_page():
    return render_template("register.html")


# ---------------- REGISTER ----------------
@app.route("/register", methods=["POST"])
def register():
    email = request.form.get("email")
    password = request.form.get("password")

    if not email or not password:
        return "Email and password required", 400

    if not email.endswith("@montclair.edu"):
        return "Only @montclair.edu emails allowed", 403

    response = supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": {
            "email_redirect_to": "http://localhost:5000/auth/callback"
        }
    })

    if response.user is None:
        return "Registration failed"

    return "Check your email to confirm your account before logging in."


# ---------------- EMAIL CONFIRM CALLBACK ----------------
@app.route("/auth/callback")
def auth_callback():
    return redirect("/login-page")


# ---------------- LOGIN PAGE ----------------
@app.route("/login-page")
def login_page():
    return render_template("login.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")

    response = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })

    if response.user is None:
        return "Invalid login or email not confirmed."

    session["logged_in"] = True
    session["email"] = response.user.email

    return redirect("/dashboard")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect("/login-page")
    
    response = supabase.table("listings").select("*").order("created_at", desc=True).execute()
    listings = response.data

    return render_template("dashboard.html", email=session.get("email"), listings=listings)

# ------------ CREATE LISTING --------------
@app.route("/createListing", methods=['GET','POST'])
def createListing():
    if not session.get("logged_in"):
        return redirect("/login-page")
    
    if request.method == 'POST':
        
        user = supabase.auth.get_user()
        listerID = user.user.id
        
        uploadedFiles = request.files.getlist("photos")
        photoURLS = []
        
        for file in uploadedFiles:
            if file.filename != '':
                fileExtension = file.filename.rsplit('.',1)[1]
                uniqueName = f"{uuid.uuid4()}.{fileExtension}"
                pathSupabase = f"{listerID}/{uniqueName}"
                
                fileData = file.read()
                supabase.storage.from_("listingPhotos").upload(
                    path=pathSupabase,
                    file=fileData,
                    file_options={'content-type': file.content_type})
                
                urlRes = supabase.storage.from_("listingPhotos").get_public_url(pathSupabase)
                photoURLS.append(urlRes)

        newListing = {
            "lister_id": listerID,
            "title": request.form.get("title"),
            "price": request.form.get("price"),
            "status": "Available",
            "photos": photoURLS,
            # EDIT HERE TO ADD MORE ATTRIBUTES TO POST LISTING
        }
        
        response = supabase.table("listings").insert(newListing).execute()
        
        return redirect("/dashboard")
    else:
        return render_template("createListing.html")

# ------------ PROFILE --------------
@app.route("/profile")
def profile():
    if not session.get("logged_in"):
        return redirect("/login-page")
    
    return render_template("profile.html")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login-page")


if __name__ == "__main__":
    app.run(debug=True)
