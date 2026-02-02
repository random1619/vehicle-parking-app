# Vehicle Parking App - Deployment Guide

This guide provides step-by-step instructions for deploying the Vehicle Parking Application to production.

## Prerequisites

- Git installed on your system
- GitHub account (or GitLab/Bitbucket)
- Account on your chosen deployment platform

## Quick Start - Deploy to Render (Recommended)

Render is the easiest platform for deploying Flask applications with a free tier.

### Step 1: Prepare Your Repository

1. **Initialize Git** (if not already done):
   ```bash
   cd c:\Users\gagan\OneDrive\Desktop\vehicle_parking_app
   git init
   git add .
   git commit -m "Initial commit - ready for deployment"
   ```

2. **Create a GitHub repository**:
   - Go to https://github.com/new
   - Create a new repository (e.g., `vehicle-parking-app`)
   - Don't initialize with README (we already have code)

3. **Push to GitHub**:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/vehicle-parking-app.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Deploy on Render

1. **Sign up for Render**:
   - Go to https://render.com
   - Sign up with your GitHub account

2. **Create a New Web Service**:
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select `vehicle-parking-app` repository

3. **Configure the Service**:
   - **Name**: `vehicle-parking-app` (or your choice)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: Select "Free"

4. **Add Environment Variables**:
   Click "Advanced" and add these environment variables:
   
   | Key | Value |
   |-----|-------|
   | `SECRET_KEY` | (Click "Generate" to create a random key) |
   | `FLASK_ENV` | `production` |
   | `ADMIN_EMAIL` | `admin@parking.com` |
   | `ADMIN_PASSWORD` | (Choose a secure password!) |

5. **Add PostgreSQL Database** (Recommended):
   - In Render dashboard, click "New +" → "PostgreSQL"
   - **Name**: `parking-db`
   - **Plan**: Select "Free"
   - Click "Create Database"
   - Copy the "Internal Database URL"
   - Go back to your web service → Environment
   - Add environment variable:
     - **Key**: `DATABASE_URL`
     - **Value**: (Paste the Internal Database URL)

6. **Deploy**:
   - Click "Create Web Service"
   - Render will automatically build and deploy your app
   - Wait 2-5 minutes for the first deployment

7. **Access Your App**:
   - Once deployed, you'll get a URL like: `https://vehicle-parking-app-xxxx.onrender.com`
   - Visit the URL and log in with your admin credentials!

### Step 3: Initialize Database (First Time Only)

After first deployment, you need to create database tables:

1. Go to your Render dashboard
2. Click on your web service
3. Go to "Shell" tab
4. Run these commands:
   ```bash
   python
   from app import app, db
   app.app_context().push()
   db.create_all()
   exit()
   ```

Your app is now live! 🎉

---

## Alternative: Deploy to Railway

Railway is another excellent platform with $5 free credit.

### Step 1: Prepare Repository
(Same as Render - push your code to GitHub)

### Step 2: Deploy on Railway

1. **Sign up**: Go to https://railway.app and sign up with GitHub

2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose `vehicle-parking-app`

3. **Add PostgreSQL**:
   - Click "New" → "Database" → "Add PostgreSQL"
   - Railway will automatically set `DATABASE_URL` environment variable

4. **Configure Environment Variables**:
   - Click on your service → "Variables"
   - Add:
     ```
     SECRET_KEY=<generate-random-string>
     FLASK_ENV=production
     ADMIN_EMAIL=admin@parking.com
     ADMIN_PASSWORD=<your-secure-password>
     ```

5. **Configure Start Command**:
   - Go to "Settings" → "Deploy"
   - **Start Command**: `gunicorn app:app`

6. **Deploy**:
   - Railway will auto-deploy
   - Get your public URL from "Settings" → "Networking" → "Generate Domain"

---

## Alternative: Deploy to PythonAnywhere

PythonAnywhere is great for Python apps with a generous free tier.

