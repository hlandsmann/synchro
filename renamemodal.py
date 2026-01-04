#!/usr/bin/env python3
from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.widgets import  Input, Label, Button
from textual.containers import Container, Horizontal

class RenameModal(ModalScreen):
    """Screen for renaming a file."""
    BINDINGS = [
        ("escape", "close", "Close modal"),
    ]
    def __init__(self, current_name):
        super().__init__()
        self.current_name = current_name

    def compose(self) -> ComposeResult:
        with Container(classes="modal-container"):
            yield Label(f"Rename '{self.current_name}' to:")
            yield Input(value=self.current_name, id="name_input")
            with Horizontal(classes="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Rename", variant="primary", id="rename")

    def on_mount(self):
        input = self.query_one(Input)
        input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rename":
            new_name = self.query_one(Input).value
            self.dismiss(new_name)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_close(self):
        self.dismiss(None)

