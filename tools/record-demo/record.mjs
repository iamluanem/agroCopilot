// Records the AgroCopilot demo video (the 10-step script in the README) with a visible cursor and captions.
// Requires `docker compose up` running (web on :3000, API on :8000).
// Usage: npm install && npx playwright install chromium && npm run record
// Env vars: BASE_URL, API_URL, OUT (output folder), PHOTO (optional crop photo for the inspection),
//           PACE (pause pacing; default 0.65 — use 0.8 for a calmer video).
import { chromium } from "playwright";
import { existsSync, mkdirSync, readdirSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join, resolve } from "node:path";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";
const OUT = resolve(process.env.OUT ?? "out");
const PHOTO = process.env.PHOTO && existsSync(process.env.PHOTO) ? resolve(process.env.PHOTO) : null;
const W = 1440, H = 900;
const PACE = Number(process.env.PACE ?? 0.65); // < 1 speeds up reading pauses
const wait = (ms) => new Promise((r) => setTimeout(r, ms * PACE));

const OVERLAY = `(() => {
  if (document.getElementById('__cursor')) return;
  const c = document.createElement('div'); c.id = '__cursor';
  c.style.cssText = 'position:fixed;z-index:2147483647;left:${W / 2}px;top:${H / 2}px;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:rgba(10,17,32,.85);border:3px solid #fff;box-shadow:0 4px 14px rgba(0,0,0,.3);pointer-events:none;transition:left .4s cubic-bezier(.3,.7,.2,1),top .4s cubic-bezier(.3,.7,.2,1),transform .12s';
  document.body.appendChild(c);
  const cap = document.createElement('div'); cap.id = '__caption';
  cap.style.cssText = 'position:fixed;z-index:2147483646;left:50%;bottom:30px;transform:translateX(-50%) translateY(16px);opacity:0;max-width:960px;padding:14px 24px;border-radius:16px;background:rgba(10,17,32,.93);color:#fff;font:500 19px/1.4 system-ui,-apple-system,Segoe UI,sans-serif;box-shadow:0 18px 40px -12px rgba(0,0,0,.5);transition:all .4s cubic-bezier(.2,.7,.2,1);pointer-events:none;text-align:center';
  document.body.appendChild(cap);
})();`;

async function api(path, method = "GET", body) {
  const r = await fetch(API + path, { method, headers: { "Content-Type": "application/json" }, body: body && JSON.stringify(body) });
  if (!r.ok) throw new Error(`${method} ${path} → ${r.status}`);
  return r.json();
}

