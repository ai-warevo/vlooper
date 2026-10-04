from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header, Static

from vlooper.database import Database


class VLooperTUI(App):
    CSS = """
    Screen {
        background: #1e1e1e;
    }
    DataTable {
        height: 1fr;
        margin: 0 2;
    }
    #status-panel {
        height: 3;
        background: $accent;
        color: white;
        content-align: center middle;
        margin: 0 2;
        border: solid $primary;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Initializing...", id="status-panel")
        yield DataTable()
        yield Footer()

    def on_mount(self) -> None:
        self.db = Database()
        self.table = self.query_one(DataTable)
        self.status_label = self.query_one("#status-panel", Static)
        self.table.add_columns("ID", "Type", "Repo", "Branch", "Status")
        self.set_interval(3, self.update_data)
        self.update_data()

    def update_data(self) -> None:
        try:
            # Update Status Panel
            active = self.db.get_active_claimed_task()
            if active:
                status_text = (
                    f"🚀 WORKING ON: #{active['id']} ({active['repo_full_name']})"
                )
            else:
                status_text = "💤 IDLE - Waiting for tasks..."
            self.status_label.update(status_text)

            # Update Table
            tasks = self.db.get_all_tasks()
            self.table.clear()
            for t in tasks:
                self.table.add_row(
                    str(t["id"]),
                    t["task_type"],
                    t["repo_full_name"].split("/")[-1],
                    t["branch_name"],
                    t["status"],
                )
        except Exception as e:
            self.status_label.update(f"⚠️ Error loading data: {e}")

    def action_quit(self) -> None:
        self.exit()


if __name__ == "__main__":
    app = VLooperTUI()
    app.run()
