# RedHawkExchange 🚀  
Montclair State University Marketplace  
Flask + Supabase Authentication System  

---

## 📦 Project Setup Guide (Team Instructions)

Follow these steps carefully to run the project locally.

---

## 1️⃣ Install Requirements

Make sure you have:

- Python 3.10+ installed  
- Git installed  

Check by running:

```bash
python --version
git --version
```

---

## 2️⃣ Clone The Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

---

## 3️⃣ Create Virtual Environment (Recommended)

```bash
python -m venv venv
```

Activate it:

### Windows
```bash
venv\Scripts\activate
```

### Mac/Linux
```bash
source venv/bin/activate
```

---

## 4️⃣ Install Dependencies

If `requirements.txt` exists:

```bash
pip install -r requirements.txt
```

If not:

```bash
pip install flask supabase python-dotenv
```

---

## 5️⃣ Create `.env` File

In the root project folder (same level as `app.py`), create a file named:

```
.env
```

Add the following:

```
SUPABASE_URL=YOUR_SUPABASE_PROJECT_URL
SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY
```

⚠️ These values will be shared privately by the project owner.

DO NOT commit this file.

---

## 6️⃣ Run The App

```bash
python app.py
```

You should see:

```
Running on http://127.0.0.1:5000
```

Open your browser and go to:

```
http://localhost:5000
```

---

## 🔐 Authentication Rules

- Only `@montclair.edu` emails are allowed
- Email confirmation must be completed before login
- Users register with email + password
- After confirmation, users can log in normally

---

## 📁 Project Structure

```
RedHawkExchange/
│
├── app.py
├── .env (not committed)
├── .gitignore
├── requirements.txt
├── templates/
│   ├── login.html
│   ├── register.html
│   └── dashboard.html
└── static/
```

---

## 🚫 Important Notes

- Never commit `.env`
- Never share Supabase service role keys
- Only use the public anon key
- Email confirmation must be enabled in Supabase

---

## 🛠 Common Issues

### Login not working?
- Confirm your email first
- Check `.env` configuration
- Ensure Supabase email confirmation is enabled

### Server not starting?
- Activate virtual environment
- Install dependencies

---

## 👥 Collaboration Workflow

Work on the `dev` branch.

Before pushing:

```bash
git pull origin dev
```

After making changes:

```bash
git add .
git commit -m "your message"
git push origin dev
```

---

## 🚀 Future Improvements

- Add listings system
- Create database tables
- Add protected API routes
- Deploy to production (Render / Railway)

---

If you encounter issues, share:
- Screenshot
- Error message
- Step number you’re on
