# LocalControl

A terminal-based command center for managing multiple development projects.

## Installation

To install the LocalControl CLI tool, use the `uv` package manager:

```bash
uv tool install --editable .
```

This will install the tool in editable mode, allowing for easy development and updates.

## Usage

After installation, simply run:

```bash
localcontrol
```

Or, if running from the project directory without installation:

```bash
python main.py
```

## Features

- 🔍 Automatic project discovery with virtual environment detection
- 💻 Embedded terminal with venv activation
- 🖥️ System resource monitoring (CPU, RAM, Disk, Battery, Network)
- 🚀 Quick application launcher and process killer
- ⌨️ Command autocomplete with history (like zsh-autosuggestions)
- 🔗 Git branch tracking and remote URL display
- 🎯 Fuzzy project search
- 📌 Manual project management

## Keyboard Shortcuts

- `Ctrl+P` or `/` - Search projects
- `Enter` - Open console with venv
- `r` - Open console without venv
- `t` - Open iTerm with venv
- `T` - Open iTerm without venv
- `Ctrl+K` - Focus Running Applications
- `Ctrl+C` - Interrupt process
- `Ctrl+L` - Clear console
- `?` or `h` - Show help

## Requirements

- Python >=3.9
- macOS (for iTerm integration and system monitoring)
