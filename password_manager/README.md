🛡️ Password Vault CLI

░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓████████▓▒░▒▓███████▓▒░  
░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░
░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓██████▓▒░ ░▒▓███████▓▒░  
░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░
░▒▓████████▓▒░░▒▓██████▓▒░░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░

Manage your passwords effortlessly with a simple and secure command-line tool designed to keep your credentials safe.

===================
FEATURES
===================

- Secure password storage using encryption (Fernet)
- Search and view saved passwords with rich UI
- Delete credentials you no longer need
- Generate strong passwords instantly
- Easy to use menu navigation with arrow keys

===================
REQUIREMENTS
===================

- Python 3.11+
- cryptography
- questionary
- prompt_toolkit
- PyYAML
- rich

===================
INSTALLATION
===================

1. Install `uv`:

   > curl -LsSf https://astral.sh/uv/install.sh | sh

2. Sync dependencies:
   > uv sync # Install all dependencies from uv.lock

===================
USAGE
===================

Run the application:

> python main.py

You'll see a menu like this:

╭───────────────────────────────────────────╮
│ 🔽 Menu Options │
│ Use arrow keys to choose an option below. │
╰───────────────────────────────────────────╯
? What would you like to do? (Use arrow keys)
» 🔓 View saved passwords  
 ➕ Add a new password  
 🔧 Generate a password  
 ❌ Exit

===================
SECURITY
===================

- All passwords are encrypted with a symmetric key (`secret.key`)
- The `passwords.yaml` file contains encrypted entries only
- Keep your `secret.key` safe and private — without it, passwords cannot be decrypted

===================
ROADMAP IDEAS
===================

- Master password to unlock vault
- Export/import functionality
- Clipboard copy with auto-clear
- Cloud sync or backup (optional)

===================
LICENSE
===================

MIT License — free to use and modify.
