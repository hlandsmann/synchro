#!/usr/bin/env python3
import subprocess
import os
import shutil
from collections.abc import Callable
from datamanager import DataManager
from checksum import Md5Sum
from textual.worker import get_current_worker
from time import sleep
from pathlib import Path


class ActionManager:
    def __init__(self, locations):
        self.locations = locations
        self.cache = {}

    def toggle_availability(self, loc_key : str, entry: dict) -> None:
        name = entry['name']
        new_entry = {}
        if name in self.cache:
            new_entry = self.cache[name]
        else:
            new_entry = {
                    'name' : name,
                    'is_dir' : entry['is_dir'],
                    'locations' : entry['locations'],
                    'action' : dict((key, "") for key in self.locations)
                    }
        action = new_entry['action']
        if action[loc_key] == "":
            action[loc_key] = "n" if loc_key in new_entry['locations'] else "y"
        else:
            action[loc_key] = ""
        new_entry['action'] = action
        self.cache[name] = new_entry

    def toggle_md5_scan(self, entry: dict):
        name = entry['name']
        new_entry = {}
        if name in self.cache:
            new_entry = self.cache[name]
        else:
            new_entry = {
                    'name' : name,
                    'is_dir' : entry['is_dir'],
                    'locations' : entry['locations'],
                    'action' : dict((key, "") for key in self.locations)
                    }
        actions = new_entry['action']
        if all(actions[key] == "md5" for key in new_entry['locations']):
            actions = dict((key, "") for key in self.locations)
        else:
            actions = dict((key, "md5") for key in self.locations)
        new_entry['action'] = actions

        self.cache[name] = new_entry


    def get_action(self, name: str):
        if name in self.cache:
            return self.cache[name]['action']
        return dict((key, "") for key in self.locations)

    def move_to_delete(self, loc_key:str, name: str):
        path = self.locations[loc_key]['path']
        dst_path_toDelete = os.path.join(path, "00_toDelete")
        Path(dst_path_toDelete).mkdir(exist_ok=True)

        src_path = os.path.join(path, name)
        shutil.move(src_path, dst_path_toDelete)


    def copy_with_rsync(self, src:str, dst: str, update_progress: Callable) -> None:
        """Background worker running rsync."""
        worker = get_current_worker()

        cmd = [
            "rsync",
            "-a",
            "--out-format=%n",  # one line per transferred file
            src,
            dst,
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        assert process.stdout is not None

        for line in process.stdout:
            if worker.is_cancelled:
                process.terminate()
                return

            filename = line.strip()
            if not filename:
                continue

            # A file was copied → update counter
            # self.filename = filename
            update_progress(os.path.basename(filename))

        process.wait()

    def execute(self, dm: DataManager, md5: Md5Sum, update_progress: Callable, finish_progress: Callable):
        for name in self.cache:
            def update_progress_name(filename):
                update_progress(name, filename)
            items = dm.get_merged_view()
            idx = next(i for i, d in enumerate(items) if d.get('name') == name)
            entry = items[idx]
            src_loc_key = entry['locations'][0]
            actions = self.cache[name]['action']
            src_path = self.locations[src_loc_key]['path']
            src = os.path.join(src_path, name)
            for dst_loc_key in actions:
                action = actions[dst_loc_key]
                dst_path = self.locations[dst_loc_key]['path']
                if action == "y":
                    self.copy_with_rsync(src, dst_path, update_progress_name)
            for loc_key in actions:
                action = actions[loc_key]
                if action == "n":
                    update_progress_name(f"{loc_key} -> toDelete")
                    self.move_to_delete(loc_key, name)
            if all(actions[key] == "md5" for key in actions):
                md5.run_md5_check(entry, update_progress_name)
        self.cache = {}
        finish_progress()