### Step 1: Sign Up
- Go to https://www.pythonanywhere.com
- Create a free account

### Step 2: Upload Code

1. **Open Bash Console**:
   - Dashboard → "Consoles" → "Bash"

2. **Clone Repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/vehicle-parking-app.git
   cd vehicle-parking-app
   ```

3. **Create Virtual Environment**:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 parking-env
   pip install -r requirements.txt
   ```

### Step 3: Configure Web App

1. **Create Web App**:
   - Dashboard → "Web" → "Add a new web app"
   - Choose "Manual configuration"
   - Select "Python 3.10"

2. **Configure WSGI File**:
   - Click on WSGI configuration file link
   - Replace contents with:
   ```python
   import sys
   import os
   
   path = '/home/YOUR_USERNAME/vehicle-parking-app'
   if path not in sys.path:
       sys.path.append(path)
   
   os.environ['SECRET_KEY'] = 'your-secret-key-here'
   os.environ['DATABASE_URL'] = 'sqlite:////home/YOUR_USERNAME/vehicle-parking-app/parking.db'
   os.environ['FLASK_ENV'] = 'production'
   
   from app import app as application
   ```

3. **Set Virtual Environment**:
   - In Web tab, set virtualenv path:
     `/home/YOUR_USERNAME/.virtualenvs/parking-env`

4. **Reload Web App**:
   - Click green "Reload" button
   - Your app will be at: `https://YOUR_USERNAME.pythonanywhere.com`

---

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session encryption key | `a1b2c3d4e5f6...` (random string) |
| `DATABASE_URL` | Database connection string | `postgresql://user:pass@host/db` or `sqlite:///parking.db` |
| `FLASK_ENV` | Environment mode | `production` or `development` |
| `ADMIN_EMAIL` | Default admin email | `admin@parking.com` |
| `ADMIN_PASSWORD` | Default admin password | `SecurePassword123!` |

## Post-Deployment Checklist

After deploying, verify these items:

- [ ] Application is accessible via public URL
- [ ] Can log in with admin credentials
- [ ] Can create a parking lot
- [ ] Can create a booking
- [ ] Can view dashboard
- [ ] Can edit profile
- [ ] Data persists after app restart
- [ ] Sessions work correctly (stay logged in)
- [ ] Change default admin password!

## Troubleshooting

### Database Issues
**Problem**: Tables don't exist
**Solution**: Run database initialization:
```python
from app import app, db
app.app_context().push()
db.create_all()
```

### Import Errors
**Problem**: Module not found
**Solution**: Ensure all dependencies are in `requirements.txt` and installed

### 500 Internal Server Error
**Problem**: Application crashes
**Solution**: 
- Check platform logs for error details
- Verify all environment variables are set
- Ensure SECRET_KEY is set in production

### Database Connection Error (PostgreSQL)
**Problem**: Can't connect to database
**Solution**: 
- Verify DATABASE_URL is correct
- Check if `psycopg2-binary` is installed
- Ensure database is created and accessible

## Updating Your Deployment

When you make changes to your code:

1. **Commit changes**:
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```

2. **Auto-deploy**:
   - Render and Railway will automatically redeploy
   - PythonAnywhere: Click "Reload" button in Web tab

## Security Best Practices

1. **Change default admin password** immediately after first login
2. **Use strong SECRET_KEY** (at least 32 random characters)
3. **Never commit `.env` file** to Git (already in `.gitignore`)
4. **Use PostgreSQL** for production (not SQLite)
5. **Enable HTTPS** (automatic on Render/Railway)
6. **Regular backups** of your database

## Need Help?

- **Render Docs**: https://render.com/docs
- **Railway Docs**: https://docs.railway.app
- **PythonAnywhere Help**: https://help.pythonanywhere.com
- **Flask Deployment**: https://flask.palletsprojects.com/en/2.3.x/deploying/

---

**Congratulations!** Your Vehicle Parking App is now live! 🚗🎉
