# 🛡️ Password Vault CLI

```

░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓████████▓▒░▒▓███████▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓██████▓▒░ ░▒▓███████▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓████████▓▒░░▒▓██████▓▒░░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░

```

Manage your passwords effortlessly with a simple and secure command-line tool designed to keep your credentials safe.

---

## ✨ Features

- 🔐 Secure password storage using encryption (Fernet)
- 🔍 Search and view saved passwords with rich UI
- 🗑️ Delete credentials you no longer need
- 🔧 Generate strong passwords instantly
- 🧠 Analyze password strength with real-time feedback
- 🎮 Easy to use menu navigation with arrow keys

---

## 📦 Requirements

- `Python 3.11+`
- `cryptography`
- `questionary`
- `prompt_toolkit`
- `PyYAML`
- `rich`
- `zxcvbn`

---

## ⚙️ Installation

Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Sync dependencies:

```bash
uv sync
```

> This installs all dependencies from `uv.lock`.

---

## 🚀 Usage

Run the application:

```bash
python main.py
```

You'll see a menu like this:

```
╭───────────────────────────────────────────╮
│ 🔽 Menu Options                           │
│ Use arrow keys to choose an option below. │
╰───────────────────────────────────────────╯
? What would you like to do? (Use arrow keys)
» 🔓 View saved passwords
  ➕ Add a new password
  🔍 Check your password
  🔧 Generate a password
  ❌ Exit
```

---

## 🔒 Security

- All passwords are encrypted with a symmetric key (`secret.key`)
- The `passwords.yaml` file contains encrypted entries only
- Keep your `secret.key` safe and private — without it, passwords cannot be decrypted

---

## 🛣️ Roadmap Ideas

- Master password to unlock vault
- Export/import functionality
- Clipboard copy with auto-clear
- Cloud sync or backup (optional)

---

## 📝 License

MIT License — free to use and modify.

---

## 🤝 Contributing

Feel free to open an issue or submit a pull request to contribute new features or improvements!

---