async function main() {
  // ---------------------------------------------------------------- setup
  console.log("Preparing the demo (reset + copilot demo mode)…");
  await api("/api/demo/reset", "POST");
  const cfg = await api("/api/settings");
  await api("/api/settings", "PUT", { economics: cfg.economics, risk: cfg.risk, llm_provider: "demo" });
  const farm = (await api("/api/farms"))[0];
  const detail = await api(`/api/farms/${farm.id}`);
  const f04 = detail.fields.find((f) => f.code === "F04");
  await api(`/api/farms/${farm.id}/priorities`); // precompute
  await api(`/api/fields/${f04.id}`);
  const hasSentinel = (await api(`/api/farms/${farm.id}/imagery`)).length > 0;

  mkdirSync(OUT, { recursive: true });
  const tmp = join(OUT, ".raw");
  rmSync(tmp, { recursive: true, force: true });
  const browser = await chromium.launch();
  // warm-up outside the recording (compiles Next pages and loads tiles)
  const warm = await browser.newPage({ viewport: { width: W, height: H } });
  for (const p of ["/", "/map", `/fields/${f04.id}`, "/tasks", "/outcomes", "/copilot"]) {
    await warm.goto(BASE + p, { waitUntil: "load" }); await wait(p === "/map" ? 6000 : 2500);
  }
  await warm.close();

  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, recordVideo: { dir: tmp, size: { width: W, height: H } } });
  const page = await ctx.newPage();
  page.on("dialog", (d) => d.dismiss());
  globalThis.__page = page;
  // loading waits are cut from the final video
  const T0 = Date.now();
  const cuts = [];
  const cut = async (fn) => {
    const a = Date.now(); await fn(); const b = Date.now();
    if (b - a > 500) cuts.push([(a - T0) / 1000 + 0.12, (b - T0) / 1000 - 0.08]);
  };

  let cur = { x: W / 2, y: H / 2 };
  const overlay = () => page.evaluate(OVERLAY);
  const caption = async (html, hold = 0) => {
    await page.evaluate((h) => {
      const c = document.getElementById("__caption"); if (!c) return;
      c.style.opacity = 0; c.style.transform = "translateX(-50%) translateY(12px)";
      setTimeout(() => { c.innerHTML = h; if (h) { c.style.opacity = 1; c.style.transform = "translateX(-50%)"; } }, 260);
    }, html);
    await wait(700 + hold);
  };
  const cursorTo = async (x, y) => {
    await page.evaluate(([x, y]) => { const c = document.getElementById("__cursor"); if (c) { c.style.left = x + "px"; c.style.top = y + "px"; } }, [x, y]);
    await page.mouse.move(x, y, { steps: 8 });
    cur = { x, y }; await wait(600);
  };
  const press = () => page.evaluate(() => { const c = document.getElementById("__cursor"); if (c) { c.style.transform = "scale(.7)"; setTimeout(() => (c.style.transform = ""), 160); } });
  const pointAt = async (loc) => {
    await loc.scrollIntoViewIfNeeded(); await wait(250);
    const b = await loc.boundingBox();
    await cursorTo(b.x + b.width / 2, b.y + b.height / 2);
  };
  const click = async (loc, after = 900) => { await pointAt(loc); await press(); await loc.click(); await wait(after); };
  const clickAt = async (x, y, after = 900) => { await cursorTo(x, y); await press(); await page.mouse.click(x, y); await wait(after); };
  const wheel = async (x, y, dy, ms = 1400) => {
    await cursorTo(x, y);
    const n = Math.max(1, Math.round(ms / 40));
    for (let i = 0; i < n; i++) { await page.mouse.wheel(0, dy / n); await wait(40); }
    await wait(350);
  };
  const go = async (path, ready, settle = 700) => {
    await cut(async () => { await page.goto(BASE + path, { waitUntil: "load" }); await overlay(); await ready(); });
    await wait(settle);
  };
  const MAP = async () => {
    await page.locator(".maplibregl-marker").first().waitFor({ timeout: 60000 });
    await page.waitForFunction(() => !document.body.innerText.includes("Loading management cells"), null, { timeout: 60000 });
    await wait(2500); // satellite tiles
  };
  const SEL = (sel) => async () => { await page.locator(sel).first().waitFor({ timeout: 60000 }); await wait(600); };
  const TXT = (t) => async () => { await page.getByText(t).first().waitFor({ timeout: 60000 }); await wait(600); };
  const card = async (title, sub, ms = 4200) => {
    await page.setContent(`<body style="margin:0;height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 30% 20%,#172540,#0a1120 60%);color:#fff;font-family:system-ui,-apple-system,Segoe UI,sans-serif">
      <div style="text-align:center;max-width:1040px;padding:0 40px">
        <div style="display:inline-flex;align-items:center;gap:14px;font-size:22px;font-weight:600;color:#7ee2a1;letter-spacing:.3px">
          <span style="display:grid;place-items:center;width:44px;height:44px;border-radius:12px;background:#2f9e5b;color:#fff;font-size:24px">🌱</span>AgroCopilot</div>
        <div style="margin-top:26px;font-size:54px;font-weight:700;letter-spacing:-1.2px;line-height:1.12">${title}</div>
        <div style="margin-top:22px;font-size:24px;color:#a7b4cc;line-height:1.5">${sub}</div></div></body>`);
    await overlay();
    await page.evaluate(() => { document.getElementById("__cursor").style.display = "none"; });
    await wait(ms);
  };

  // ---------------------------------------------------------------- 0. opening
  await cut(() => wait(1)); cuts.push([0, (Date.now() - T0) / 1000 + 0.2]);
  await card("Everyone has an NDVI map.<br>What happens after the alert?", "An operations copilot that turns satellite imagery into decisions,<br>work orders and <b style='color:#fff'>proof of results</b>, field by field.", 4800);

  // ---------------------------------------------------------------- 1. map
  await go("/map", MAP, 500);
  await caption("A soybean farm in Mato Grosso, Brazil · each square is a 30 m cell compared with <b>its own history</b>", 2600);
  const sec = await page.locator("section").first().boundingBox();
  const opt = (d) => page.locator(`[role=option][title^="${d}"]`).first();
  await caption("Go back a few weeks: F04 was healthy…", 300);
  await click(opt("Dec 20, 2025"), 2200);
  await caption("…until 14 days without rain. The pivot's southwest sector turns <b>critical</b>", 300);
  await click(opt("Jan 9, 2026"), 2600);

  // ---------------------------------------------------------------- 2. overview
  await go("/", SEL("table tbody tr"));
  await caption("Ranked by <b>money at risk (R$)</b>, not by color: F04 is this week's #1", 1200);
  await pointAt(page.locator("table tbody tr").first()); await wait(1600);
  await pointAt(page.getByText("Estimated exposure").first()); await wait(1400);

  // ---------------------------------------------------------------- 3. cell + hypotheses
  await go("/map", MAP, 300);
  await click(page.locator(".maplibregl-marker", { hasText: "F04" }), 2600);
  const red = await page.evaluate(() => {
    const m = window.__agroMap; if (!m) return null;
    const reds = m.queryRenderedFeatures({ layers: ["cells-fill"] })
      .filter((f) => m.getFeatureState({ source: "cells", id: f.id }).level === 2)
      .map((f) => { const ring = f.geometry.coordinates[0]; const lon = ring.reduce((a, c) => a + c[0], 0) / ring.length, lat = ring.reduce((a, c) => a + c[1], 0) / ring.length; return m.project([lon, lat]); });
    if (!reds.length) return null;
    const cx = reds.reduce((a, p) => a + p.x, 0) / reds.length, cy = reds.reduce((a, p) => a + p.y, 0) / reds.length;
    const best = reds.sort((a, b) => Math.hypot(a.x - cx, a.y - cy) - Math.hypot(b.x - cx, b.y - cy))[0];
    const r = m.getCanvas().getBoundingClientRect();
    return { x: r.left + best.x, y: r.top + best.y };
  });
  await clickAt(red?.x ?? sec.x + sec.width * 0.33, red?.y ?? sec.y + sec.height * 0.68, 2200);
  await caption("Satellite is a <b>signal</b>, not a diagnosis: hypotheses with evidence, confidence and missing data", 1200);
  const aside = await page.locator("aside").last().boundingBox();
  await wheel(aside.x + aside.width / 2, aside.y + 500, 520, 1600); await wait(1800);
  await wheel(aside.x + aside.width / 2, aside.y + 500, 520, 1400);
  await caption("Exposure as an <b>R$ range</b>, with visible assumptions", 2200);

  // ---------------------------------------------------------------- 4. copilot
  await click(page.getByRole("button", { name: "Copilot", exact: true }), 900);
  await caption("The copilot queries the app's data: it never invents measurements", 300);
  const answers = page.getByText("Next action.", { exact: true });
  const before = await answers.count();
  await click(page.getByText(/Why is (Field 04|F04) red\?/).first(), 300);
  await answers.nth(before).waitFor({ timeout: 20000 }); await wait(3800);
  const box = page.locator("textarea").last();
  await click(box, 200);
  await box.pressSequentially("Has this happened here before? What worked?", { delay: 38 });
  await page.keyboard.press("Enter");
  await caption("<b>Field memory</b>: what worked last season, with caveats", 300);
  await answers.nth(before + 1).waitFor({ timeout: 20000 }); await wait(4200);
  await click(page.getByRole("button", { name: "Close copilot" }), 700);

  // ---------------------------------------------------------------- 5. create inspection
  await caption("From alert to <b>work order</b> in one click", 200);
  await click(page.getByRole("button", { name: /Create inspection for this zone/ }), 1600);
  const link = page.getByRole("link", { name: /Inspection #\d+ created/ });
  await link.waitFor({ timeout: 15000 });
  await pointAt(link); await wait(1200);
  const taskPath = await link.getAttribute("href");

  // ---------------------------------------------------------------- 6–8. phone: inspection, verification, intervention
  await page.setContent(`<body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;gap:90px;background:radial-gradient(circle at 70% 30%,#172540,#0a1120 65%);font-family:system-ui,-apple-system,Segoe UI,sans-serif">
    <div style="max-width:470px;color:#fff">
      <div style="font-size:15px;font-weight:600;letter-spacing:2px;color:#7ee2a1;text-transform:uppercase">In the field</div>
      <div id="__side" style="margin-top:14px;font-size:38px;font-weight:700;line-height:1.18;letter-spacing:-.6px">The field technician gets the inspection on their phone</div>
      <div id="__sub" style="margin-top:16px;font-size:20px;line-height:1.5;color:#a7b4cc">With a draft saved on the device and photos of the crop.</div>
    </div>
    <div style="padding:12px;border-radius:52px;background:#05080f;box-shadow:0 40px 80px -20px rgba(0,0,0,.7),0 0 0 2px #22345a">
      <iframe id="__phone" src="${BASE}${taskPath}" style="display:block;width:390px;height:800px;border:0;border-radius:40px;background:#f4f6f8"></iframe>
    </div></body>`);
  const ph = page.frameLocator("#__phone");
  await cut(async () => { await overlay(); await ph.getByText("Start field inspection").waitFor({ timeout: 60000 }); await wait(800); });
  await wait(1500);
  const side = async (title, sub, hold = 0) => {
    await page.evaluate(([t, s]) => { document.getElementById("__side").innerHTML = t; document.getElementById("__sub").innerHTML = s; }, [title, sub]);
    await wait(500 + hold);
  };
  await click(ph.getByText("Start field inspection"), 1200);
  await side("Records what they found", "Findings, verified cause and photos. The draft stays saved on the device.");
  const ta = ph.locator("textarea").first();
  await click(ta, 200);
  await ta.pressSequentially("Wilting in the hot hours in the SW sector. Sprinklers on towers 7 and 8 clogged. Beat-sheet counts below action threshold.", { delay: 14 });
  await wait(500);
  await click(ph.getByRole("button", { name: "Water stress" }), 900);
  if (PHOTO) { await ph.locator("input[type=file]").setInputFiles(PHOTO); await wait(1800); }
  await click(ph.getByText("Complete inspection"), 1800);
  await side("The agronomist signs off", "No intervention is approved without verification. Chemicals require a prescription.", 600);
  await click(ph.getByText("Verify inspection"), 1800);
  await side("Logs what was done and what it cost", "Approved action, owner and actual cost go into the field's memory.", 600);
  await click(ph.getByText("Record intervention"), 1800);
  await side("And measures the outcome", "In the demo, 3 post-intervention scenes are <b style='color:#c4b5fd'>simulated</b> and labeled as such.", 600);
  await click(ph.getByText("Simulate post-intervention observations (demo)"), 3200);
  const rlink = ph.getByText("Open outcome report");
  await cut(() => rlink.waitFor({ timeout: 30000 })); await pointAt(rlink); await wait(1800);
  const outcomes = await api("/api/outcomes");
  const outcomeId = outcomes.find((o) => o.user_created)?.id ?? outcomes[0].id;

  // ---------------------------------------------------------------- 9. outcome
  await go(`/outcomes/${outcomeId}`, SEL("figure svg path"), 1200);
  await caption("Outcome measured against a <b>comparison area</b>, not just before × after", 2600);
  await wheel(W / 2 + 120, 500, 560, 1800);
  await caption("F04 critical area: <b>36 ha → 7 ha</b>. Association, not proof of causation — and the report says so", 3600);
  await wheel(W / 2 + 120, 500, 500, 1400); await wait(1800);

  // ---------------------------------------------------------------- 10. memory
  await go(`/fields/${f04.id}`, TXT("Field agronomic memory"), 1200);
  await wheel(W / 2, 500, 1100, 2000);
  await caption("Every season becomes <b>memory</b>: anomaly → inspection → intervention → outcome", 3600);

  if (hasSentinel) {
    await go("/map", MAP, 300);
    await click(page.getByRole("radio", { name: "Real Sentinel-2" }), 2400);
    await caption("And the pipeline already reads real <b>Sentinel-2</b> imagery (Copernicus), with clouds masked", 3200);
  }

  // ---------------------------------------------------------------- closing
  await card("From alert to proof of results.", "Prioritizes by money at risk · treats satellite as a signal · closes the loop with measurement<br>and builds the agronomic memory of every field.<br><span style='font-size:17px;color:#7f8ba3'>MVP with demo data · github.com/iamluanem/agroCopilot</span>", 5200);

  await ctx.close(); await browser.close();
  const raw = readdirSync(tmp).find((f) => f.endsWith(".webm"));
  const webm = join(OUT, "agrocopilot-demo.webm");
  renameSync(join(tmp, raw), webm);
  rmSync(tmp, { recursive: true, force: true });
  console.log(`Video saved to ${webm}`);
  writeFileSync(join(OUT, "cuts.json"), JSON.stringify(cuts));
  const keep = cuts.length ? `select='not(${cuts.map(([a, b]) => `between(t,${a.toFixed(2)},${b.toFixed(2)})`).join("+")})',setpts=N/FRAME_RATE/TB,` : "";
  const ff = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-i", webm, "-vf", `${keep}fps=30,format=yuv420p`, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-movflags", "+faststart", join(OUT, "agrocopilot-demo.mp4")]);
  console.log(ff.status === 0 ? `MP4 ready at ${join(OUT, "agrocopilot-demo.mp4")}` : "ffmpeg not found: the .webm works as is; convert it to MP4 if you need to.");
  await api("/api/demo/reset", "POST");
}

main().catch(async (e) => {
  console.error(e);
  try { await globalThis.__page?.screenshot({ path: join(OUT, "error.png") }); console.error(`Screen at the time of the error: ${join(OUT, "error.png")}`); } catch { /* no page */ }
  process.exit(1);
});
