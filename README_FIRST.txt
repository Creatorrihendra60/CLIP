VIRAL AI — ONLINE BACKEND STARTER
=================================

You do NOT need Python installed on your computer. Python runs only inside the hosted Render server.

WHAT THIS BUILD DOES
- Accepts a YouTube URL for a video you own or are authorized to edit.
- Downloads/processes it on the hosted server using yt-dlp (availability and platform terms may limit this).
- Transcribes speech with Whisper.
- Uses an OpenAI API key, if configured, to select engaging transcript moments. Without it, it uses a basic keyword scoring fallback.
- Renders up to 10 vertical 9:16 MP4 clips with burned-in captions.

IMPORTANT LIMITATIONS
- This is a starter deployment, not a guaranteed viral predictor.
- YouTube's official API does not provide a general video-download endpoint. The included downloader may fail for some videos and must only be used where you have permission and downloading is allowed by the platform and law. Do not use it to bypass restrictions, DRM, or access controls.
- The Render service needs enough memory/CPU and disk space. Video processing may be slow; a paid instance may be needed. Free instances may sleep or be unsuitable.
- Add your own OpenAI API key to Render to enable AI moment selection. API usage can cost money. Keep the key secret; never put it in frontend/config.js.
- This first version center-crops video to 9:16; it does not track faces or create synthetic voice commentary.
- Render's local files are temporary. Download finished clips before the service restarts.

DEPLOYMENT — NO LOCAL PYTHON
1. Create a GitHub account (if you don't already have one).
2. Create a NEW repository named viral-ai. Upload the contents of this ZIP so that backend/ and frontend/ are at the repository root. Do not upload the ZIP file itself.
3. In Render, create a new Web Service from that GitHub repository.
   - Runtime: Docker
   - Root Directory: backend
   - Health Check Path: /api/health
   - Choose a plan with enough memory for FFmpeg + Whisper. The smallest/free tier may not work reliably.
4. In Render → Environment, add:
   - OPENAI_API_KEY = your own API key (optional for AI selection; without it keyword scoring is used)
   - FRONTEND_ORIGIN = * (temporary during first test; later replace with your Vercel site URL)
5. Deploy. Wait until Render reports Live. Copy the service URL, e.g. https://viral-ai-api.onrender.com
6. In GitHub, open frontend/config.js and replace YOUR-BACKEND with your actual Render service name/URL. Commit the change.
7. In Vercel, import the same GitHub repository:
   - Framework Preset: Other
   - Root Directory: frontend
   - Deploy.
8. Open your Vercel URL. Paste a permitted YouTube video URL and test.

IF YOU SEE "ROOT DIRECTORY backend DOES NOT EXIST"
Your repository layout is wrong. The GitHub repository's top level must show two folders named backend and frontend. Inside backend must be app.py, Dockerfile, requirements.txt. Do not set Root Directory to a folder that is nested one level deeper.

IF THE APP SAYS SERVER NOT CONNECTED
Check frontend/config.js. It must contain your exact Render URL, including https://, and no trailing slash. Redeploy Vercel after committing the change.

SAFETY / ACCOUNT
If a hosting provider requires an adult account or payment method, ask a parent/guardian to manage that account. Do not falsify your age or enter payment details without permission.
