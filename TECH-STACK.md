# Tools, Technology & Setup Guide

**What was used to build this, why each thing was chosen, and how to get it running on a different computer.**

Written for beginners and non-technical readers. Every term is explained the first time it appears.

---

# PART 1 — The tools we used, and why

## First, three words you will keep seeing

| Word | Plain meaning |
|---|---|
| **Library** | Somebody else's ready-made code that you borrow instead of writing it yourself. Like buying flour instead of growing wheat. |
| **Package** | One downloadable bundle of that borrowed code. |
| **Dependency** | A package your project *depends on* — remove it and the project stops working. |

Software is built mostly from borrowed pieces. That is normal, and it is how everything from banking apps to Netflix is made.

---

## The main ingredients

### 1. React — version 19.2

**What it is:** The tool that draws the screen and keeps it up to date.

**The problem it solves.** Without React, if you wanted to add one new message to a chat, you would have to write step-by-step instructions by hand: *"find the message list, create a new bubble, put the text inside, colour it, attach it at the bottom, scroll down."* For every single change. It becomes an unmanageable mess very quickly.

React flips this around. You describe **what the screen should look like** for any given situation — *"a list of messages, one bubble each"* — and React works out the steps to get there. You change the list; the screen follows automatically.

**Why we chose it:** It is the most widely used tool of its kind in the world. That means the most tutorials, the most answered questions online, and by far the easiest hiring pool. For a company project that other people must maintain later, that matters more than raw cleverness.

---

### 2. Vite — version 8.2

*Pronounced "veet" — French for "fast".*

**What it is:** The workshop the project is built in.

**Two problems it solves:**

**While building:** You save a file, and the change appears in your browser in well under a second, without losing your place. Older tools took 10–30 seconds for the same thing. Over a full day of work, that difference is enormous.

**When shipping:** Browsers cannot run this project's code directly — it is written in a friendlier style meant for humans. Vite translates it all into plain, fast files that any browser understands, and squeezes them as small as possible. That is what the `npm run build` command does.

**Why we chose it:** It is the current standard for React projects and needs almost no configuration. Our entire settings file is four lines long.

---

### 3. lucide-react — version 1.33

**What it is:** A collection of well over a thousand ready-made icons — the paperclip, the send arrow, the sun and moon, the trash can, the eye that shows and hides a password.

**Why we chose it:** Drawing consistent icons by hand is slow, and mismatched icons make an app look amateurish instantly. These are clean, professional, free to use commercially, and importantly they **adapt to their surroundings** — an icon automatically turns light in dark mode and dark in light mode, without anyone doing anything.

Also, only the icons we actually use get included in the final app. The rest are left behind and cost us nothing.

---

### 4. Plain CSS — no framework

**What it is:** CSS is the language that controls appearance — colours, spacing, sizes, animation.

**What we did:** Wrote it ourselves, split into five small files that match the screens: `base.css`, `auth.css`, `sidebar.css`, `chat.css`, `settings.css`. Find the sidebar looking wrong? Open `sidebar.css`. That is the entire filing system.

**Why we did not use a framework** (such as Tailwind or Bootstrap, which many projects use): Those add a large extra thing for every developer to learn, and this app is not complicated enough to need it. Seven small components, one consistent style. Plain CSS keeps the project small and means anyone who knows basic web design can contribute without learning our specific tooling first.

The dark/light theme is handled by a built-in CSS feature called **custom properties** — the colour "nicknames" explained in `README.md` section 5. No library needed for it at all.

---

### 5. ESLint — version 10.8

**What it is:** An automatic proofreader for code.

**What it does:** Reads every file looking for mistakes — something spelled wrong, something written but never used, a common React trap — and points at the exact line. It runs in a second and catches the small errors that would otherwise cost half an hour of confused hunting.

**Why we chose it:** It is the standard for JavaScript, and it came pre-configured with the project. It costs nothing to keep and quietly prevents a steady drip of small bugs.

---

## Every package, in one table

Everything here is free and open-source. This is copied from `package.json`, the project's official ingredient list.

**Needed to run the app:**

| Package | Version | What it does |
|---|---|---|
| `react` | 19.2.8 | Draws and updates the screen |
| `react-dom` | 19.2.8 | Connects React to the web browser specifically |
| `lucide-react` | 1.33.0 | The icons |

