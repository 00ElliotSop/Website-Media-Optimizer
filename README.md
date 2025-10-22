# Website Media Optimizer (Debian-Ready)

A safe, interactive Python 3 tool to **analyze, report, and optimize** media across HTML and Node.js websites — while keeping visual quality as close to the original as possible. It follows a strict, production-friendly flow and your provided thresholds.

## Features

- Recursively scans your project (excludes `backup_originals/`, `.git/`, `node_modules/`, etc.)
- Detects:
  - **Images:** `.jpg`, `.jpeg`, `.png`, `.webp`, `.avif`
  - **GIFs:** `.gif`
  - **Videos:** `.mp4`, `.mov`, `.webm`
  - **Docs (report only):** `.pdf`, `.zip`, `.doc`, `.docx`
  - **Bundles (report only):** `.js`, `.css`
- Compares against **Heavy** / **Ideal** thresholds (see table)
- Interactively asks before making any changes
- **Images:** compressed *without format change*
- **GIFs:** optional conversion to **MP4** or **WebM**
- **Videos:** re-encoded (H.264/AAC) with conservative CRF
- Optional **reference replacement** in `.html`, `.js`, `.css` for converted GIFs
- **Backups** of originals kept in `backup_originals/`
- End-of-run **summary table**: per-file before/after and total savings

## Thresholds

| File Type          | "Heavy" Threshold | Ideal Target | Action |
|--------------------|-------------------|--------------|--------|
| Images (JPG, PNG)  | ≥ **800 KB**      | ≤ **250 KB** | Compress (no format change) |
| WebP / AVIF        | ≥ **400 KB**      | ≤ **250 KB** | Compress (no format change) |
| GIFs               | ≥ **2 MB**        | —            | **Convert** to MP4 / WebM |
| MP4 / MOV / WebM   | ≥ **8 MB**        | **2–5 MB**   | Compress (CRF-based) |
| PDFs / ZIPs / DOCs | ≥ **5 MB**        | gzip/zstd    | Report (future option) |
| JS / CSS bundles   | ≥ **500 KB**      | split/minify | Report (future option) |

> **Policy:** Files already within the *ideal* target are **skipped**. Images below the *heavy* threshold are **skipped** (no conversion). GIFs are only converted if you choose to convert and they are heavy.

## Requirements

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg                   # video/GIF handling
pip install --upgrade pillow tqdm rich
```
## Usage

```bash
chmod +x site_media_optimizer.py
./site_media_optimizer.py
# or: python3 site_media_optimizer.py
```


