from flask import Flask, request, render_template, redirect, session, url_for
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_IN_PRODUCTION"

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
        return render_template(
            "register.html",
            error="Email and password required"
        )

    if not email.endswith("@montclair.edu"):
        return render_template(
            "register.html",
            error="Only @montclair.edu emails allowed"
        )

    response = supabase.auth.sign_up({
        "email": email,
        "password": password,

    })

    if response.user is None:
        return render_template(
            "register.html",
            error="Registration failed"
        )

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
        return render_template(
            "login.html",
            error="Invalid login or email not confirmed."
        )

    session["logged_in"] = True
    session["email"] = response.user.email
    session["user_id"] = response.user.id

    return redirect("/homepage")

# ---------------- HOME ----------------
@app.route("/homepage")
def homepage():
    if not session.get("logged_in"):
        return redirect("/login-page")
    
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
            query = query.contains("category", [category_filter])

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
        selected_category=category_filter
    )
# ------------ CREATE LISTING --------------
@app.route("/createListing", methods=["GET", "POST"])
def createListing():
    if not session.get("logged_in"):
        return redirect("/login-page")
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        price = request.form.get("price", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "").strip()
        category_value = request.form.get("category", "").strip()
        tags_raw = request.form.get("tags", "").strip()
        photos_raw = request.form.get("photos", "").strip()
        
        tags = parse_csv_field(tags_raw)
        photos = parse_csv_field(photos_raw)
        category = [category_value] if category_value else []

        if title and price:
            try:
                supabase.table("listings").insert({
                    "title": title,
                    "price": price,
                    "description": description,
                    "status": status,
                    "category": category,
                    "tags": tags,
                    "photos": photos
                }).execute()
                return redirect(url_for("homepage"))
            
            except Exception as e:
                print("Create Listing Error:", e)
            
        return render_template(
            "createListing.html", 
            error="Could not create listing. Please try again."
        )
    
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

# ---------------- MESSAGE PAGE ----------------
@app.route('/message/<listing_id>/<seller_id>')
def message_seller(listing_id, seller_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    current_user_id = session['user_id']

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
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    listing_id = request.form.get('listing_id')
    receiver_id = request.form.get('receiver_id')
    message = request.form.get('message')
    sender_id = session['user_id']

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
    seller_id=receiver_id
))


# ---------------- INBOX ----------------
@app.route('/inbox')
def inbox():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    user_id = session['user_id']

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
    

if __name__ == "__main__":
    app.run(debug=True)