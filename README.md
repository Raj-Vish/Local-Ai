# Company AI Assistant — Project Guide

**A simple explanation of what this project is, what it does today, and how its parts fit together.**

This guide is written for anyone — you do not need to be a programmer to follow it.

---

## 1. What is this project, in one paragraph?

Imagine a private version of ChatGPT that a company runs for its own staff. An employee logs in, types a question like *"What is our remote work policy?"*, and gets an answer based on the company's own internal documents — not from the public internet.

**This project is the screen that employee looks at.** It is the chat window, the login page, the sidebar with past conversations, the settings panel, the dark/light mode. Everything a person sees and clicks.

---

## 2. The most important thing to understand

Think of a restaurant. There are two halves:

| The half | In a restaurant | In software |
|---|---|---|
| What the customer sees | The dining room — tables, menu, waiter | The **frontend** (the screens) |
| What the customer never sees | The kitchen — chefs, ingredients, ovens | The **backend** (the brain) |

**Right now, this project is only the dining room. The kitchen has not been built yet.**

The screens are complete and polished. But there is no real artificial intelligence behind them yet. When you type a question, the app does not actually think — it replies with a pre-written, fake answer that was typed into the code by hand.

**Why build it this way?** Because you can perfect the entire customer experience — the layout, the buttons, the feel — before spending time on the expensive, complicated kitchen. When the real AI is ready later, it plugs into screens that are already finished and tested.

### What is real vs. what is pretend

| Feature | Status |
|---|---|
| Login page, with error messages | ✅ Real screen — but accepts **any** email and any 4-letter password |
| Chat window and message bubbles | ✅ Fully real |
| Answers appearing word-by-word | ⚠️ Real animation, but the words are **fake and pre-written** |
| Sidebar with past conversations | ⚠️ Real list — but the old chats are **made-up samples** |
| Dark mode / Light mode | ✅ Fully real and working |
| Settings, clear history, memory switch | ✅ Real buttons that work on screen |
| Attaching a document or photo | ⚠️ You can pick a file and see its name — the file is **not sent anywhere** |
| The actual AI answering your question | ❌ **Does not exist yet** |
| Searching real company documents | ❌ **Does not exist yet** |
| Real security / real accounts | ❌ **Does not exist yet** |

> ⚠️ **Please do not treat the login as security.** It is a drawing of a lock, not a lock. Anyone can get in with any email address.

---

## 3. What you can actually do today

If you run the app (see `TECH-STACK.md` for how), here is the full experience:

1. **A login screen appears.** Type any email that looks like an email (`test@company.com`) and any password with 4 or more characters. Click Sign In. A small spinner runs for about a second, then you are in.
2. **The main chat screen opens.** On the left is a sidebar; the middle is the conversation; at the bottom is the box where you type.
3. **A welcome screen greets you** with four suggested questions. Clicking one drops it into the typing box for you.
4. **Type anything and press Enter.** Three dots appear (as if the assistant is thinking), then an answer types itself out word by word. The answer is always the same template with your question inserted into it.
5. **You can press Stop** while it is typing to interrupt it mid-sentence.
6. **Press Shift+Enter** instead of Enter to start a new line rather than sending.
7. **Your question becomes the title** of that conversation in the sidebar, under "Recent Chats".
8. **Click the + button** to attach a document or photo. Its name shows as a small tag above the typing box. You can remove it by clicking the ×.
9. **Hover an answer** to reveal a "Copy" button that copies the text.
10. **Open Settings** (bottom left) to switch between Light, Dark, and System theme, flip a Memory switch, or clear your conversation history (it asks you to click twice, so you cannot wipe it by accident).

---

## 4. How the app is built — the "boxes inside boxes" idea

A web app is built out of **components**. A component is simply one reusable piece of the screen, like a Lego brick. Small bricks snap into bigger bricks.

Here is the whole app, drawn as bricks:

```
┌─────────────────────────────────────────────────────────┐
│  App            ← the outermost brick. Holds everything. │
│                                                          │
│  Not logged in?  ──►  ┌──────────────┐                   │
│                       │  LoginView   │  the sign-in form │
│                       └──────────────┘                   │
│                                                          │
│  Logged in?      ──►  ┌─────────┬────────────────────┐   │
│                       │ Sidebar │      ChatView      │   │
│                       │         │  ┌──────────────┐  │   │
│                       │ • New   │  │ EmptyState   │  │   │
│                       │   Chat  │  │  or a list   │  │   │
│                       │ • Past  │  │  of Chat-    │  │   │
│                       │   chats │  │  Message     │  │   │
│                       │ • Set-  │  ├──────────────┤  │   │
│                       │   tings │  │  Composer    │  │   │
│                       │ • Logout│  │  (type here) │  │   │
│                       └─────────┴──┴──────────────┴──┘   │
│                                                          │
│  Settings clicked? ──► ┌────────────────┐                │
│                        │ SettingsModal  │  pop-up window │
│                        └────────────────┘                │
└─────────────────────────────────────────────────────────┘
```

