---
name: github-push
description: Automated workflow to inspect, sanitize, stage, commit, and push project changes to GitHub. Activate when the user asks to push to GitHub or uses /github-push.
---

# 🚀 GitHub Push Workflow

Use this skill whenever the user wants to push or sync their changes to GitHub.

## 📋 Standard Execution Procedure:

### Step 1: Pre-Push Security & Privacy Verification
1. Inspect `git status` and untracked/modified files.
2. Ensure sensitive assets are NOT staged:
   - Personal/local IP addresses or hardcoded device serials
   - Private user tokens, API keys, or `.env` files
   - Binary directories (`scrcpy/`, `dist/`, `build/`)
   - Internal agent documentation files (`AGENTS.md`)
   - Local caches (`data/icons/`, `data/config.json`)
3. Verify that [`.gitignore`](file:///z:/Github/Scrcpy-UI/.gitignore) properly ignores all runtime data.

### Step 2: Check Remote Configuration
Check if `origin` remote is configured:
```powershell
git remote -v
```
If no remote is configured:
- Ask the user for their GitHub repository URL.
- Link it via: `git remote add origin <url>`

### Step 3: Stage and Commit
1. Stage all safe tracked changes:
   ```powershell
   git add .
   ```
2. Generate a clean, conventional commit message reflecting the recent changes:
   ```powershell
   git commit -m "feat/fix/docs: <description of changes>"
   ```

### Step 4: Push to GitHub
Push the commits to the upstream branch:
```powershell
git push -u origin main
```

### Step 5: Report Status
Provide a concise summary with:
- Commit hash & message
- Target GitHub branch
- Direct link to the repository / commit
