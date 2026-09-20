# Deploying YojanSetu Frontend to Vercel

The Next.js frontend for **YojanSetu** is located inside the `frontend/` directory of this monorepo. Follow these exact steps to deploy to Vercel without 404 or build errors:

---

## Why You Saw `404 NOT_FOUND`
By default, Vercel sets the **Root Directory** to `./` (the repository root). Because the repository root has backend code and docs instead of the Next.js app, Vercel deployed an empty directory without an `index.html`, causing:
```
This page doesn’t exist
404 NOT_FOUND
bom1::...
```

---

## How to Fix in 1 Minute (Vercel Dashboard)

### Step 1: Open Project Settings
1. Go to your project dashboard on [vercel.com](https://vercel.com).
2. Click the **Settings** tab at the top.
3. Select **General** from the left sidebar.

### Step 2: Set the Root Directory
1. Scroll down to the **Root Directory** section.
2. Click **Edit**.
3. Type:
   ```
   frontend
   ```
   *(or click the folder icon and select `frontend`)*
4. Click **Save**.

### Step 3: Verify Framework Preset
1. Right below Root Directory, ensure **Framework Preset** is set to **Next.js**.
2. Leave **Build Command** and **Output Directory** toggles turned **OFF** (Vercel defaults will automatically run `next build` and output to `.next`).

### Step 4: Add Environment Variables (Optional)
1. Go to **Settings** $\rightarrow$ **Environment Variables**.
2. If your backend is hosted (e.g. on Render, Railway, or VPS), add:
   - **Key**: `NEXT_PUBLIC_API_BASE_URL`
   - **Value**: `https://your-backend-api-url.com/api/v1`
   *(If not set, the frontend defaults to `http://localhost:8000/api/v1` and displays the offline status indicator).*

### Step 5: Redeploy
1. Go to the **Deployments** tab at the top.
2. Click the three dots (`...`) on the far right of the latest deployment.
3. Click **Redeploy**.
4. Make sure **"Use existing Build Cache" is UNCHECKED**.
5. Click **Redeploy**.

---

## Verifying the Deployment
Once the build completes (~45s), your Vercel URL will display:
- **Home Page**: `https://<your-project>.vercel.app/`
- **Citizen Portal**: `https://<your-project>.vercel.app/citizen`
- **Admin Dashboard**: `https://<your-project>.vercel.app/admin`
