import os, tempfile, subprocess, pathlib, requests
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app=FastAPI(title="VIRAL AI Backend")
origins=os.getenv("CORS_ORIGINS","*").split(",")
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=["*"],allow_headers=["*"])
API_KEY=os.getenv("OPENAI_API_KEY","")

def require_key():
    if not API_KEY:
        raise HTTPException(503,"OPENAI_API_KEY is not configured in the Render environment variables.")

@app.get("/health")
def health(): return {"status":"ok","service":"VIRAL AI"}

@app.post("/api/transcribe")
async def transcribe(file: UploadFile=File(...)):
    require_key()
    if not file.filename.lower().endswith((".mp4",".mov",".webm",".m4v")):
        raise HTTPException(400,"Please upload a supported video file.")
    with tempfile.TemporaryDirectory() as td:
        src=pathlib.Path(td)/"input_video"
        audio=pathlib.Path(td)/"audio.mp3"
        data=await file.read()
        if len(data)>500*1024*1024: raise HTTPException(413,"Video is larger than the 500 MB limit.")
        src.write_bytes(data)
        p=subprocess.run(["ffmpeg","-y","-i",str(src),"-vn","-ac","1","-ar","16000","-b:a","64k",str(audio)],capture_output=True)
        if p.returncode!=0: raise HTTPException(400,"Could not extract audio. Check that the video contains an audio track.")
        with audio.open("rb") as af:
            r=requests.post("https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization":f"Bearer {API_KEY}"},
                data={"model":"gpt-4o-mini-transcribe"},
                files={"file":("audio.mp3",af,"audio/mpeg")},timeout=600)
        if not r.ok: raise HTTPException(r.status_code,"Transcription service error: "+r.text[:500])
        return {"text":r.json().get("text","")}

class CommentaryRequest(BaseModel):
    transcript:str
    style:str="Energetic viral shorts"

@app.post("/api/commentary")
def commentary(body:CommentaryRequest):
    require_key()
    if not body.transcript.strip(): raise HTTPException(400,"Transcript is empty.")
    prompt=("Write an original short-form video commentary based only on the supplied transcript. "
            "Style: "+body.style+". Start with a strong but truthful hook, keep it engaging, use concise spoken language, "
            "do not invent facts, and finish naturally. Do not include timestamps or claim to quote people unless transcript does. "
            "Return only the commentary script.\n\nTRANSCRIPT:\n"+body.transcript[:25000])
    r=requests.post("https://api.openai.com/v1/chat/completions",
        headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"},
        json={"model":"gpt-4o-mini","messages":[{"role":"user","content":prompt}],"temperature":0.7},timeout=120)
    if not r.ok: raise HTTPException(r.status_code,"Commentary service error: "+r.text[:500])
    return {"commentary":r.json()["choices"][0]["message"]["content"].strip()}

@app.post("/api/render")
async def render(file:UploadFile=File(...), start:float=Form(0), duration:float=Form(30),
                 resolution:int=Form(1080), aspect:str=Form("9:16"), enhance:bool=Form(True)):
    if not file.filename.lower().endswith((".mp4",".mov",".webm",".m4v")): raise HTTPException(400,"Upload a video file.")
    if duration<3 or duration>180: raise HTTPException(400,"Clip duration must be between 3 and 180 seconds.")
    if start<0: raise HTTPException(400,"Start time cannot be negative.")
    if resolution not in [720,1080,1440,2160]: raise HTTPException(400,"Unsupported resolution.")
    if aspect not in ["9:16","16:9","1:1"]: raise HTTPException(400,"Unsupported aspect ratio.")
    with tempfile.TemporaryDirectory() as td:
        src=pathlib.Path(td)/"source"
        out=pathlib.Path(td)/"viral-ai-clip.mp4"
        data=await file.read()
        if len(data)>500*1024*1024: raise HTTPException(413,"Video is larger than the 500 MB limit.")
        src.write_bytes(data)
        w,h={"9:16":(int(resolution*9/16),resolution),"16:9":(resolution,int(resolution*9/16)),"1:1":(resolution,resolution)}[aspect]
        # Ensure even dimensions for H.264.
        w-=w%2; h-=h%2
        vf=f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
        if enhance: vf+=",hqdn3d=1.5:1.5:6:6,eq=contrast=1.04:brightness=0.01:saturation=1.05,unsharp=5:5:0.5:3:3:0.0"
        cmd=["ffmpeg","-y","-ss",str(start),"-i",str(src),"-t",str(duration),"-vf",vf,
             "-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p",
             "-c:a","aac","-b:a","160k","-movflags","+faststart",str(out)]
        p=subprocess.run(cmd,capture_output=True,timeout=900)
        if p.returncode!=0 or not out.exists(): raise HTTPException(500,"Video render failed. Try a shorter clip or lower resolution.")
        # FileResponse streams the temporary output; background cleanup runs after response.
        return FileResponse(str(out),media_type="video/mp4",filename="viral-ai-clip.mp4",
                            background=None)
