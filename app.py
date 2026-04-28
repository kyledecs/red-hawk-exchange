from flask import Flask, request, render_template, redirect, session, url_for
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
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

def parse_csv_field(value):
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]

def get_first_photo(photos):
    if photos:
        if isinstance(photos, list) and len(photos) > 0:
            return photos[0]
    return None

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
        return render_template("register.html", error="Email and password required")

    if not email.endswith("@montclair.edu"):
        return render_template("register.html", error="Only @montclair.edu emails allowed")

    response = supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": {
            "email_redirect_to": "http://localhost:5000/auth/callback"
        }
    })

    if response.user is None:
        return render_template("register.html", error="Registration failed")

    return render_template(
        "register.html",
        success="Check your email to confirm your account before logging in."
    )

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
        return render_template("login.html", error="Invalid login or email not confirmed.")

    session["logged_in"] = True
    session["email"] = response.user.email
    session["userID"] = response.user.id

    # ✅ AUTO-CREATE PROFILE IF NOT EXISTS
    supabase.table("profiles").upsert({
        "id": response.user.id,
        "email": response.user.email
    }).execute()

    return redirect("/homepage")

# ---------------- HOMEPAGE ----------------
@app.route("/homepage")
def homepage():
    if not session.get("logged_in"):
        return redirect("/login-page")
    
    user_id = session.get("userID")

    response = supabase.table("profiles").select("*").eq("id", user_id).execute()
    user_data = response.data[0] if response.data else {}

    search = request.args.get("query", "").strip()

    try:
        query = (
            supabase.table("listings")
            .select("*")
            .order("created_at", desc=True)
        )
        
        if search:
            query = query.or_(f"title.ilike.%{search}%,description.ilike.%{search}%")

        response = query.execute()
        listings = response.data if response.data else []
        
        for listing in listings:
            listing["display_photos"] = get_first_photo(listing.get("photos"))

    except Exception as e:
        print("Homepage Error:", e)
        listings = []

    return render_template("homepage.html", listings=listings, search=search, user_data=user_data)

# ------------ CREATE LISTING --------------
@app.route("/createListing", methods=['GET','POST'])
def createListing():
    if not session.get("logged_in"):
        return redirect("/login-page")
    
    if request.method == 'POST':
        listerID = session.get('userID')
        
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
                    file_options={'content-type': file.content_type}
                )
                
                urlRes = supabase.storage.from_("listingPhotos").get_public_url(pathSupabase)
                photoURLS.append(urlRes)

        newListing = {
            "lister_id": listerID,
            "title": request.form.get("title"),
            "price": request.form.get("price"),
            "status": "Available",
            "photos": photoURLS,
        }
        
        supabase.table("listings").insert(newListing).execute()
        
        return redirect("/homepage")

    return render_template("createListing.html")

# ------------ PROFILE --------------
@app.route("/profile")
def profile():
    if not session.get("logged_in"):
        return redirect("/login-page")

    user_id = session.get("userID")

    # PROFILE DATA
    response = supabase.table("profiles") \
        .select("*") \
        .eq("id", user_id) \
        .execute()

    user_data = response.data[0] if response.data else {}

    # USER LISTINGS (NEW PART)
    listings_res = supabase.table("listings") \
        .select("*") \
        .eq("lister_id", user_id) \
        .order("created_at", desc=True) \
        .execute()

    listings = listings_res.data if listings_res.data else []

    return render_template(
        "profile.html",
        user_data=user_data,
        listings=listings
    )

@app.route("/update-profile", methods=["POST"])
def update_profile():
    if not session.get("logged_in"):
        return redirect("/login-page")

    user_id = session.get("userID")

    displayName = request.form.get("displayName")
    major = request.form.get("major")
    yearStanding = request.form.get("yearStanding")
    bio = request.form.get("bio")
    avatarURL = request.form.get("avatarURL")

    supabase.table("profiles").update({
        "displayName": displayName,
        "major": major,
        "yearStanding": yearStanding,
        "bio": bio,
        "avatarURL": avatarURL
    }).eq("id", user_id).execute()

    return redirect("/profile")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    try:
        supabase.auth.sign_out()
    except Exception as e:
        print("Supabase sign_out error:", e)

    session.clear()
    return redirect("/login-page")

# ------------ Details page for listing ------------- #
@app.route("/listing/<listing_id>")
def listing_detail(listing_id):
    listing = supabase.table("listings") \
        .select("*") \
        .eq("id", listing_id) \
        .single() \
        .execute()

    return render_template("listing.html", listing=listing.data)

# ----------- ERROR --------------
@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template(
        "createListing.html",
        error="File is too large! Please upload images under 5MB."
    ), 413


if __name__ == "__main__":
    app.run(debug=True)