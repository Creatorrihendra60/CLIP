VIRAL AI — Auto Captions + AI Commentary starter

WHAT THIS PACKAGE DOES
- YouTube embed preview (preview only; no downloading from YouTube).
- Upload an MP4 you own or are authorized to edit.
- Automatic speech transcription through OpenAI audio transcription API.
- Caption sentence segmentation and SRT export. Segment timing is estimated, not word-level timing; review and adjust before publishing.
- AI commentary generation through OpenAI chat API.
- Browser text-to-speech playback.
- Online FFmpeg clip rendering with 9:16 / 16:9 / 1:1 and 720p / 1080p / 1440p / 2160p output options.
- Basic FFmpeg visual filters (denoise/sharpen/brightness/contrast), not neural AI super-resolution.
- No VIRAL AI watermark is added. This does not remove watermarks already in source footage.

IMPORTANT
This is an MVP starter, not a finished commercial-scale service. Render CPU plans may be slow or have memory/time limits, especially for 4K. The source video limits the real detail; selecting 4K does not create genuine 4K detail from a low-resolution source. Caption timestamps are estimated and should be checked. The current renderer exports the selected clip but does not burn subtitles into the video yet.

DEPLOY FRONTEND
1. Copy frontend/index.html, frontend/config.js and frontend/vercel.json into your GitHub repository's frontend folder.
2. config.js currently points to https://clip-dbmv.onrender.com. Change only if your backend URL differs.
3. Commit/push; Vercel should redeploy.

DEPLOY BACKEND ON RENDER
1. Upload the contents of the backend folder to the backend folder in your GitHub repository.
2. In Render, create/update a Web Service using Docker runtime and set Root Directory to the backend folder's actual path in your repository.
3. Deploy.
4. In Render Environment, add OPENAI_API_KEY with an API key from your own OpenAI developer account. Never put the key in frontend/config.js or share it in chat.
5. Set CORS_ORIGINS to your deployed frontend origin if desired; "*" is the easy initial setting.
6. Confirm https://YOUR-BACKEND/health returns {"status":"ok","service":"VIRAL AI"}.
7. Make sure frontend/config.js points to that backend URL.

SECURITY / COST
- API usage can cost money. Check provider pricing and usage limits before enabling.
- Keep the API key private and on the backend only.
- Only upload content you own or have permission to process.
- Do not use the app to bypass YouTube access restrictions or download videos from YouTube.
