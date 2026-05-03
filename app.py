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

    user_data = {
        "id": response.user.id,
        "email": response.user.email
    }
    profile = supabase.table("profiles").select("displayName").eq("id", response.user.id).execute()

    if not profile.data or not profile.data[0].get("displayName"):
        user_data["displayName"] = email.split('@')[0]

    # AUTO-CREATE PROFILE IF NOT EXISTS
    supabase.table("profiles").upsert(user_data).execute()

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
    category_filter = request.args.get("category", "").strip()

    try:
        query = (
            supabase.table("listings")
            .select("*")
            .order("created_at", desc=True)
        )
        
        if search:
            query = query.or_(f"title.ilike.%{search}%,description.ilike.%{search}%")

        # Category button filtering
        if category_filter:
            query = query.eq("category", category_filter)

        response = query.execute()
        listings = response.data if response.data else []
        
        for listing in listings:
            listing["display_photos"] = get_first_photo(listing.get("photos"))

    except Exception as e:
        print("Homepage Error:", e)
        listings = []

    return render_template(
        "homepage.html",
        email=session.get("email"),
        listings=listings,
        search=search,
        user_data=user_data
    )

@app.route("/edit-listing/<listing_id>")
def edit_listing(listing_id):
    if not session.get("logged_in"):
        return redirect("/login-page")

    user_id = session.get("userID")

    response = supabase.table("profiles").select("*").eq("id", user_id).execute()
    user_data = response.data[0] if response.data else {}

    res = supabase.table("listings") \
        .select("*") \
        .eq("id", listing_id) \
        .single() \
        .execute()

    listing = res.data

    # SECURITY: make sure user owns it
    if listing["lister_id"] != user_id:
        return "Unauthorized", 403

    return render_template("edit_listing.html", listing=listing, user_data=user_data)

@app.route("/update-listing/<listing_id>", methods=["POST"])
def update_listing(listing_id):
    if not session.get("logged_in"):
        return redirect("/login-page")

    user_id = session.get("userID")
    response = supabase.table("profiles").select("*").eq("id", user_id).execute()
    user_data = response.data[0] if response.data else {}

    # SECURITY CHECK
    listing = supabase.table("listings") \
        .select("lister_id", "photos") \
        .eq("id", listing_id) \
        .single() \
        .execute()

    if listing.data["lister_id"] != user_id:
        return "Unauthorized", 403
    
    photosURLS = listing.data.get("photos", [])

    # 3. Check if new photos were uploaded
    uploaded_files = request.files.getlist("photos")

    if uploaded_files and uploaded_files[0].filename != '':
        new_photo_urls = []
        
        for file in uploaded_files:
            file_extension = file.filename.rsplit('.', 1)[1]
            unique_name = f"{uuid.uuid4()}.{file_extension}"
            path_supabase = f"{user_id}/{unique_name}"
            
            file_data = file.read()
            supabase.storage.from_("listingPhotos").upload(
                path=path_supabase,
                file=file_data,
                file_options={'content-type': file.content_type}
            )
            
            # Get public URL and add to our new list
            url_res = supabase.storage.from_("listingPhotos").get_public_url(path_supabase)
            new_photo_urls.append(url_res)
        
        # REPLACE the old photos with the new ones
        photosURLS = new_photo_urls

    update_data = {
        "title": request.form.get("title"),
        "price": request.form.get("price"),
        "status": request.form.get("status"),
        'description': request.form.get("description"),
        'category': request.form.get("category"),
        'condition': request.form.get("condition"),
        'photos': photosURLS
    }

    supabase.table("listings") \
        .update(update_data) \
        .eq("id", listing_id) \
        .execute()

    return redirect("/profile")

# ------------ CREATE LISTING --------------
@app.route("/createListing", methods=['GET','POST'])
def createListing():
    if not session.get("logged_in"):
        return redirect("/login-page")
    
    user_id = session.get("userID")
    response = supabase.table("profiles").select("*").eq("id", user_id).execute()
    user_data = response.data[0] if response.data else {}

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
            "condition" : request.form.get("condition"),
            "description": request.form.get("description"),
            'category': request.form.get("category")
        }
        
        supabase.table("listings").insert(newListing).execute()
        
        return redirect("/homepage")

    return render_template("createListing.html", user_data=user_data)

@app.route("/delete-listing/<listing_id>", methods=["POST"])
def delete_listing(listing_id):
    if not session.get("logged_in"):
        return redirect("/login-page")

    user_id = session.get("userID")

    # confirm ownership using lister_id
    listing = supabase.table("listings") \
        .select("*") \
        .eq("id", listing_id) \
        .eq("lister_id", user_id) \
        .execute()

    if not listing.data:
        return "Not allowed", 403

    # delete listing
    supabase.table("listings") \
        .delete() \
        .eq("id", listing_id) \
        .execute()

    # optional cleanup: remove saved entries
    supabase.table("savedListings") \
        .delete() \
        .eq("listingID", listing_id) \
        .execute()

    return redirect("/profile")

