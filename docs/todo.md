# Pre-Deployment Manual Setup Tasks

This document lists all tasks that must be completed manually before or during deployment. These cannot be automated in the codebase.

---

## 1. DNS Configuration (GoDaddy or Your Registrar)

### Required DNS A Records

Configure these A records pointing to your server IP address:

| Type | Name | Value | Purpose |
|------|------|-------|---------|
| A | @ | `<YOUR_SERVER_IP>` | Apex domain (yourapp.com) - redirects to app |
| A | app | `<YOUR_SERVER_IP>` | Frontend (app.yourapp.com) |
| A | api | `<YOUR_SERVER_IP>` | Backend API (api.yourapp.com) |
| A | flower | `<YOUR_SERVER_IP>` | Flower monitoring (optional) |

### GoDaddy Specific Steps

1. Log in to [GoDaddy](https://godaddy.com/)
2. Go to **My Products** > **Domains** > Select your domain
3. Click **DNS** or **Manage DNS**
4. Under **Records**, add A records as shown above
5. Set TTL to 600 (10 minutes) initially for faster propagation testing
6. After confirming everything works, increase TTL to 3600 (1 hour)

### Verification

After DNS propagation (5-30 minutes), verify with:

```bash
# Replace with your actual domain and server IP
dig +short yourapp.com
dig +short app.yourapp.com
dig +short api.yourapp.com

# Should all return your server IP
```

---

## 2. Google OAuth Configuration

### Create OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select or create a project
3. Navigate to **APIs & Services** > **Credentials**
4. Click **Create Credentials** > **OAuth client ID**
5. Select **Web application**
6. Configure:
   - **Name**: Job Agent (or your app name)
   - **Authorized JavaScript origins**:
     - `http://localhost:3000` (development)
     - `https://app.yourapp.com` (production)
   - **Authorized redirect URIs**:
     - `http://localhost:3000/api/auth/callback/google` (development)
     - `https://app.yourapp.com/api/auth/callback/google` (production)
7. Click **Create**
8. Copy the **Client ID** and **Client Secret**

### Update Environment Variables

Add to your `.env` file:

```env
BETTER_AUTH_GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
BETTER_AUTH_GOOGLE_CLIENT_SECRET=your-client-secret-here
```

### OAuth Consent Screen (If Not Configured)

1. Go to **APIs & Services** > **OAuth consent screen**
2. Select **External** user type
3. Fill in:
   - App name
   - User support email
   - Developer contact email
4. Add scopes: `email`, `profile`, `openid`
5. Add test users if in testing mode

---

## 3. Generate Secrets

### BETTER_AUTH_SECRET

Generate a secure random secret for authentication:

```bash
openssl rand -base64 32
```

Copy the output to your `.env`:

```env
BETTER_AUTH_SECRET=your-generated-secret-here
```

**Important**: Never reuse secrets between environments. Generate unique secrets for development and production.

### Database Passwords

Generate strong passwords for database users:

```bash
# Generate POSTGRES_PASSWORD (admin user)
openssl rand -base64 24

# Generate POSTGRES_UI_PASSWORD (frontend user)
openssl rand -base64 24

# Generate POSTGRES_INIT_PASSWORD (bootstrap user)
openssl rand -base64 24
```

Add to `.env`:

```env
POSTGRES_PASSWORD=your-admin-password
POSTGRES_UI_PASSWORD=your-ui-password
POSTGRES_INIT_PASSWORD=your-init-password
```

---

## 4. UploadThing Setup

1. Go to [UploadThing Dashboard](https://uploadthing.com/dashboard)
2. Create an account or log in
3. Create a new app or select existing
4. Go to **API Keys** tab
5. Copy the token

Add to `.env`:

```env
UPLOADTHING_TOKEN=your-uploadthing-token
```

**Note**: UploadThing uses token-based authentication. No domain allowlisting is required.

---

## 5. Server Firewall Configuration (UFW)

On your production server, configure UFW to only allow necessary ports:

```bash
# Reset UFW to defaults (careful - this clears existing rules)
sudo ufw reset

# Allow SSH (important - do this first!)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS (for Caddy)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable UFW
sudo ufw enable

# Verify status
sudo ufw status verbose
```

Expected output:

```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
```

**Do NOT expose**:
- Port 5432 (PostgreSQL) - internal only
- Port 6379 (Redis) - internal only
- Port 5555 (Flower) - use Caddy reverse proxy with Basic Auth if needed

---

## 6. Environment Variables Checklist

Before deployment, ensure all these are set in your production `.env`:

### Required

- [ ] `POSTGRES_PASSWORD` - Strong, unique password
- [ ] `POSTGRES_UI_PASSWORD` - Strong, unique password (different from above)
- [ ] `POSTGRES_INIT_PASSWORD` - Strong, unique password
- [ ] `BETTER_AUTH_SECRET` - 32+ character random string
- [ ] `BETTER_AUTH_GOOGLE_CLIENT_ID` - From Google Cloud Console
- [ ] `BETTER_AUTH_GOOGLE_CLIENT_SECRET` - From Google Cloud Console
- [ ] `UPLOADTHING_TOKEN` - From UploadThing dashboard
- [ ] `JOB_LAND_API_KEY` - Your backend API key

### Domain Configuration

- [ ] `APEX_DOMAIN` - e.g., `yourapp.com`
- [ ] `FRONTEND_DOMAIN` - e.g., `app.yourapp.com`
- [ ] `API_DOMAIN` - e.g., `api.yourapp.com`
- [ ] `BETTER_AUTH_URL` - `https://app.yourapp.com`
- [ ] `NEXT_PUBLIC_BETTER_AUTH_URL` - `https://app.yourapp.com`
- [ ] `NEXT_PUBLIC_API_URL` - `https://api.yourapp.com`
- [ ] `CORS_ORIGINS` - `https://app.yourapp.com,https://api.yourapp.com`

### Optional

- [ ] `GEMINI_API_KEY` - For AI chat features
- [ ] `FLOWER_DOMAIN` - If exposing Flower monitoring
- [ ] `FLOWER_BASIC_AUTH_USER` - Basic auth username for Flower
- [ ] `FLOWER_BASIC_AUTH_HASH` - Basic auth password hash for Flower

---

## 7. Pre-Deployment Verification

Run the preflight check script before deploying:

```bash
./scripts/preflight-check.sh
```

All checks should pass or show only acceptable warnings.

---

## 8. Post-Deployment Verification

After deployment, verify these endpoints:

```bash
# Backend health
curl https://api.yourapp.com/health

# Frontend health
curl https://app.yourapp.com/api/health

# Apex redirect
curl -I https://yourapp.com
# Should show 301 redirect to https://app.yourapp.com
```

Test Google OAuth by:
1. Opening https://app.yourapp.com in browser
2. Clicking "Sign in with Google"
3. Completing the OAuth flow
4. Verifying you're redirected back and logged in

---

## Quick Reference

| Task | Where | What to Set |
|------|-------|-------------|
| DNS A Records | GoDaddy / Registrar | @, app, api → Server IP |
| OAuth Redirect URI | Google Cloud Console | `https://app.yourapp.com/api/auth/callback/google` |
| Generate Secret | Terminal | `openssl rand -base64 32` |
| Firewall | Server | Ports 22, 80, 443 only |
