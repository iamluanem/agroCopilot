# Automated demo recording

Produces `out/agrocopilot-demo.webm` (and an `.mp4` if `ffmpeg` is installed) by walking through the 10-step script with
a visible cursor and captions. The script resets the demo before and after, forces the copilot into demo mode and cuts
out the loading waits.

```bash
docker compose up -d                 # from the project root
cd tools/record-demo
npm install
npx playwright install chromium      # first time only
npm run record
# optional: a real crop photo for the inspection and a calmer pace
PHOTO=~/Downloads/crop.jpg PACE=0.8 npm run record
```

PowerShell: `$env:PHOTO="C:\path\crop.jpg"; npm run record`.
If something fails, a screenshot of that moment is saved to `out/error.png`.
