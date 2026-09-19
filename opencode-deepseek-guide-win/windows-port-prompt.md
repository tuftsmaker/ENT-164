# Prompt: Windows port of the ENT-164 "Making with AI" guide

Recreate the ENT-164 "Making with AI" beginner setup guide as a **Windows** version, with real Windows screenshots captured on this machine, and render it to PDF.

## Source material
- The macOS version lives in `opencode-deepseek-guide/` (`guide.html` + `shots/`). If it isn't next to this prompt, ask me for it before starting.
- Use it as the source of truth: structure, wording, design system, figure conventions, page order.
- Product: OpenCode desktop app (Electron) + OpenRouter (provider) + DeepSeek V4.1 Flash (model).
- Audience: students of ENT-164 Intro to Making (Tufts) with zero technical experience. The class workspace on OpenRouter is "ENT-164 Intro to Making"; students join by signing up with their Tufts email and requesting to join (admin approves). Access is covered by a shared class budget — students don't pay but should keep usage to class work.

## Deliverable
- `opencode-deepseek-guide/opencode-deepseek-v4.1-flash-setup.pdf` (8–9 pages, A4), plus the updated `guide.html` and `shots/` used to build it.
- Every app/website screenshot must be captured live on this Windows machine — no reused macOS images, no mockups or redrawn UI.

## Content changes for Windows (keep everything else identical)
1. **Step 1 — Download the OpenCode app:** opencode.ai/download → the Windows x64 installer under "OpenCode Desktop". (Keep it simple; omit package-manager alternatives.)
2. **Step 2 — Install the app:** run the downloaded `.exe` installer and follow the prompts. If Windows shows "Windows protected your PC", click **More info → Run anyway**. Then open OpenCode from the **Start menu** (press the Windows key, type "OpenCode", press Enter).
3. **Steps 3–7** (join class on OpenRouter, create your API key, connect OpenRouter in the app, choose DeepSeek V4.1 Flash, ask your first question): same flow and wording, but all screenshots must show Windows UI.
4. Replace macOS-specific details everywhere: no Spotlight/⌘ symbols; use the Start menu and Ctrl-based shortcuts. "To quit" = close the window or Alt+F4.
5. **Troubleshooting table:** swap macOS rows for Windows equivalents while keeping the shared rows:
   - "Windows protected your PC" → More info → Run anyway
   - Can't find the app → Start menu → type "OpenCode"
   - Antivirus/SmartScreen blocks it → allow it (the app is signed and comes from opencode.ai)
   - Installer doesn't seem to do anything → re-download from opencode.ai/download
   - Keep: provider panel location, OpenRouter not listed, invalid key, class budget error (don't add credit — tell your instructor), model missing from list, no answer/slow.
6. **Keep unchanged:** cover (Lucide hammer mark in a Tufts-blue rounded square, class title "ENT-164 · Intro to Making", title "Making with AI", subtitle "OpenCode + DeepSeek V4.1 Flash", pills: About 15 minutes · For Windows · Provider: OpenRouter · Model: DeepSeek V4.1 Flash, plus the app start screen as the hero image); the "Why DeepSeek V4.1 Flash for this class?" info card; "What you'll need" checklist with "Nothing to pay — the class budget covers AI usage for your coursework"; the class-budget callout in the key step; the Tufts palette (Tufts Blue #3E8EDE, Tufts/Bessie Brown #63493A/#3D2E25, Candle White #F2EDE7, tip green #1A5532, warn orange #F37121); step-number circles; callouts; "Figure N." captions; `break-inside: avoid` guards on figures/images/captions.

## Screenshots to capture on Windows (live)
- Download page in a browser showing the Windows installer.
- OpenCode app start screen (opencode logo, message box, "DeepSeek V4.1 Flash" selected).
- "Connect OpenRouter" dialog with the API-key field; the "OpenRouter connected" toast (tight centered crop).
- Manage models panel: search "v4.1 flash", DeepSeek V4.1 Flash toggle ON.
- Model list filtered to "v4.1" with DeepSeek V4.1 Flash (OpenRouter).
- A real chat exchange with the reply.
- Capturing method: the desktop app is Electron — relaunch it with `--remote-debugging-port=9222` and drive it over CDP (Node ≥22 has a global WebSocket; no extra packages needed) for reliable clicks and pixel-accurate captures; use Playwright/browser automation for web pages. For window chrome or installer screens, use a native Windows capture (Win+Shift+S or a PowerShell/.NET screen capture script).
- Use an isolated profile for the demo: launch with a temporary `USERPROFILE`/`--user-data-dir` and an auth file containing only the OpenRouter credential, so the existing app data isn't touched. Ask before installing anything system-wide.

## Render + verify
- Render with headless Edge or Chrome: `msedge --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="...pdf" "file:///.../guide.html"` using a fresh temp user-data-dir.
- Verify page by page (convert pages to images with `pdftoppm`/ImageMagick if available): no split figures, no orphaned or overlapping captions, caption directly under each figure, page count 8–9.
- Report the final PDF path and a short summary of what differs from the macOS edition.

If anything is ambiguous (for example, how to obtain a key for the demo profile), ask me before proceeding.
