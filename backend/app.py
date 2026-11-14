import os, re, uuid, shutil, subprocess, threading, json, time
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import yt_dlp
from faster_whisper import WhisperModel
from openai import OpenAI

BASE = Path("/tmp/viral_ai")
BASE.mkdir(exist_ok=True)
JOBS: Dict[str, Dict[str, Any]] = {}
LOCK = threading.Lock()
app = FastAPI(title="VIRAL AI API")

allowed = os.getenv("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware, allow_origins=[x.strip() for x in allowed.split(",")],
    allow_credentials=False, allow_methods=["*"], allow_headers=["*"]
)

class ProcessRequest(BaseModel):
    youtube_url: HttpUrl
    clips: int = 5

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout or "Processing failed")[-2500:])
    return p.stdout

def update(job, **kwargs):
    with LOCK:
        JOBS[job].update(kwargs)

def download_video(url, folder):
    output = str(folder / "source.%(ext)s")
    opts = {
        "outtmpl": output,
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 2,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(str(url), download=True)
    candidates = list(folder.glob("source.*"))
    candidates = [p for p in candidates if p.suffix.lower() in [".mp4", ".mkv", ".webm", ".mov"]]
    if not candidates:
        raise RuntimeError("Could not find the downloaded video file.")
    return candidates[0], info.get("duration") or 0, info.get("title") or "Video"

def transcribe(video):
    model_name = os.getenv("WHISPER_MODEL", "base")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(video), vad_filter=True, word_timestamps=False)
    rows = []
    for s in segments:
        text = (s.text or "").strip()
        if text:
            rows.append({"start": float(s.start), "end": float(s.end), "text": text})
    return rows

def select_moments(transcript, duration, count):
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        client = OpenAI(api_key=api_key)
        compact = [{"start": round(x["start"],1), "end": round(x["end"],1), "text": x["text"][:350]} for x in transcript]
        prompt = (
            "Choose the strongest short-form video moments from this transcript. "
            "Return ONLY JSON: {\"clips\":[{\"start\":number,\"end\":number,\"reason\":\"short reason\"}]}. "
            f"Choose up to {count} non-overlapping moments, each 20-60 seconds, within 0 and {duration}. "
            "Favor surprising, funny, emotional, useful, high-curiosity moments with a clear hook. "
            "Do not invent transcript content. Transcript segments: " + json.dumps(compact, ensure_ascii=False)
        )
        result = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role":"user","content":prompt}],
            response_format={"type":"json_object"},
            temperature=0.2
        )
        data = json.loads(result.choices[0].message.content)
        clips = data.get("clips", [])
    else:
        # Simple fallback: rank transcript windows by energetic / curiosity language.
        cues = ["why", "secret", "crazy", "never", "amazing", "mistake", "best", "worst",
                "shocking", "actually", "because", "imagine", "problem", "happened", "truth"]
        scored = []
        for seg in transcript:
            words = seg["text"].lower()
            score = sum(words.count(w) for w in cues) + min(len(words.split()) / 25, 2)
            scored.append((score, seg["start"]))
        scored.sort(reverse=True)
        clips = []
        for score, start in scored:
            a = max(0, min(float(start) - 8, max(0, duration - 35)))
            b = min(duration, a + 35)
            if b-a < 15: continue
            if all(abs(a-c["start"]) > 25 for c in clips):
                clips.append({"start":a,"end":b,"reason":"Transcript keyword and speech-density score"})
            if len(clips) >= count: break
    clean = []
    for c in clips:
        try:
            a, b = max(0, float(c["start"])), min(float(duration), float(c["end"]))
            if 12 <= b-a <= 75 and a < b:
                clean.append({"start":a,"end":b,"reason":str(c.get("reason","Strong moment"))[:180]})
        except Exception:
            pass
    return sorted(clean[:count], key=lambda x:x["start"])

def make_clip(video, clip, folder, index, transcript):
    start, end = clip["start"], clip["end"]
    srt = folder / f"clip_{index}.srt"
    lines = []
    n = 1
    for seg in transcript:
        a, b = max(seg["start"], start), min(seg["end"], end)
        if b <= a: continue
        def ts(v):
            ms = int(round(v * 1000))
            h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); sec, ms = divmod(ms, 1000)
            return f"{h:02}:{m:02}:{sec:02},{ms:03}"
        lines += [str(n), f"{ts(a-start)} --> {ts(b-start)}", seg["text"], ""]
        n += 1
    srt.write_text("\n".join(lines), encoding="utf-8")
    out = folder / f"viral_clip_{index}.mp4"
    # Center crop to vertical 9:16; burn in readable subtitles.
    sub = str(srt).replace("\\", "/").replace(":", r"\:")
    vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,subtitles='{sub}':force_style='FontName=Arial,FontSize=17,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=120'"
    run(["ffmpeg","-y","-ss",str(start),"-i",str(video),"-t",str(end-start),
         "-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","23",
         "-c:a","aac","-b:a","128k","-movflags","+faststart",str(out)])
    return out

def process_job(job_id, url, count):
    folder = BASE / job_id
    folder.mkdir(parents=True, exist_ok=True)
    try:
        update(job_id, status="downloading", message="Getting the video…")
        video, duration, title = download_video(url, folder)
        if not duration:
            raise RuntimeError("Could not read video duration.")
        if duration > 7200:
            raise RuntimeError("For this starter version, videos must be 2 hours or shorter.")
        update(job_id, status="transcribing", message="Transcribing speech…", title=title)
        transcript = transcribe(video)
        if not transcript:
            raise RuntimeError("No speech was detected. This version needs spoken audio to find moments and create captions.")
        update(job_id, status="finding", message="Finding engaging moments…")
        clips = select_moments(transcript, duration, count)
        if not clips:
            raise RuntimeError("No suitable moments found. Try a video with clearer speech.")
        results = []
        for i, clip in enumerate(clips, 1):
            update(job_id, status="rendering", message=f"Creating clip {i} of {len(clips)}…")
            out = make_clip(video, clip, folder, i, transcript)
            results.append({"url":f"/api/jobs/{job_id}/files/{out.name}","start":clip["start"],"end":clip["end"],"reason":clip["reason"]})
        update(job_id, status="completed", message="Your clips are ready.", title=title, clips=results)
    except Exception as e:
        update(job_id, status="failed", message=str(e)[:1200])

@app.get("/api/health")
def health():
    return {"ok":True,"service":"VIRAL AI"}

@app.post("/api/process")
def process(req: ProcessRequest, background: BackgroundTasks):
    url = str(req.youtube_url)
    if not any(host in url.lower() for host in ["youtube.com/", "youtu.be/"]):
        raise HTTPException(400, "Please enter a YouTube video URL.")
    if not 1 <= req.clips <= 10:
        raise HTTPException(400, "Choose between 1 and 10 clips.")
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status":"queued","message":"Added to queue.","clips":[]}
    background.add_task(process_job, job_id, url, req.clips)
    return {"job_id":job_id}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in JOBS: raise HTTPException(404, "Job not found.")
    return JOBS[job_id]

@app.get("/api/jobs/{job_id}/files/{filename}")
def get_file(job_id: str, filename: str):
    from fastapi.responses import FileResponse
    if not re.fullmatch(r"viral_clip_\d+\.mp4", filename):
        raise HTTPException(400, "Invalid file name.")
    path = BASE / job_id / filename
    if not path.exists(): raise HTTPException(404, "Clip not found.")
    return FileResponse(path, media_type="video/mp4", filename=filename)
