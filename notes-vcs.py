import os
import fnmatch
import pathlib

def load_gitignore(gitignore_path):
    ignore_patterns = []
    with open(gitignore_path, 'r') as f:
        for line in f.readlines():
            line = line.strip()
            if line and not line.startswith('#'):
                ignore_patterns.append(line)
    return ignore_patterns

def should_ignore(path, ignore_patterns, is_dir):
    for pattern in ignore_patterns:
        if pattern.startswith('/'):
            # Remove leading '/' to indicate it's based on the directory where .gitignore resides
            pattern = pattern[1:]
            local_path = os.path.relpath(path, start_dir)
            if fnmatch.fnmatch(local_path, pattern):
                return True
        elif pattern.startswith('!'):
            # Remove leading '!' indicating an exception to a previous pattern
            pattern = pattern[1:]
            if fnmatch.fnmatch(path, pattern):
                return False
        else:
            if fnmatch.fnmatch(path, pattern):
                return True

            # If it's a directory, we need to consider the case where the directory itself is ignored
            # E.g., pattern = "dir_to_ignore/*"
            if is_dir and fnmatch.fnmatch(path + "/", pattern):
                return True
    return False

def find_files_with_extensions(target_extensions, start_dir='.'):
    matching_files = []
    
    gitignore_path = os.path.join(start_dir, '.gitignore')
    ignore_patterns = []
    
    if os.path.exists(gitignore_path):
        ignore_patterns = load_gitignore(gitignore_path)

    for root, dirs, files in os.walk(start_dir):
        # Modify dirs in place to remove ignored directories (affects os.walk behavior)
        dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), ignore_patterns, True)]

        for filename in files:
            if any(filename.endswith(ext) for ext in target_extensions):
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, start_dir)
                
                if should_ignore(relative_path, ignore_patterns, False):
                    continue
                
                matching_files.append(full_path)

    return matching_files

# Define target file extensions
target_extensions = ['.txt', '.md']

# Find and print matching files
note_files = find_files_with_extensions(target_extensions)

def create_files(file_names, directory='.'):
    """
    Create files in a given directory if they do not already exist.

    Parameters:
        file_names (list): List of file names to create.
        directory (str): The directory where the files will be created. Default is the current directory.
    """
    # Ensure the directory exists
    dir_path = pathlib.Path(directory)
    dir_path.mkdir(parents=True, exist_ok=True)

    print(f"Creating files in directory: {dir_path.resolve()}")

    for file_name in file_names:
        file_path = dir_path / file_name  # Using pathlib to form the path

        print(f"Checking file: {file_path.resolve()}")

        # Only create the file if it does not already exist
        if not file_path.exists():
            print(f"Creating file: {file_path.resolve()}")
            with open(file_path, 'w') as f:
                pass  # File is created and closed immediately, remaining empty
        else:
            print(f"File already exists: {file_path.resolve()}")
            
# Directory where files will be created
directory = './Bridge Notes'

# Create the files
create_files(note_files, directory)
