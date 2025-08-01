from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from utils.file import read_text  
from utils.password_generator import PasswordEnhancer
from utils.password_view import PasswordViewer
from utils.view import ScreenUtils

import questionary

console = Console()

def description():
    
    title = Text.from_markup(read_text("resource/logo.txt"), style="bright_blue")
    console.print(title)

    # Description
    console.print("Manage your passwords effortlessly with a simple and secure tool designed to keep your credentials safe.\n")

    # Features
    console.print("[green]🔐[/green] Store all your passwords securely")
    console.print("[green]🔧[/green] Generate strong, unique passwords instantly")
    console.print("[green]➕[/green] Add new credentials with ease\n")

def menu():
    # Print the menu panel
    console.print(Panel.fit(
        "[bold yellow]🔽 Menu Options[/bold yellow]\nUse arrow keys to choose an option below.",
        border_style="green"
    ))

    # Show interactive menu (outside the panel)
    choice = questionary.select(
        "What would you like to do?",
        choices=[
            "🔓 View saved passwords",
            "➕ Add a new password",
            "🔧 Generate a password",
            "❌ Exit"
        ]
    ).ask()

    return choice


def main():
    
    while True:
        ScreenUtils.clear()
        description()
        choice = menu()
        
        if choice == "🔓 View saved passwords":
            print("You selected: View saved passwords")
            viewer = PasswordViewer()
            viewer.view()
            input("\nPress Enter to return to menu...")

        elif choice == "➕ Add a new password":
            print("You selected: Add a new password")
            # Add logic here

        elif choice == "🔧 Generate a password":
            print("You selected: Generate a password")
            PasswordEnhancer().run()
            input("\nPress [Enter] to return to the menu...")  # Optional pause

        elif choice == "❌ Exit":
            print("Goodbye!")
            break 

if __name__ == "__main__":
    main()