# ------------ PROFILE --------------
@app.route("/profile")
def profile():
    if not session.get("logged_in"):
        return redirect("/login-page")

    user_id = session.get("userID")

    # ================= PROFILE DATA =================
    response = supabase.table("profiles") \
        .select("*") \
        .eq("id", user_id) \
        .execute()

    user_data = response.data[0] if response.data else {}

    # ================= USER LISTINGS =================
    listings_res = supabase.table("listings") \
        .select("*") \
        .eq("lister_id", user_id) \
        .order("created_at", desc=True) \
        .execute()

    listings = listings_res.data if listings_res.data else []

   # ================= SAVED LISTINGS =================
    saved_res = supabase.table("savedListings") \
    .select("listingID") \
    .eq("userID", user_id) \
    .execute()

    saved_ids = [item["listingID"] for item in saved_res.data] if saved_res.data else []

    saved_listings = []

    if saved_ids:
        saved_listings = supabase.table("listings") \
            .select("*") \
            .in_("id", saved_ids) \
            .execute() \
            .data or []
        # ================= RENDER PAGE =================
    return render_template(
        "profile.html",
        user_data=user_data,
        listings=listings,
        saved_listings=saved_listings
    )

@app.route("/toggle-save/<listing_id>", methods=["POST"])
def toggle_save(listing_id):
    if not session.get("logged_in"):
        return redirect("/login-page")

    user_id = session.get("userID")

    # check if already saved
    existing = supabase.table("savedListings") \
        .select("*") \
        .eq("userID", user_id) \
        .eq("listingID", listing_id) \
        .execute()

    if existing.data:
        # UNSAVE
        supabase.table("savedListings") \
            .delete() \
            .eq("userID", user_id) \
            .eq("listingID", listing_id) \
            .execute()
    else:
        # SAVE
        supabase.table("savedListings") \
            .insert({
                "userID": user_id,
                "listingID": listing_id
            }) \
            .execute()

    return redirect(request.referrer or "/profile")

@app.route("/update-profile", methods=["POST"])
def update_profile():
    if not session.get("logged_in"):
        return redirect("/login-page")

    user_id = session.get("userID")

    displayName = request.form.get("displayName")
    major = request.form.get("major")
    yearStanding = request.form.get("yearStanding")
    bio = request.form.get("bio")

    # -------------------------
    # AVATAR UPLOAD (NEW)
    # -------------------------
    avatar_file = request.files.get("avatar")
    avatar_url = None

    if avatar_file and avatar_file.filename != "":
        file_ext = avatar_file.filename.rsplit(".", 1)[-1]
        unique_name = f"{uuid.uuid4()}.{file_ext}"
        path = f"{user_id}/{unique_name}"

        file_data = avatar_file.read()

        # upload to Supabase Storage
        supabase.storage.from_("avatars").upload(
            path=path,
            file=file_data,
            file_options={"content-type": avatar_file.content_type}
        )

        avatar_url = supabase.storage.from_("avatars").get_public_url(path)

    # -------------------------
    # BUILD UPDATE DATA
    # -------------------------
    update_data = {
        "displayName": displayName,
        "major": major,
        "yearStanding": yearStanding,
        "bio": bio
    }

    if avatar_url:
        update_data["avatarURL"] = avatar_url

    supabase.table("profiles") \
        .update(update_data) \
        .eq("id", user_id) \
        .execute()

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
    if not session.get("logged_in"):
        return redirect("/login-page")

    user_id = session.get("userID")
    response = supabase.table("profiles").select("*").eq("id", user_id).execute()
    user_data = response.data[0] if response.data else {}

    listing = supabase.table("listings") \
        .select("*") \
        .eq("id", listing_id) \
        .single() \
        .execute()
    
    profilesListing = supabase.table("profiles") \
                .select("id", "displayName", "avatarURL") \
                .eq("id", listing.data['lister_id']) \
                .execute()
    
    listing_map = {p["id"]: p['displayName'] for p in profilesListing.data}

    listing.data["lister_name"] = listing_map.get(listing.data['lister_id'], "Unknown User")
    listing.data["display_photos"] = get_first_photo(listing.data.get("photos"))
    
    print(listing.data)
    
    comments =  supabase.table("comments") \
                .select("*") \
                .eq("listing_id", listing_id) \
                .order("created_at", desc=True) \
                .execute()
    
    profiles = supabase.table("profiles") \
                .select("id", "displayName", "avatarURL") \
                .in_("id", [comment["user_id"] for comment in comments.data]) \
                .execute()
    
    # 1. Create a dictionary for quick lookup: { "user_id": "displayName" }
    comment_map = {p["id"]: p["displayName"] for p in profiles.data}

    # 2. Attach the name to each comment
    for comment in comments.data:
        comment["name"] = comment_map.get(comment["user_id"], "Unknown User")

    # 3. Send to template
    return render_template("listing.html", listing=listing.data, comments=comments.data, user_data=user_data)

