#!/usr/bin/env python3
from textual.app import App
from textual.widgets import DataTable, Header, Footer, Input
from textual.coordinate import Coordinate
from datamanager import DataManager
from renamemodal import RenameModal
from actionmanager import ActionManager
from checksum import Md5Sum, Md5Stat
import os

LOCATIONS = {
    "local": {"path": "/var/tmp/portage", "label": "portage"},
    "990P4TB":  {"path": "/media/990P4TB/home/anime",   "label": "990P4TB"},
    "8TB":  {"path": "/media/8TB/anime",   "label": "8TB"},
}
# LOCATIONS = {
#     "18_1": {"path": "/media/nfs_big_3/TB8_1", "label": "18_1"},
#     "18_2":  {"path": "/media/nfs_big_3/TB8_2",   "label": "18_2"},
#     "TB_1": {"path": "/media/nfs_big_1/00_target", "label": "TB_1"},
#     "TB_2": {"path": "/media/nfs_big_2/00_target", "label": "TB_2"},
#     # "8TB":  {"path": "/media/8TB/anime",   "label": "8TB"},
# }
# LOCATIONS = {
#     # "local": {"path": "/var/tmp/portage", "label": "portage"},
# #     # "990P4TB":  {"path": "/media/990P4TB/home/anime",   "label": "990P4TB"},
# #     "990P4TB":  {"path": "/media/990P4TB/home/00_toMove",   "label": "990P4TB"},
# #     # "8TB":  {"path": "/media/8TB/anime",   "label": "8TB"},
# #     # "18TB": {"path": "/media/nfs_big_3/00_target/video_japanese", "label": "18_1"},
# #     # "990P4TB":  {"path": "/media/990P4TB/home/anime",   "label": "990P4TB"},
#
#     "990P4TB":  {"path": "/media/990P4TB/home/anime/00_toDelete",   "label": "990P4TB"},
#     "8TB":  {"path": "/media/8TB/anime/00_toDelete",   "label": "8TB"},
#     "video": {"path": "/media/8TB/video_japanese", "label": "video"},
#     "TB8_1": {"path": "/media/nfs_big_1/video_japanese", "label": "TB8_1"},
#     "TB8_2": {"path": "/media/nfs_big_2/video_japanese", "label": "TB8_2"},
#     "18TB": {"path": "/media/nfs_big_3/video_japanese", "label": "18TB"},
# }

# LOCATIONS = {
#     "TB8_1": {"path": "/media/nfs_big_1/Chinesische Serien", "label": "TB8_1"},
#     "TB8_2": {"path": "/media/nfs_big_2/Chinesische Serien", "label": "TB8_2"},
#     "TB8_3": {"path": "/media/nfs_big_3/Chinesische Serien", "label": "TB8_3"},
#         }