**Needed only while building — not shipped to users:**

| Package | Version | What it does |
|---|---|---|
| `vite` | 8.2.0 | The workshop / build tool |
| `@vitejs/plugin-react` | 6.0.4 | Teaches Vite to understand React |
| `eslint` | 10.8.0 | The proofreader |
| `@eslint/js` | 10.0.1 | The proofreader's standard rulebook |
| `eslint-plugin-react-hooks` | 7.1.1 | Extra rules for React's trickiest feature |
| `eslint-plugin-react-refresh` | 0.5.3 | Protects the instant-refresh feature |
| `globals` | 17.7.0 | Tells the proofreader which browser words are legitimate |
| `@types/react` | 19.2.17 | Helps the code editor autocomplete React |
| `@types/react-dom` | 19.2.3 | Same, for react-dom |

**That's it — 12 packages total.** For comparison, many projects of this size carry 50 or more. Fewer packages means faster installs, fewer security alerts, and less that can break.

---

## What we deliberately did NOT use

Choosing to leave something out is a real decision. Here is what we skipped and why — this is worth reading, because a newcomer might otherwise assume it was an oversight.

| Not used | What it would have added | Why we skipped it |
|---|---|---|
| **TypeScript** | Catches a whole category of mistake before you run the app | Real benefit, but a real learning curve too. At this size, plain JavaScript keeps the project open to more people. Worth revisiting if it grows. |
| **A router** | Proper web addresses like `/chat` and `/settings` | There are only two screens: logged out and logged in. A single yes/no check does the job. Adding a router would be more machinery than the problem deserves. |
| **Redux / Zustand** (state managers) | Sophisticated memory management for large apps | Designed for apps where dozens of pieces need the same information. Ours has one boss and short chains. React's built-in memory is enough. |
| **Tailwind / Bootstrap** (CSS frameworks) | Faster styling, once learned | An extra language to learn for an app this small, with one consistent look throughout. |
| **A test framework** | Automated checks that features still work | Honest answer: not set up yet. Fine while the app is all mock data; it should be added before the real AI is connected. |
| **A backend framework** | The actual server and AI | Deliberately postponed. Screens first, kitchen second — see `README.md` section 2. |

---

# PART 2 — Setting this up on another computer

Follow these steps in order. **Total time: about 5 minutes**, most of it waiting for a download.

---

## Step 1 — Install Node.js

**What is Node.js?** JavaScript was invented to run inside web browsers. Node.js lets it run directly on your computer instead. Our building tools are written in JavaScript, so they need Node to run. It also brings along **npm**, which downloads all those borrowed packages for you.

**How to install:**

1. Go to **https://nodejs.org**
2. Download the **LTS** version. LTS means "Long Term Support" — the stable, boring, reliable one. That is what you want.
3. Run the installer and accept all the defaults.

> **Version requirement:** You need **Node 20 or newer.** Version 18 and below will fail — our build tool no longer supports them. This project was built and tested on **Node 24.18.0 with npm 11.16.0**. Any recent LTS version (20, 22 or 24) is fine.

**Check it worked.** Open a terminal — Command Prompt or PowerShell on Windows, Terminal on Mac or Linux — and type:

```bash
node -v
npm -v
```

You should see two version numbers, something like `v24.18.0` and `11.16.0`. If instead you see *"command not found"*, close the terminal completely, open a new one, and try again — a fresh terminal is needed to notice the new installation.

---

## Step 2 — Install Git

**What is Git?** The system that stores the project's code online and tracks its history. You need it to download the project.

- **Windows:** https://git-scm.com/download/win — accept the defaults.
- **Mac:** type `git --version` in Terminal. If it is missing, Mac offers to install it for you.
- **Linux (Ubuntu/Debian):** `sudo apt install git`

Confirm with:

```bash
git --version
```

---

## Step 3 — Download the project

In your terminal, move to wherever you keep your work (for example `cd Desktop`), then:

```bash
git clone https://github.com/Raj-Vish/Local-Ai.git
cd Local-Ai
```

`clone` means "download a full copy, history included". `cd` means "go into that folder".

You should now be inside a folder containing `package.json`, `index.html` and a `src` folder.

---

## Step 4 — Install the packages

```bash
npm install
```

