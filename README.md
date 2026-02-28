# 🦅 PTERODACTYL ADMIN DISCORD BOT

ENTERPRISE-GRADE PTERODACTYL PANEL MANAGEMENT DIRECTLY FROM DISCORD.  
BUILT WITH DISCORD.PY 2.X USING MODERN SLASH COMMANDS.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 VERSIONS

V1 — STABLE RELEASE ✅  
V1 — Updated to 1.0.0 to 1.0.1
V2 — MAJOR UPGRADE COMING SOON 🚀  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 WHAT IS THIS?

A COMPLETE APPLICATION API MANAGEMENT SYSTEM  
FOR PTERODACTYL PANEL.

MANAGE EVERYTHING DIRECTLY FROM DISCORD:

• NODES  
• SERVERS  
• EGGS  
• NESTS  
• MOUNTS  
• DATABASE HOSTS  
• USERS  
• ROLES  
• SUSPEND / UNSUSPEND  
• SERVER CREATION WIZARD (AUTO EGG CONFIG)  
• MANAGE SERVER REAL TIME RESOURCES SHOW 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ QUICK SETUP

### INSTALL REQUIREMENTS
```bash
pip install -r requirements.txt
```

### CONFIGURE ENVIRONMENT
```bash
cp .env.example .env
nano .env
```

### RUN THE BOT
```bash
python main.py
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔐 .ENV CONFIGURATION

```env
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN
OWNER_ID=YOUR_DISCORD_USER_ID
PTERODACTYL_URL=https://panel.example.com
PTERODACTYL_API_KEY=YOUR_APPLICATION_API_KEY
```

⚠ USE APPLICATION API KEY, NOT CLIENT API KEY.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧠 CORE FEATURES (V1)

✔ SLASH COMMANDS ONLY  
✔ OWNER-ONLY SECURITY  
✔ EPHEMERAL RESPONSES  
✔ CLEAN EMBED UI  
✔ ASYNC API CLIENT (AIOHTTP)  
✔ AUTO PAGINATION  
✔ SUSPEND / UNSUSPEND SUPPORT  
✔ SMART SERVER CREATION  
✔ CRASH-SAFE ARCHITECTURE  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🛠 COMMAND SYSTEM

### /help
SHOWS ADMIN COMMAND OVERVIEW  

### /nodes
overview  
list  
create  
edit  
delete  
allocations  
servers  
create-allocations  
delete-allocations  

### /servers
overview  
list  
create  
edit-details  
edit-build  
edit-startup  
delete  
databases  
suspend  
unsuspend  
reinstall  

### /users
overview  
list  
create  
edit  
delete  
roles  
servers  

### /roles
overview  
list  
create  
edit  
delete  

### /manage
manage

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📂 PROJECT STRUCTURE

```
ptero-bot/
├── main.py
├── api_client.py
├── config.py
├── requirements.txt
├── .env.example
└── cogs/
    ├── utils.py
    ├── help.py
    ├── nodes.py
    ├── eggs.py
    ├── nests.py
    ├── mounts.py
    ├── database_hosts.py
    ├── users.py
    ├── servers.py
    ├── roles.py
    └── server_suspend.py
    ├── manage.py
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🛡 SECURITY

• NEVER EXPOSE .ENV  
• REGENERATE API KEY IF LEAKED  
• RESTRICT PANEL IP ACCESS  
• LIMIT DISCORD BOT PERMISSIONS  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔄 VERSION HISTORY

V1  
- FULL ADMIN MANAGEMENT  
- SUSPEND / UNSUSPEND  
- AUTO EGG CONFIGURATION  
- PRODUCTION READY

V1 
- Added /manage for managing the server
- With start stop button
- And Real Time Resources Usage

V2 (COMING SOON 🚀)  
- INTERACTIVE HELP UI  
- ADVANCED LOGGING SYSTEM  
- RATE LIMIT AUTO-RETRY  
- AUDIT LOGGING  
- MULTI-OWNER SUPPORT  
- PERMISSION SYSTEM  
- PERFORMANCE OPTIMIZATION  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# OWNER
Made with ❤️ by Zerioak
