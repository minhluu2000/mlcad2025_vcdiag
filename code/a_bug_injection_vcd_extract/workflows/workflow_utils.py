import os, shutil, subprocess, time
from pathlib import Path
from collections import Counter
from dataclasses import dataclass

@dataclass
class ROI:
    id: str
    start_line: int
    end_line: int

    def includes(self, line_idx: int) -> bool:
        return line_idx >= self.start_line and line_idx <= self.end_line

    def length(self) -> int:
        return self.end_line - self.start_line + 1


def find_full_path(root_path: str, filename: str, keywords: list = []) -> str:
    design_walk = os.walk(root_path)
    for root, _, files in design_walk:
        if filename in files:
            path = f"{root}/{filename}"
            if any(keyword in path for keyword in keywords) or len(keywords) == 0:
                return path
    return ""


def combine_ranges(ranges_list: list):
    ranges = []
    # for 1-3, make it to [1, 2, 3]
    for range_ in ranges_list:
        if range_.find("-") != -1:
            start, end = map(int, range_.split("-"))
            ranges.extend(list(range(start, end + 1)))
        else:
            ranges.append(int(range_))

    return ranges


def diff_files(file1: str, file2: str):
    """Return the diff result of two files.

    Args:
        file1 (str): file path 1
        file2 (str): file path 2

    Returns:
        str: diff result (0 if the files are the same, 1 otherwise)
    """
    # check if both source and target files exist
    if not os.path.isfile(file1):
        print(f"Source file {file1} does not exist")
        return 
    if not os.path.isfile(file2):
        print(f"Target file {file2} does not exist")
        return 1
    try:
        result = os.system(f"diff -w {file1} {file2}")
    except Exception as e:
        print(f"Failed to diff {file1} and {file2} due to {e}")
        return 1
    return result


def diff_folders(folder1: str, folder2: str):
    """Return the diff result of two folders.

    Args:
        folder1 (str): folder path 1
        folder2 (str): folder path 2

    Returns:
        str: diff result (0 if the folders are the same, 1 otherwise)
    """
    # check if both source and target folders exist
    if not os.path.isdir(folder1):
        print(f"Source folder {folder1} does not exist")
        return 1
    if not os.path.isdir(folder2):
        print(f"Target folder {folder2} does not exist")
        return 1
    try:
        result = os.system(f"diff -qr -w {folder1} {folder2}")
    except Exception as e:
        print(f"Failed to diff {folder1} and {folder2} due to {e}")
        return 1
    return result


def copy_file(source_file: str, target_file: str):
    """Replace the target file with the source file.

    Args:
        source_file (str): source file path
        target_file (str): target file path
    """
    # check if source file exists
    if not os.path.isfile(source_file):
        print(f"Source file {source_file} does not exist")
        return 1
    try:
        os.system(f"cp -rf {source_file} {target_file}")
    except Exception as e:
        print(f"Failed to copy file {source_file} to file {target_file} due to {e}")
    # return diff result to check if the file is Copied successfully
    result = diff_files(source_file, target_file)
    if result != 0:
        print(f"Failed to copy file {target_file} to file {source_file}")
        return 1
    else:
        print(f"Successfully copied file {source_file} to file {target_file}")
        return 0


def copy_folder(source_folder: str, target_folder: str):
    # check to make sure source folder exists
    if not os.path.isdir(source_folder):
        print(f"Source folder {source_folder} does not exist")
        return 1
    # copy the source folder to the target folder
    try:
        os.system(f"cp -rf {source_folder}/* {target_folder}")
    except Exception as e:
        print(f"Failed to copy folder {source_folder} to folder {target_folder} due to {e}")
        return 1

    # return diff result to check if the folder is Copied successfully
    result = diff_folders(source_folder, target_folder)
    if result != 0:
        print(f"Failed to copy folder {source_folder} to folder {target_folder}")
        return 1
    else:
        print(f"Successfully copied folder {source_folder} to folder {target_folder}")
        return 0


def check_config_overlaps(configs: list, config_name: str) -> tuple:
    """Check if there are overlaps in config ranges.

    Args:
        configs (list): list of configs

    Returns:
        bool: True if there are overlaps, False otherwise
    """
    ranges = []
    for config in configs:
        ranges_list = config[config_name]
        ranges.extend(combine_ranges(ranges_list))
    if len(ranges) != len(set(ranges)):
        return (True, [k for k, v in Counter(ranges).items() if v > 1])
    return (False, [])

def create_workspace(designs_path, design_name, index):
    """Helper function to create a single workspace"""
    workspace_path = f"{designs_path}/{design_name}_{index + 1}"
    try:
        os.system(f"cp -r {designs_path}/{design_name} {workspace_path}")
        assert os.path.exists(workspace_path), f"Failed to create workspace {workspace_path}"
        print(f"Workspace {workspace_path} is created successfully")
    except Exception as e:
        print(f"Failed to create workspace {workspace_path}: {e}")

def clean_design_env(root_path, design_name):
    """
    This function deletes the existing workspaces for the target 
    design.

    Args:
        root_path (str): root path of the project
        design_name (str): name of the design
    """
    
    designs_path = f"{root_path}/designs"

    try:
        print(f"Deleting existing workspaces for {design_name}")
        os.system(f"rm -rf {designs_path}/{design_name}_*")
    except Exception as e:
        print(f"Failed to delete existing workspaces: {e}")
        exit(1)

def force_delete_busy_files(target_path: str):
    """
    Kills processes using files inside the target directory, then deletes all contents inside it.
    
    Args:
        target_path (str): The directory whose contents should be deleted.
    """
    if not target_path:
        raise ValueError("Target path must be provided.")
    if not os.path.isdir(target_path):
        raise ValueError(f"The path '{target_path}' is not a valid directory.")

    abs_target_path = os.path.abspath(target_path)
    print(f"Cleaning contents inside: {abs_target_path}")

    # Find and kill processes using any files in the directory
    try:
        print(f"Finding processes using: {abs_target_path}")
        result = subprocess.run(
            ["fuser", "-c", abs_target_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        pids = result.stdout.strip().split()
        if pids:
            print(f"Killing processes: {' '.join(pids)}")
            subprocess.run(["kill", "-9", *pids])
            time.sleep(1)
        else:
            print("No processes are using files in the directory.")
    except Exception as e:
        print(f"Warning: Failed to check or kill processes. {e}")

    # Delete all contents inside the target directory
    try:
        for entry in os.listdir(abs_target_path):
            entry_path = os.path.join(abs_target_path, entry)
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path)
            else:
                os.remove(entry_path)
            print(f"Deleted: {entry_path}")
        print(f"All contents in '{abs_target_path}' have been deleted.")
    except Exception as e:
        print(f"Error while deleting files: {e}")

def get_next_available_path(base_path):
    base_path = Path(base_path)
    base_stem = base_path.stem
    suffix = 1

    base_path.parent.mkdir(parents=True, exist_ok=True)

    while True:
        candidate = base_path.with_name(f"{base_stem}_{suffix:02d}{base_path.suffix}")
        if not candidate.exists():
            return str(candidate)
        suffix += 1