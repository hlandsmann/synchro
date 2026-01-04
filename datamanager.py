#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

def is_mounted(dir_path):
    try:
        return len(os.listdir(dir_path)) != 0
    except:
        return False

def format_size(bytes_size: float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f}{unit}" if bytes_size < 10 else f"{bytes_size:.0f}{unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f}PB"

def get_dir_size(path: Path) -> int:
    total = 0
    if path.is_file():
        return path.stat().st_size
    try:
        for entry in path.iterdir():
            if entry.is_symlink():
                continue
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry)
    except (PermissionError, OSError):
        pass
    return total

def get_dir_size_str(path) -> str:
    return format_size(get_dir_size(Path(path)))

class DataManager:
    def __init__(self, locations):
        self.locations = locations
        self.cache = {}
        self.online_status = {}


    def scan_location(self, loc_key):
        location_path = self.locations[loc_key]["path"]
        if not is_mounted(location_path):
            self.online_status[loc_key] = False 
            return
        self.online_status[loc_key] = True 

        items = []
        try:
            with os.scandir(location_path) as it:
                for entry in it:
                    items.append({
                        "name": entry.name,
                        "is_dir": entry.is_dir(),
                        "size": get_dir_size_str(os.path.join(location_path, entry.name)),
                        "subs": os.path.exists(os.path.join(location_path, entry.name, "subs"))
                    })
        except PermissionError:
            pass
        self.cache[loc_key] = items

    def get_dir_size_str(self, item):
        loc_key = item['locations'][0]
        location_path = self.locations[loc_key]["path"]
        name = item['name']
        return get_dir_size_str(os.path.join(location_path, name))

    def get_merged_view(self):
        """
        Returns a sorted list of unique items in this directory across all locations.
        """
        for key in self.locations:
            self.scan_location(key)

        merged = {} 

        for key in self.locations:
            items = self.cache.get(key, [])

            for item in items:
                name = item['name']
                if name not in merged:
                    merged[name] = {
                        "name": name, 
                        "is_dir": item['is_dir'],
                        "size": item['size'],
                        "locations": [],
                        "subs" : []
                    }
                merged[name]["locations"].append(key)
                merged[name]["subs"].append(item['subs'])

        result_list = list(merged.values())
        result_list.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return result_list

    def get_location(self, name):
        for key in self.locations:
            loc_cache = self.cache.get(key, {})
            exists_in_cache = any(x['name'] == name for x in loc_cache)

            if exists_in_cache:
                base = self.locations[key]["path"]
                full_path = os.path.join(base, name)
                if os.path.exists(full_path):
                    yield key

    def rename_item(self, old_name, new_name):
        for key in self.locations:
            loc_cache = self.cache.get(key, {})
            exists_in_cache = any(x['name'] == old_name for x in loc_cache)

            if exists_in_cache:
                base = self.locations[key]["path"]
                old_full = os.path.join(base, old_name)
                new_full = os.path.join(base, new_name)
                if os.path.exists(old_full):
                    os.rename(old_full, new_full)

    def open_directory(self, name):
        for key in self.get_location(name):
            base = self.locations[key]['path']
            full_path = os.path.join(base, name)
            subprocess.Popen(['xdg-open', full_path])
