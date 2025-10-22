#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Website Media Optimizer (Final Version)
- Debian-ready, adaptive compression, 1–5 intensity scale
- Analyzes, reports, and optimizes media toward Ideal Targets
- Maintains perceptual quality; backups originals; prints summary table
"""

import os, sys, shutil, subprocess, io
from PIL import Image, ImageFile
from tqdm import tqdm
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

ImageFile.LOAD_TRUNCATED_IMAGES = True
console = Console()

# -----------------------
# CONFIGURATION
# -----------------------
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".webm"}
TEXT_EXTS  = {".html", ".js", ".css"}
BACKUP_DIR = "backup_originals"
EXCLUDE_DIRS = {BACKUP_DIR, ".git", "node_modules", "dist", "build", ".next"}

HEAVY = {".jpg":800_000,".jpeg":800_000,".png":800_000,".webp":400_000,".avif":400_000,
         ".gif":2_000_000,".mp4":8_000_000,".mov":8_000_000,".webm":8_000_000}
IDEAL = {"images":250_000,"videos":5_000_000}

# -----------------------
# HELPERS
# -----------------------
def sizeof_fmt(num, suffix="B"):
    for unit in ["","K","M","G"]:
        if abs(num) < 1024:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024
    return f"{num:.1f}T{suffix}"

def ensure_ffmpeg():
    try:
        subprocess.run(["ffmpeg","-version"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        return True
    except Exception:
        return False

def backup(path, base):
    rel = os.path.relpath(path, base)
    bpath = os.path.join(base,BACKUP_DIR,rel)
    os.makedirs(os.path.dirname(bpath),exist_ok=True)
    shutil.copy2(path,bpath)

def adaptive_quality(intensity:int, img_size:int, target:int)->int:
    """Map intensity 1–5 to target-based JPEG/WebP quality (75–95)."""
    base_q = {1:95,2:90,3:85,4:80,5:75}[intensity]
    # small nudge if still far from target
    if img_size > target*3 and intensity>=3: base_q -= 5
    return max(70, min(95, base_q))

def adaptive_crf(intensity:int, vid_size:int, target:int)->int:
    """Map intensity 1–5 to CRF (18–28) aiming for Ideal Target."""
    base_crf = {1:18,2:20,3:22,4:24,5:26}[intensity]
    if vid_size > target*3 and intensity>=3: base_crf += 2
    return min(30,max(16,base_crf))

# -----------------------
# FILE COLLECTION / ANALYSIS
# -----------------------
def collect(base):
    files=[]
    for r,ds,fs in os.walk(base):
        ds[:] = [d for d in ds if d not in EXCLUDE_DIRS]
        for f in fs:
            ext=os.path.splitext(f.lower())[1]
            if ext in IMAGE_EXTS|VIDEO_EXTS:
                p=os.path.join(r,f)
                try:size=os.path.getsize(p)
                except:continue
                files.append((p,ext,size))
    return files

def analyze(files):
    img,vid,gif=0,0,0
    heavy_i,heavy_v,heavy_g=[],[],[]
    for p,e,s in files:
        if e==".gif": gif+=1
        elif e in IMAGE_EXTS: img+=1
        elif e in VIDEO_EXTS: vid+=1
        if s>=HEAVY.get(e,9e9):
            if e in IMAGE_EXTS and e!=".gif": heavy_i.append(p)
            elif e==".gif": heavy_g.append(p)
            elif e in VIDEO_EXTS: heavy_v.append(p)
    return img,vid,gif,heavy_i,heavy_v,heavy_g

# -----------------------
# OPTIMIZATION CORE
# -----------------------
def optimize_image(path, base, intensity):
    orig=os.path.getsize(path)
    backup(path,base)
    ext=os.path.splitext(path)[1].lower()
    q=adaptive_quality(intensity,orig,IDEAL["images"])
    try:
        with Image.open(path) as im:
            im=im.convert("RGB")
            tmp=path+".tmp"
            im.save(tmp,quality=q,optimize=True,subsampling=0)
            new=os.path.getsize(tmp)
            if new<orig: os.replace(tmp,path)
            else: os.remove(tmp); new=orig
        return orig,new,f"q={q}"
    except Exception as e:
        return orig,orig,f"error:{e}"

def optimize_video(path, base, intensity):
    if not ensure_ffmpeg():
        return os.path.getsize(path),os.path.getsize(path),"ffmpeg missing"
    orig=os.path.getsize(path)
    backup(path,base)
    crf=adaptive_crf(intensity,orig,IDEAL["videos"])
    tmp=path+".tmp.mp4"
    cmd=["ffmpeg","-y","-i",path,"-vcodec","libx264","-crf",str(crf),
         "-preset","slow","-acodec","aac","-b:a","128k","-movflags","+faststart",tmp]
    try:
        subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        new=os.path.getsize(tmp)
        if new<orig: os.replace(tmp,path)
        else: os.remove(tmp); new=orig
        return orig,new,f"crf={crf}"
    except Exception as e:
        return orig,orig,f"error:{e}"

def convert_gif(path, base, target_ext):
    if not ensure_ffmpeg():
        return os.path.getsize(path),os.path.getsize(path),"ffmpeg missing",path
    orig=os.path.getsize(path)
    backup(path,base)
    newp=os.path.splitext(path)[0]+target_ext
    codec=["libx264"] if target_ext==".mp4" else ["libvpx-vp9","-b:v","0","-crf","32"]
    cmd=["ffmpeg","-y","-i",path,"-movflags","+faststart","-an","-vcodec"]+codec+[newp]
    try:
        subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        new=os.path.getsize(newp)
        return orig,new,f"gif→{target_ext[1:]}",newp
    except Exception as e:
        return orig,orig,f"error:{e}",path

def replace_refs(base,mapping):
    modified=[]
    by_name={os.path.basename(k):os.path.basename(v) for k,v in mapping.items()}
    for r,_,fs in os.walk(base):
        for f in fs:
            if os.path.splitext(f)[1].lower() not in TEXT_EXTS: continue
            fp=os.path.join(r,f)
            try:
                with open(fp,"r",encoding="utf-8",errors="ignore") as h: data=h.read()
                newd=data
                for old,nw in by_name.items():
                    newd=newd.replace(old,nw)
                if newd!=data:
                    with open(fp,"w",encoding="utf-8") as o:o.write(newd)
                    modified.append(fp)
            except: continue
    return modified

# -----------------------
# MAIN FLOW
# -----------------------
def main():
    base=os.getcwd()
    console.rule("[bold yellow]Website Media Optimizer[/bold yellow]")
    files=collect(base)
    img,vid,gif,hi,hv,hg=analyze(files)
    total=len(files)
    panel=Panel.fit(
        Text("\n".join([
            f"Total media files: {total}",
            f"Images: {img}  | Heavy: {len(hi)}",
            f"Videos: {vid}  | Heavy: {len(hv)}",
            f"GIFs:    {gif}  | Heavy: {len(hg)}",
            "",
            "Heavy Thresholds → Images ≥800 KB, WebP/AVIF ≥400 KB, GIF ≥2 MB, Video ≥8 MB",
            "Ideal Targets → Images ≤250 KB, Videos ≤5 MB",
        ])),
        title="Analysis Summary",border_style="cyan")
    console.print(panel)

    if input("Proceed with optimization? (y/n): ").lower()!="y":
        console.print("[yellow]Aborted by user.[/yellow]"); return

    # Compression intensity
    while True:
        try:
            lvl=int(input("Enter compression intensity (1–5): ").strip())
            if 1<=lvl<=5: break
        except: pass
        console.print("[red]Enter a number between 1 and 5.[/red]")

    # GIF conversion
    target_ext=None
    if hg:
        console.print("\nConvert GIFs to:\n 1) MP4\n 2) WebM\n 3) Skip")
        ch=input("Select [1/2/3]: ").strip()
        if ch=="1": target_ext=".mp4"
        elif ch=="2": target_ext=".webm"

    # Reference replacement
    ref_ok=input("\nSearch through .html, .js, and .css to update references to converted files? (y/n): ").lower()=="y"

    console.rule("[bold green]Optimizing…[/bold green]")
    summary=[]
    mapping={}

    # Optimize images
    for p,e,s in tqdm([x for x in files if x[1] in IMAGE_EXTS and x[1]!=".gif"],desc="Images"):
        if s<HEAVY.get(e,9e9): summary.append((p,"skip",s,s,"below heavy")); continue
        o,n,note=optimize_image(p,base,lvl)
        act="compress" if n<o else "skip"
        summary.append((p,act,o,n,note))

    # GIFs
    if target_ext:
        for p in tqdm(hg,desc="GIFs"):
            o,n,note,newp=convert_gif(p,base,target_ext)
            mapping[p]=newp
            act="convert" if n<o or newp!=p else "skip"
            summary.append((p,act,o,n,note))
    else:
        for p in hg: summary.append((p,"skip",os.path.getsize(p),os.path.getsize(p),"skipped"))

    # Videos
    for p,e,s in tqdm([x for x in files if x[1] in VIDEO_EXTS],desc="Videos"):
        if s<HEAVY.get(e,9e9): summary.append((p,"skip",s,s,"below heavy")); continue
        o,n,note=optimize_video(p,base,lvl)
        act="compress" if n<o else "skip"
        summary.append((p,act,o,n,n,note))

    mod=[]
    if ref_ok and mapping: mod=replace_refs(base,mapping)

    # Summary table
    console.rule("[bold cyan]Optimization Summary[/bold cyan]")
    tab=Table(show_header=True,header_style="bold magenta")
    tab.add_column("File");tab.add_column("Action");tab.add_column("Original",justify="right")
    tab.add_column("Optimized",justify="right");tab.add_column("Reduction",justify="right");tab.add_column("Note")
    tb,ta=0,0
    for f,a,o,n,note in summary:
        tb+=o;ta+=n
        red=0 if o==0 else 100*(o-n)/o
        tab.add_row(os.path.relpath(f,base),a,sizeof_fmt(o),sizeof_fmt(n),f"{red:.1f}%",note)
    console.print(tab)
    overall=0 if tb==0 else 100*(tb-ta)/tb
    panel=Panel.fit(Text("\n".join([
        f"Total files processed: {len(summary)}",
        f"Overall reduction: {overall:.1f} %",
        f"Backups saved in: {BACKUP_DIR}/",
        f"Text files updated: {len(mod)}"
    ])),title="Run Summary",border_style="green")
    console.print(panel)

if __name__=="__main__":
    try: main()
    except KeyboardInterrupt: console.print("\n[red]Interrupted.[/red]"); sys.exit(1)
