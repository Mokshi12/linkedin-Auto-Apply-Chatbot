# LinkedIn Easy Apply Bot

A specialized, robust Python & Selenium automation bot to discover and apply to **"Easy Apply"** jobs on [LinkedIn](https://www.linkedin.com).

---

## 🌟 Key Features

1. **Safe Login Handling**:
   - Opens Chrome for manual login (supports Password, 2FA, SMS OTP, or Authenticator App).
   - Keeps your session alive inside a local directory (`chrome_profile`). You only log in once!
2. **Anti-Bot Detection**:
   - Disables automation banners (`--disable-blink-features=AutomationControlled`).
   - Masks `navigator.webdriver` via Chrome DevTools Protocol (CDP).
3. **Easy Apply Filter (`f_AL=true`)**:
   - Exclusively searches and applies to jobs supporting LinkedIn's 1-click Easy Apply mechanism.
4. **Smart Multi-Step Modal Handling**:
   - Automatically steps through standard screens (**Next** ➔ **Review** ➔ **Submit application**).
   - If complex recruiter questions, salary expectations, or custom assessments appear that cannot be auto-completed safely, the bot **cleanly discards the modal** and records the job as `needs_manual_review` in [`applied_jobs.csv`](file:///c:/Users/moksh/Documents/linkedin%20script/applied_jobs.csv).
5. **Title Filtering**:
   - `TITLE_INCLUDE`: Targets roles matching your domain (Python, Full Stack, Software, ML, Fresher, etc.).
   - `TITLE_EXCLUDE`: Skips senior, lead, managerial, or non-engineering positions.
6. **Duplicate Guard & Rate Limiting**:
   - Records every action with timestamps to prevent applying to the same job twice.
   - Built-in human-like delays (5–9 seconds) and a strict daily limit (default 20 applications) to keep your account safe.

---

## 🚀 Execution Guide

### 1. Requirements
Selenium is already installed on your system. If you ever need to reinstall:
```powershell
pip install -r requirements.txt
```

### 2. Configure Your Preferences
Open [`linkedin_apply.py`](file:///c:/Users/moksh/Documents/linkedin%20script/linkedin_apply.py) and modify the `CONFIG` section near the top:
- **`KEYWORDS`**: Roles you are targeting (e.g. `["python developer", "software engineer fresher"]`).
- **`LOCATION`**: Your target location (e.g. `"India"`, `"Bengaluru"`, `"Remote"`, or `""`).
- **`MAX_APPLIES_PER_RUN`**: Max applications per run (recommended: 15–25 daily).

### 3. Run the Bot
- **Option A (Double-Click)**:
  Double-click [`run.bat`](file:///c:/Users/moksh/Documents/linkedin%20script/run.bat) in the `linkedin script` folder.
- **Option B (PowerShell / Terminal)**:
  ```powershell
  cd "c:\Users\moksh\Documents\linkedin script"
  python linkedin_apply.py
  ```

### 4. First-Time Setup Flow
1. Chrome will launch and navigate to the LinkedIn login page.
2. Enter your credentials, solve any 2FA/SMS prompt, and verify you are on your LinkedIn feed.
3. Switch back to the terminal and press **`Enter`**.
4. The bot will automatically search, filter, and apply to eligible jobs!
