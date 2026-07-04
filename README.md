# MusicProfiler

CLI audio batch processing workflow engine.

CSV-driven pipeline: **unlock → decode → transcode → demucs → normalize → export**

## Install

```bash
pip install musicprofiler  # or: pip install -e .
```

Requires external tools on PATH:
- **[FFmpeg](https://ffmpeg.org/)** — transcoding, normalization, export
- **[Demucs](https://github.com/facebookresearch/demucs)** — source separation (optional)
- **[um](https://git.unlock-music.dev/um/cli)** — decrypt locked formats (optional)

Pre-built `um` binaries for Windows/Linux/macOS are included in [releases](https://github.com/...).

## Quick start

```bash
# import songs
musicprofiler import my_songs.csv

# view
musicprofiler list
musicprofiler list --status pending

# run full pipeline on a playlist
musicprofiler process --playlist monday.csv

# or single steps
musicprofiler process --step unlock
musicprofiler process --step normalize --target-format mp3

# export playlist to single file
musicprofiler export --playlist monday.csv --format mp3

# check task status
musicprofiler tasks
```

## CSV format

### songs.csv

| id | title | path | format | status | is_locked | is_demucs_done | is_normalized | duration |
|----|-------|------|--------|--------|-----------|----------------|---------------|----------|

### playlist.csv

| playlist | song_id | order |
|----------|---------|-------|

## i18n

```bash
set MUSICPROFILER_LANG=zh_CN   # Windows
export MUSICPROFILER_LANG=zh_CN  # Linux/macOS

musicprofiler --lang zh_CN list
```

## License

MIT License.

### Third-party

This project includes **[Unlock Music CLI](https://git.unlock-music.dev/um/cli)** (`exlib/um-main/`) for decrypting locked audio formats.

```
MIT License
Copyright (c) 2020-2021 Unlock Music
```

The `um` binary in releases is built from unmodified upstream source.