class FileListTable(App):
    CSS_PATH='textual.css'
    num_bindings = [
        (str(i), f"num({i})", f"Location {i}")
        for i in range(len(LOCATIONS))
    ]
    BINDINGS = [
        *num_bindings,
        ("q", "quit", "Quit"),
        ("j", "down", "Down"),
        ("k", "up", "Up"),
        ("ctrl+d", "page_down", "Page Down"),
        ("ctrl+u", "page_up", "Page Up"),
        ("m", "md5", "scan MD5"),
        ("r", "rename", "Rename"),
        ("u", "update", "Update"),
        ("o", "open", "Open"),
        ("e", "execute", "Execute"),
        ("/", "start_search", "search"),
        ("escape", "close_search", "reset search"),
    ]

    def __init__(self):
        super().__init__()
        self.locations = LOCATIONS
        self.dm = DataManager(self.locations)
        self.am = ActionManager(self.locations)
        self.md5 = Md5Sum(self.locations)
        self.items = []
        self.filtered = []
        self.search_query = ""
        # self.table_offset = 0
        self.columns = []
        self.execution_running = False

    def compose(self):
        self.title = "synchro"
        yield Header()
        yield DataTable(cursor_type="row")
        yield Input(id = "search", placeholder="Filter first column...",)
        yield Footer()

    def refresh_data_table(self):
        table = self.query_one(DataTable)
        table.clear()
        for item in self.filtered:
            display_name = item['name']
            if item['is_dir']:
                display_name = f"[bold white]{display_name}[/]"
            else:
                display_name = f"[yellow]{display_name}[/]"
            subs = "[    ]"
            if any(has_subs == True for has_subs in item['subs']):
                subs = "[bold cyan]\\[subs][/]"
            if all(has_subs == True for has_subs in item['subs']):
                subs = "[bold green]\\[subs][/]"
            md5stats = item['md5stats']
            # md5stats = [self.md5.get_md5stat_for_location(item['name'], loc_key) for loc_key in item['locations']]

            action = self.am.get_action(item['name'])
            md5 = "[     ]"
            if all(md5stat == Md5Stat.OK for md5stat in md5stats):
                md5 = "[bold green]\\[ md5 ][/]"
            if any(md5stat == Md5Stat.Incomplete for md5stat in md5stats):
                md5 = "[bold yellow]\\[     ][/]"
            if any(md5stat == Md5Stat.FilesDiffer for md5stat in md5stats):
                md5 = "[bold yellow]\\[diff ][/]"
            if any(md5stat == Md5Stat.Error for md5stat in md5stats):
                md5 = "[bold red]\\[ md5 ][/]"
            if all(action[key] == "md5" for key in item['locations']):
                md5 = "[bold cyan]\\[check][/]"
            # size = self.dm.get_dir_size_str(item)
            size = item['size']
            row=[display_name, subs, md5, size]

            for key in self.locations:
                has_file = key in item['locations']
                # is_online = self.dm.online_status.get(key, False)

                cell = ""
                if has_file:
                    cell = "[bold green][✅][/]"
                else:
                    cell = "[bold yellow]\\[  ][/]"
                if action[key] == "y":
                    cell = "[bold cyan][✓][/]"
                if action[key] == "n":
                    cell = "[bold red][❌][/]"
                row.append(cell)
            table.add_row(*row)

    def get_filtered(self):
        filtered = []
        for item in self.items:
            if self.search_query in item['name'].lower():
                filtered.append(item) 
        return filtered

    def load_data_table(self):
        self.items = self.dm.get_merged_view()
        for idx, item in enumerate(self.items):
            md5stats = [self.md5.get_md5stat_for_location(item['name'], loc_key) for loc_key in item['locations']]
            self.items[idx]['md5stats'] = md5stats

        self.filtered = self.get_filtered()
        self.refresh_data_table()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        columns = ["Name", "subs", "md5", "size"]
        # self.table_offset = len(colums)
        for key in self.locations:
            columns.append(self.locations[key]["label"])
        columns.append('status')
        table.add_columns(*columns)
        self.columns = columns
        self.load_data_table()

    def on_unmount(self):
        self.dm.save_cache()

    def move_cursor(self, name, old_cursor):
        table = self.query_one(DataTable)
        idx = next(
            (i for i, d in enumerate(self.filtered) if d.get('name') == name),
            None
        )
        if idx is not None:
            table.move_cursor(row=idx)
        else:
            table.move_cursor(row=old_cursor)

    def action_up(self):
        table = self.query_one(DataTable)
        table.move_cursor(row=max(0, table.cursor_row - 1))

    def action_down(self):
        table = self.query_one(DataTable)
        table.move_cursor(row=min(len(self.filtered)-1, table.cursor_row + 1))

    def action_page_down(self):
        table = self.query_one(DataTable)
        table.move_cursor(row=min(len(self.filtered)-1, table.cursor_row + 20))

    def action_page_up(self):
        table = self.query_one(DataTable)
        table.move_cursor(row=max(0, table.cursor_row - 20))

    def action_rename(self):
        if self.execution_running:
            return
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return


        old_name = self.filtered[table.cursor_row]['name']
        def handle_rename(new_name):
            if new_name and new_name != old_name:
                self.dm.rename_item( old_name, new_name)
                if self.search_query not in new_name.lower():
                    self.search_query = ""
                self.load_data_table()

            self.move_cursor(new_name, None)
        self.push_screen(RenameModal(old_name), handle_rename)

    def action_open(self):
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return

        name = self.filtered[table.cursor_row]['name']
        self.dm.open_directory(name)


    def action_num(self, idx: int) -> None:
        if self.execution_running:
            return
        if idx >= len(self.locations):
            return
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return
        table_idx = table.cursor_row
        entry = self.filtered[table_idx]
        loc_key = list(self.locations)[idx]
        self.am.toggle_availability(loc_key, entry)
        self.refresh_data_table()
        table.move_cursor(row=table_idx)

    def action_md5(self):
        if self.execution_running:
            return
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return
        table_idx = table.cursor_row
        entry = self.filtered[table_idx]
        self.am.toggle_md5_scan(entry)
        self.refresh_data_table()
        table.move_cursor(row=table_idx)


    def update_cell(self, name: str, column_name: str, content: str):
        row = next(
            (i for i, d in enumerate(self.filtered) if d.get('name') == name)
        )
        column = next(
            (i for i, d in enumerate(self.columns) if d == column_name)
        )
        coordinate = Coordinate(row = row, column = column)

        table = self.query_one(DataTable)
        row_key = table.coordinate_to_cell_key(coordinate).row_key
        column_key = table.coordinate_to_cell_key(coordinate).column_key
        table.update_cell(row_key, column_key, content)

        if column_name == 'status':
            try:
                coordinate = Coordinate(row = len(self.filtered), column = 0)
                row_key = table.coordinate_to_cell_key(coordinate).row_key
                table.remove_row(row_key)
            except:
                pass
            dummy_row = ["" for _ in self.columns]
            dummy_row[column] = content
            table.add_row(*dummy_row)

    def action_execute(self):
        if self.execution_running:
            return
        table = self.query_one(DataTable)
        cursor_row = table.cursor_row
        self.execution_running = True
        def update_progress(name :str, content: str):
            def update_cell(name: str, content: str):
                self.update_cell(name, 'status', content)
                self.move_cursor(name, cursor_row)
            self.call_from_thread(update_cell, name, content)
        def finish_progress():
            def finish_progress_callable():
                self.load_data_table()
                self.execution_running = False
                table.move_cursor(row = min(len(self.filtered)-1, cursor_row))
                os.system("cvlc --play-and-exit /home/harmen/Misc/default_alarm.wav")
            self.call_from_thread(finish_progress_callable)
        def execute():
            self.am.execute(self.dm, self.md5, update_progress, finish_progress)
        self.run_worker(execute, exclusive=True, thread=True) 

    def action_update(self):
        self.load_data_table()

    def action_start_search(self) -> None:
        """Show the input and focus it."""
        search_input = self.query_one(Input)
        search_input.add_class("visible")
        search_input.focus()

    def action_close_search(self) -> None:
        """
        Triggered by ESC.
        Hides the input AND clears the value to reset the table.
        """
        search_input = self.query_one(Input)
        search_input.remove_class("visible")
        search_input.value = ""  # <--- This resets the filter
        self.query_one(DataTable).focus()

    def on_input_submitted(self, message: Input.Submitted) -> None:
        """
        Triggered by ENTER.
        Hides the input, but keeps the value (table stays filtered).
        """
        if message.input.id != "search":
            return
        search_input = self.query_one(Input)
        search_input.remove_class("visible")
        # Note: We do NOT clear search_input.value here
        self.query_one(DataTable).focus()


    def on_input_changed(self, message: Input.Changed) -> None:
        """Updates the table contents based on the input value."""
        if message.input.id != "search":
            return
        self.search_query = message.value.lower()
        table = self.query_one(DataTable)
        
        table.clear()
        self.filtered = self.get_filtered()
        
        self.refresh_data_table()
# # Update column 1 (index 1) of that row
# col_key = table.columns[1].key 
# table.update_cell(row_key, col_key, "New Value")


if __name__ == "__main__":
    app = FileListTable()
    app.run()