**What this does:** reads `package.json`, sees the 12 packages listed there, and downloads them — plus everything *they* depend on — into a new folder called `node_modules`.

**What to expect:** one to three minutes, lots of scrolling text, and a `node_modules` folder that ends up surprisingly large (a few hundred megabytes). This is completely normal and not a mistake.

> **Tip for exact reproduction:** if you want the *identical* package versions this project was built with, run **`npm ci`** instead of `npm install`. It reads `package-lock.json`, a file that records the exact version of every single package down to the last decimal point. `npm install` may pick up newer compatible versions; `npm ci` never does. Use `npm ci` when you want certainty, `npm install` when adding something new.

> **Note:** `node_modules` is intentionally **not** stored on GitHub — it is far too large and can always be rebuilt from `package.json`. That is why this step is necessary and cannot be skipped.

---

## Step 5 — Run it

```bash
npm run dev
```

You will see something like:

```
  VITE v8.2.0  ready in 412 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

Open **http://localhost:5173/** in your browser. The login screen appears.

Sign in with any email that looks like an email and any password of 4 or more characters — for example `test@company.com` / `test`. (As `README.md` explains, the login is decorative; there is no real account system yet.)

**"localhost" simply means "this computer".** The app is running on your own machine. Nobody else can see it, and it is not on the internet.

**To stop it:** press `Ctrl + C` in the terminal.

---

## Step 6 — Try the instant refresh

With the app running, open `src/data/mockData.js` in any text editor, change some of the wording, and save.

Look at your browser — it has already updated. You did not refresh, and you were not logged out. This is Vite's headline feature and it is what makes day-to-day work fast.

---

## All the commands

Run these from inside the project folder.

| Command | What it does | When you use it |
|---|---|---|
| `npm install` | Downloads the packages | Once, after cloning |
| `npm ci` | Downloads the *exact* recorded versions | When you want a guaranteed-identical setup |
| `npm run dev` | Starts the app for development | Every time you sit down to work |
| `npm run build` | Creates the finished, optimised version in a `dist` folder | When preparing to publish |
| `npm run preview` | Shows you the built version, to check it before publishing | After `npm run build` |
| `npm run lint` | Runs the proofreader over all the code | Before sharing your changes |

---

## When something goes wrong

### "npm: command not found" or "node: command not found"
Node did not install, or your terminal has not noticed it yet. Close **every** terminal window, open a fresh one, and retry. If it still fails, reinstall Node from nodejs.org.

### "Vite requires Node.js version 20.19+" or similar
Your Node is too old. Check with `node -v`. Install the current LTS from nodejs.org, then close and reopen your terminal.

### "Port 5173 is already in use"
Something else is using that door number — most likely another copy of this app still running in a terminal you forgot about. Either close it, or run:
```bash
npm run dev -- --port 3000
```
and use `http://localhost:3000/` instead.

### The page is blank, or errors mention missing packages
The download was probably incomplete. Delete and redo it:

```bash
rm -rf node_modules package-lock.json   # Mac / Linux
npm install
```
On Windows, delete the `node_modules` folder and `package-lock.json` by hand, then run `npm install`.

### Nothing updates when I save a file
Make sure `npm run dev` is still running and has not crashed — check the terminal for red error text. If it is running fine, refresh the browser once. If it still misbehaves, stop with `Ctrl + C` and start it again.

### Everything looks unstyled and broken
Usually a mistake in a `.css` file. The terminal running `npm run dev` will name the file and line number.

---

## Wanting to show it to someone else

```bash
npm run dev -- --host
```

This prints a second address (something like `http://192.168.1.7:5173/`) that anyone **on the same Wi-Fi network** can open on their phone or laptop. Handy for demos and for checking the app on a real phone screen.

This is for local demos only. It is not a way to publish the app on the internet.

---

## Summary card

```
NEEDED FIRST     Node.js 20 or newer   (nodejs.org — take the LTS)
                 Git                   (git-scm.com)

SET UP           git clone https://github.com/Raj-Vish/Local-Ai.git
                 cd Local-Ai
                 npm install

RUN              npm run dev      →  open http://localhost:5173/

LOG IN WITH      any@email.com  /  any 4+ character password

STOP             Ctrl + C
```

➡️ For what the project does and how its parts fit together, see **`README.md`**.
