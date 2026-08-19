---
name: github-release
description: Automated workflow to create a version tag, prepare release notes, and trigger a downloadable Windows release on GitHub. Activate when the user asks to publish a release or uses /github-release.
---

# 🚀 GitHub Release & Publishing Workflow

Use this skill when the user wants to publish a new downloadable version of Scrcpy Studio.

## 📋 Release Execution Steps:

### Step 1: Determine Next Version Tag
1. Inspect existing tags:
   ```powershell
   git tag -l --sort=-v:refname
   ```
2. If no tags exist, default to `v1.0.0`. Otherwise increment the patch/minor version as requested by the user.

### Step 2: Ensure Repository Is Clean
1. Run `git status` to verify there are no uncommitted changes.
2. If there are changes, commit them before tagging:
   ```powershell
   git add .
   git commit -m "chore: Prepare release vX.X.X"
   ```

### Step 3: Create Local Git Tag
Create an annotated release tag:
```powershell
git tag -a vX.X.X -m "Release Scrcpy Studio vX.X.X"
```

### Step 4: Prompt the User to Push the Tag
Since AI agents must never execute `git push` directly (per Rule #5 in `AGENTS.md`), present the exact command to the user:
```powershell
git push origin vX.X.X
```

### Step 5: Explain the Automated GitHub Actions Pipeline
Inform the user that once pushed:
1. GitHub Actions will automatically spin up Windows runners.
2. Install Python 3.13 and PySide6 dependencies.
3. Download the latest official 64-bit Scrcpy binaries.
4. Package the release into `Scrcpy-Studio-Windows-vX.X.X.zip`.
5. Automatically publish the new public GitHub Release under the repository's **Releases** tab.