@app.route("/addComment/<listing_id>", methods=["POST"])
def addComment(listing_id):
    if not session.get("logged_in"):
        return redirect("/login-page")

    user_id = session.get("userID")
    comment_content = request.form.get("comment")

    supabase.table("comments") \
        .insert({
            "user_id": str(user_id),
            "listing_id": listing_id,
            "content": comment_content
        }) \
        .execute()

    return redirect(request.referrer or f"/listing/{listing_id}")

# ---------------- MESSAGE PAGE ----------------
@app.route('/message/<listing_id>/<seller_id>')
def message_seller(listing_id, seller_id):
    if not session.get("logged_in"):
        return redirect("/login-page")

    current_user_id = session.get("userID")

    seller_response = supabase.table('profiles') \
        .select('displayName, avatarURL') \
        .eq('id', seller_id) \
        .single() \
        .execute()

    seller = seller_response.data

    seller_username = "User"
    seller_avatar = None

    if seller:
        seller_username = seller.get("displayName") or "User"
        seller_avatar = seller.get("avatarURL")

    messages_response = supabase.table('messages') \
        .select('*') \
        .eq('listing_id', listing_id) \
        .or_(
            f'and(sender_id.eq.{current_user_id},receiver_id.eq.{seller_id}),'
            f'and(sender_id.eq.{seller_id},receiver_id.eq.{current_user_id})'
        ) \
        .order('created_at', desc=False) \
        .execute()

    messages = messages_response.data if messages_response.data else []

    for msg in messages:
        if msg['sender_id'] == current_user_id:
            msg['sender_username'] = "You"
            msg['bubble_class'] = "my-bubble"
        else:
            msg['sender_username'] = seller_username
            msg['bubble_class'] = "seller-bubble"

    return render_template(
        'message.html',
        listing_id=listing_id,
        seller_id=seller_id,
        seller_username=seller_username,
        seller_avatar=seller_avatar,
        messages=messages
    )

# ---------------- SEND MESSAGE ----------------
@app.route('/send_message', methods=['POST'])
def send_message():
    if not session.get("logged_in"):
        return redirect("/login-page")

    listing_id = request.form.get('listing_id')
    receiver_id = request.form.get('receiver_id')
    message = request.form.get('message')
    sender_id = session.get("userID")
    print("SenderUID:", sender_id)
    print("ReceiverUID:", receiver_id)
    print("ListingID:", listing_id)

    if message and listing_id and receiver_id:
        supabase.table('messages').insert({
            'listing_id': listing_id,
            'sender_id': sender_id,
            'receiver_id': receiver_id,
            'message': message
        }).execute()

    return redirect(url_for(
    'message_seller',
    listing_id=listing_id,
    seller_id=receiver_id))


# ---------------- INBOX ----------------
@app.route('/inbox')
def inbox():
    if not session.get("logged_in"):
        return redirect("/login-page")

    user_id = session.get("userID")

    response = supabase.table('messages') \
        .select('*') \
        .or_(f'sender_id.eq.{user_id},receiver_id.eq.{user_id}') \
        .order('created_at', desc=True) \
        .execute()

    messages = response.data if response.data else []

    conversations = {}

    for msg in messages:
        other_user = msg['receiver_id'] if msg['sender_id'] == user_id else msg['sender_id']
        key = f"{msg['listing_id']}-{other_user}"

        if key not in conversations:
            profile_response = supabase.table('profiles') \
                .select('displayName, avatarURL') \
                .eq('id', other_user) \
                .single() \
                .execute()

            profile = profile_response.data

            msg['username'] = profile['displayName'] if profile and profile.get('displayName') else "User"
            msg['avatar'] = profile['avatarURL'] if profile and profile.get('avatarURL') else None
            msg['other_user_id'] = other_user

            conversations[key] = msg

    return render_template(
        'inbox.html',
        messages=list(conversations.values())
    )

# ----------- ERROR --------------
@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template(
        "createListing.html",
        error="File is too large! Please upload images under 5MB."
    ), 413


if __name__ == "__main__":
    app.run(debug=True)