**What each brick does:**

| Brick | Its one job |
|---|---|
| **App** | The boss. Decides which screen to show and remembers who is logged in. |
| **LoginView** | The sign-in form and its error messages. |
| **Sidebar** | The left panel: your name, past chats, Settings and Logout buttons. |
| **ChatView** | The middle area: holds the conversation and the typing box. |
| **ChatMessage** | **One single message bubble.** Used once per message. |
| **EmptyState** | The "How can I help you today?" welcome shown before you type anything. |
| **Composer** | The typing box at the bottom, plus attach and send buttons. |
| **SettingsModal** | The settings pop-up window. |

Each brick lives in its own file inside the `src/components/` folder, named after itself.

---

## 5. How the pieces talk to each other

This is the single most important idea in the whole project, and it is simpler than it sounds.

### There is one boss, and information flows downhill

Only **App** is allowed to remember the important things:

- Who is logged in
- Whether the sidebar is open
- Whether the settings window is open
- Whether the Memory switch is on

Every other brick is "dumb" on purpose. It does not remember anything important. It is simply **handed** what it needs to display, and **handed** a phone number to call when the user clicks something.

```
                    ┌──────────┐
                    │   App    │   ← the only brick that remembers
                    └────┬─────┘
        hands down info  │  ▲  reports clicks back up
                         ▼  │
        ┌──────────┬─────────────┬──────────────┐
        │ Sidebar  │  ChatView   │ SettingsModal│
        └──────────┴──────┬──────┴──────────────┘
                          ▼
                 ┌─────────────────┐
                 │ ChatMessage,    │
                 │ Composer, etc.  │
                 └─────────────────┘
```

**A real example.** When you click "New Chat" in the sidebar:

1. Sidebar does **not** clear the conversation itself. It cannot — it does not own the conversation.
2. Sidebar simply shouts upward: *"the New Chat button was pressed."*
3. App hears it, empties the conversation, and hands the now-empty conversation back down.
4. ChatView receives an empty conversation and redraws itself as the welcome screen.

**Why do it this way?** Because there is exactly one copy of the truth. If three different bricks each kept their own copy of the conversation, they would slowly drift apart and start disagreeing — that is where confusing bugs come from. One boss, one truth.

### Two "helper packs" do the heavy lifting

Some logic is too big to leave sitting in App. It gets moved into a **hook** — think of it as a self-contained helper pack that App picks up and uses.

**`useChatSession`** — the conversation manager. This is the busiest file in the project. It alone handles:
- the list of messages
- what you have typed so far
- whether an answer is currently being written
- the files you attached
- the list of past conversations
- starting, stopping, loading and clearing conversations

**`useTheme`** — the dark/light manager. It knows your choice (Light, Dark, or "follow my computer") and works out which one to actually paint. If you choose "System" and then change your laptop from light to dark mode, the app notices and switches instantly, without a refresh.

There are three smaller helpers too: one grows the typing box as you type, one closes the attach menu when you click elsewhere, and one makes the settings pop-up behave properly for keyboard users.

### How dark mode actually works

Every colour in the app is written as a **nickname** instead of a real colour. Nothing says "dark grey" — it says "background colour", and a separate list decides what "background colour" currently means.

```
Light mode list:            Dark mode list:
  background = white          background = near-black
  text       = black          text       = near-white
```

Switching theme swaps which list is active. All ~20 colours change at once, everywhere in the app. Nobody has to hunt through the files changing colours one by one — a huge time-saver, and it makes it impossible to miss a spot.

---

## 6. The fake AI, explained

When you send a message, here is exactly what happens inside:

1. Your message is added to the conversation.
2. An **empty** answer bubble is added below it. Because it is empty, it shows three bouncing dots.
3. The app waits **0.45 seconds**, doing nothing. This pause exists purely so the "thinking" dots are visible — without it the answer would appear instantly and feel cheap and unrealistic.
4. A pre-written sentence is chopped into individual words.
5. Every **25 milliseconds**, one more word is glued onto the answer bubble.
6. When the words run out, it stops and the Stop button turns back into a Send button.

That's the entire illusion. All the pre-written text lives in one file: `src/data/mockData.js`.

