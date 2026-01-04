#!/usr/bin/env python3
import os
import subprocess
import shutil
import sys
from enum import Enum
from collections.abc import Callable
from pathlib import Path

def get_md5_subprocess(filepath):
    """
    Calculates MD5 using the system md5sum command via subprocess.
    """
    try:
        result = subprocess.run(
            ['md5sum', filepath],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.split()[0]
    except subprocess.CalledProcessError as e:
        print(f"Error calculating md5 for {filepath}: {e}")
        return None
    except FileNotFoundError:
        print("Error: 'md5sum' command not found. Please check PATH.")
        sys.exit(1)

def parse_checksum_file(checksum_path):
    """
    Reads a checksum file and returns a dict: {filename: hash}
    """
    checksums = {}
    if os.path.exists(checksum_path):
        with open(checksum_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    hash_val = parts[0]
                    filename = ' '.join(parts[1:])
                    # Remove binary/text indicators
                    if filename.startswith('*') or filename.startswith(' '):
                        filename = filename.lstrip('* ')
                    checksums[filename] = hash_val
    return checksums

def write_checksum_file(checksum_path, data):
    """
    Writes the dictionary {filename: hash} to the checksum file.
    """
    with open(checksum_path, 'w') as f:
        # Sort keys for consistent output
        for filename in sorted(data.keys()):
            f.write(f"{data[filename]}  {filename}\n")

def run_md5_check(root_dir, update_progress: Callable):
    global_errors = []
    global_deleted = []
    
    # Files to ignore (metadata files)
    ignored_files = {'checksum.md5', 'error.md5', 'deleted.md5'}
    
    error_file_path = os.path.join(root_dir, 'error.md5')
    deleted_file_path = os.path.join(root_dir, 'deleted.md5')

    # clean up old reports
    if os.path.exists(error_file_path): os.remove(error_file_path)
    if os.path.exists(deleted_file_path): os.remove(deleted_file_path)

    for current_dir, dirs, files in os.walk(root_dir):
        checksum_file = os.path.join(current_dir, 'checksum.md5')
        
        existing_checksums = parse_checksum_file(checksum_file)
        new_checksums = existing_checksums.copy()
        is_modified = False
        
        # Filter on-disk files
        valid_files_on_disk = [f for f in files if f not in ignored_files]
        valid_files_set = set(valid_files_on_disk)

        # --- 1. Check for DELETIONS ---
        # If it's in the checksum file but not on disk
        for tracked_file in list(existing_checksums.keys()):
            if tracked_file not in valid_files_set:
                old_hash = existing_checksums[tracked_file]
                
                # Log to global deleted.md5
                # Path relative to root for the report
                full_path_missing = os.path.join(current_dir, tracked_file)
                rel_path = os.path.relpath(full_path_missing, root_dir)
                
                global_deleted.append(f"{old_hash} {rel_path}")
                print(f"[DELETED] {rel_path}")
                
                # Remove from local dictionary
                del new_checksums[tracked_file]
                is_modified = True

        # --- 2. Check for VERIFICATION and ADDITIONS ---
        for filename in valid_files_on_disk:
            file_path = os.path.join(current_dir, filename)
            
            if filename in existing_checksums:
                # VERIFY
                expected_hash = existing_checksums[filename]
                update_progress(os.path.basename(filename))
                actual_hash = get_md5_subprocess(file_path)
                
                if actual_hash != expected_hash:
                    rel_path = os.path.relpath(file_path, root_dir)
                    global_errors.append(f"{expected_hash} {rel_path}")
                    print(f"[FAIL]    {rel_path}")
            else:
                # ADD
                print(f"[NEW]     {os.path.join(current_dir, filename)}")
                update_progress(os.path.basename(filename))
                actual_hash = get_md5_subprocess(file_path)
                if actual_hash:
                    new_checksums[filename] = actual_hash
                    is_modified = True

        # Save changes if files were added or deleted
        if is_modified:
            write_checksum_file(checksum_file, new_checksums)

    # Write global reports
    if global_errors:
        with open(error_file_path, 'w') as f:
            for line in global_errors:
                f.write(line + "\n")
        print(f"\nErrors detected. See: {error_file_path}")

    if global_deleted:
        with open(deleted_file_path, 'w') as f:
            for line in global_deleted:
                f.write(line + "\n")
        print(f"Deletions detected. See: {deleted_file_path}")
    
    if not global_errors and not global_deleted:
        print("\nSuccess. All files verified and synchronized.")

def get_relative_structure(root_dir: str) -> set[str]:
    """
    Returns a set of relative paths representing the directory structure.
    Directories are included with a trailing '/', files without.
    The root directory itself is not included.
    Empty subdirectories are properly detected and included.
    """
    structure = set()
    root = Path(root_dir).resolve()
    
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir != '.':
            structure.add(rel_dir.replace('\\', '/') + '/')
        
        for filename in filenames:
            rel_file = os.path.join(rel_dir, filename) if rel_dir != '.' else filename
            structure.add(rel_file.replace('\\', '/'))
    
    return structure

class Md5Stat(Enum):
    OK=1
    Incomplete=2
    FilesDiffer=3
    Error=4

class Md5Sum:
    ignored_files = {'checksum.md5', 'error.md5', 'deleted.md5'}

    def __init__(self, locations):
        self.locations = locations


    def get_md5stat_for_location(self, name : str, loc_key : str) -> Md5Stat:
        location = self.locations[loc_key]['path']
        root_dir = os.path.join(location, name)
        error_file = os.path.join(root_dir, 'error.md5')
        diff_file = os.path.join(root_dir, "00_diff.chk")

        if os.path.exists(error_file):
            return Md5Stat.Error
        if os.path.exists(diff_file):
            return Md5Stat.FilesDiffer

        for current_dir, dirs, files in os.walk(root_dir):
            checksum_file = os.path.join(current_dir, 'checksum.md5')
            valid_files_on_disk = [f for f in files if f not in self.ignored_files]
            if valid_files_on_disk and not os.path.exists(checksum_file):
                return Md5Stat.Incomplete


        return Md5Stat.OK

    def cp_checksums(self, name, src_loc_key, dst_loc_key):
        src_location = self.locations[src_loc_key]['path']
        dst_location = self.locations[dst_loc_key]['path']
        src_path = os.path.join(src_location, name)
        dst_path = os.path.join(dst_location, name)
        for current_dir, dirs, files in os.walk(src_path):
            checksum_file = os.path.join(current_dir, 'checksum.md5')
            valid_files_on_disk = [f for f in files if f not in self.ignored_files]
            if valid_files_on_disk and not os.path.exists(checksum_file):
                continue
            rel_checksum_file = os.path.relpath(checksum_file, src_path)
            dst_checksum_file = os.path.join(dst_path, rel_checksum_file)
            try:
                shutil.copy(checksum_file, dst_checksum_file)
            except:
                pass

    def check_dir_diff(self, name, src_loc_key, dst_loc_key):
        src_location = self.locations[src_loc_key]['path']
        dst_location = self.locations[dst_loc_key]['path']
        src_path = os.path.join(src_location, name)
        dst_path = os.path.join(dst_location, name)

        struct_src = get_relative_structure(src_path)
        struct_dst = get_relative_structure(dst_path)
        added = struct_dst - struct_src
        deleted = struct_src - struct_dst
        if not added and not deleted:
            return
        diff_file = os.path.join(dst_path, "00_diff.chk")
        with open(diff_file, "w", encoding="utf-8") as f:
            for path in sorted(added):
                f.write(f"added {path}\n")
            for path in sorted(deleted):
                f.write(f"deleted {path}\n")


    def run_md5_check(self, item: dict, update_progress: Callable):
        name = item['name']
        loc_key = item['locations'][0]
        src_location = self.locations[loc_key]['path']
        src = os.path.join(src_location, name)
        run_md5_check(src, update_progress)
        for dst_loc_key in item['locations'][1:]:
            self.cp_checksums(name, loc_key, dst_loc_key)
            self.check_dir_diff(name, loc_key, dst_loc_key)
            dst_location = self.locations[dst_loc_key]['path']
            dst = os.path.join(dst_location, name)
            run_md5_check(dst, update_progress)



