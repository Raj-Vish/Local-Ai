# Company AI Assistant — Project Guide

**A simple explanation of what this project is, what it does today, and how its parts fit together.**

This guide is written for anyone — you do not need to be a programmer to follow it.

---

## 1. What is this project, in one paragraph?

Imagine a private version of ChatGPT that a company runs for its own staff. An employee logs in, types a question like *"What is our remote work policy?"*, and gets an answer based on the company's own internal documents — not from the public internet.

**This project is the screen that employee looks at.** It is the chat window, the login page, the sidebar with past conversations, the settings panel, the dark/light mode. Everything a person sees and clicks.

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



### Two "helper packs" do the heavy lifting

Some logic is too big to leave sitting in App. It gets moved into a **hook** — think of it as a self-contained helper pack that App picks up and uses.

**`useChatSession`** — the conversation manager. This is the busiest file in the project. It alone handles:
- the list of messages
- what you have typed so far
- whether an answer is currently being written
- the files you attached
- the list of past conversations
- starting, stopping, loading and clearing conversations


---



## 7. Small details that were handled carefully


**The double-word bug that was prevented.** During development, React deliberately runs some code twice to help catch mistakes. Written the obvious way, this made every answer come out with every word doubled — "Based Based on on internal internal records records". The code was written to make a fresh copy of the message each time rather than editing it in place, which sidesteps it entirely. There is a note in the file explaining this so nobody "simplifies" it back into a bug.


---

## 8. Where everything lives

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

➡️ For the tools used, why they were chosen, and how to run this on another computer, see **`TECH-STACK.md`**.