---

## 7. Small details that were handled carefully

These are quiet decisions that took thought. They are worth knowing because they look pointless until you remove one and something breaks.

**Pressing Stop before any words arrive.** If you hit Stop during those first 0.45 seconds, the empty answer bubble is deleted. Without this, you would be left staring at a blank bubble with three dots bouncing forever, which could never fill in.

**Leaving the page while an answer is typing.** The word-by-word timer is switched off. Otherwise it would keep quietly writing into a conversation nobody is looking at any more — wasting effort and risking odd behaviour later.

**The double-word bug that was prevented.** During development, React deliberately runs some code twice to help catch mistakes. Written the obvious way, this made every answer come out with every word doubled — "Based Based on on internal internal records records". The code was written to make a fresh copy of the message each time rather than editing it in place, which sidesteps it entirely. There is a note in the file explaining this so nobody "simplifies" it back into a bug.

**The Copy button never lies.** Copying to the clipboard can silently fail — browsers block it in certain situations. The code checks whether the copy genuinely worked, and only then shows "Copied ✓". If it failed, there is a backup method, and if that also fails, no false confirmation is shown.

**The settings pop-up respects the keyboard.** Press Escape to close it. Press Tab repeatedly and focus stays trapped politely inside the window instead of wandering off behind it. Close it, and focus jumps back to the button you opened it with. This matters enormously for people who cannot use a mouse.

**Clearing history asks twice.** The first click changes the button to "Confirm". Only the second click deletes. A single misclick cannot destroy anything.

---

## 8. What is missing, and where the kitchen will connect

The good news: connecting a real AI later touches **very few places**. The screens were built so the fake parts sit in obvious, isolated spots.

| To make this real, replace... | Which currently... |
|---|---|
| The fake reply generator in `src/data/mockData.js` | Returns one hand-written sentence |
| The word-by-word timer in `src/hooks/useChatSession.js` | Fakes typing with a stopwatch, instead of receiving real words from a server |
| The 0.9-second pause in `src/components/LoginView.jsx` | Pretends to check a password |
| The file attachment handler in `src/components/Composer.jsx` | Records the file's name but never uploads it |
| The sample conversations in `src/data/mockData.js` | Are three invented examples |

Beyond that, still to be built: a real login system, a place to store conversations permanently (today everything vanishes when you refresh the page), the document-reading engine, and the AI itself.

---

## 9. Where everything lives

```
├── index.html                 The empty page the app is poured into
├── package.json               The project's ingredient list
│
└── src/
    ├── main.jsx               The ignition switch — starts the app
    ├── App.jsx                The boss (see section 5)
    │
    ├── components/            One file per visible piece of screen
    │   ├── LoginView.jsx          Sign-in form
    │   ├── Sidebar.jsx            Left panel
    │   ├── ChatView.jsx           Middle conversation area
    │   ├── ChatMessage.jsx        A single message bubble
    │   ├── EmptyState.jsx         "How can I help you today?"
    │   ├── Composer.jsx           The typing box
    │   └── SettingsModal.jsx      Settings pop-up
    │
    ├── hooks/                 Reusable logic, no visuals
    │   ├── useChatSession.js      Runs the whole conversation
    │   ├── useTheme.js            Dark / light mode
    │   ├── useAutoGrow.js         Grows the typing box
    │   ├── useOutsideClick.js     Closes menus on outside click
    │   └── useDialogA11y.js       Keyboard support for pop-ups
    │
    ├── lib/
    │   └── clipboard.js           Copy-to-clipboard, done safely
    │
    ├── data/
    │   └── mockData.js        ★ ALL the fake content lives here
    │
    └── styles/                Appearance only
        ├── base.css               ★ The colour lists for both themes
        ├── auth.css               Login page looks
        ├── sidebar.css            Sidebar looks
        ├── chat.css               Chat area looks
        └── settings.css           Settings pop-up looks
```

**The two files marked ★ are the ones worth opening first.** `mockData.js` holds every fake sentence in the app. `base.css` holds every colour.

---

## 10. In one minute

- It is the **screen half** of a private company AI assistant. Complete and polished.
- The **thinking half does not exist yet.** All answers are pre-written fakes.
- **App is the boss** and holds the truth; every other piece is handed what to show.
- **`useChatSession`** runs the conversation; **`useTheme`** runs dark mode.
- **Colours are nicknames**, so themes swap in one move.
- **All fake content is in one file**, so it is easy to find and replace later.
- **The login is decorative, not secure.**

➡️ For the tools used, why they were chosen, and how to run this on another computer, see **`TECH-STACK.md`**.
