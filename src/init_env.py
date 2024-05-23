from enum import Enum, unique
import os
import sys

from dotenv import dotenv_values

# TODO: consider renaming MODEL_REPOSITORY(.*) to MODEL_REPO(.*) across the codebase for brevity and consistency
# TODO: consider using click for the CLI interface

HOME_PATH = os.path.expanduser("~")

OLLAMA_PATH_ENV_VAR = "OLLAMA_PATH"
MODEL_REPOSITORY_PATH_ENV_VAR = "MODEL_REPOSITORY_PATH"

OLLAMA_DIR_NAME = ".ollama"
MODEL_REPOSITORY_DIR_NAME = ".model_repo"

OLLAMA_PATH = os.path.join(HOME_PATH, OLLAMA_DIR_NAME)
MODEL_REPOSITORY_PATH = os.path.join(HOME_PATH, MODEL_REPOSITORY_DIR_NAME)

def escape_dot_env_value(value):
    # dotenv_values() returns all values as strings
    return value.replace("\\", "\\\\")

def write_config_at_path(config, path):
    with open(path, "w") as f:
        for key, value in config.items():
            f.write(f"{key}={escape_dot_env_value(value)}\n")

@unique
class ReuseChoice(Enum):
    REUSE_BOTH_DIRS = 0
    REUSE_MODEL_REPO_DIR = 1
    REUSE_OLLAMA_DIR = 2
    REUSE_NONE = 3

    @classmethod
    def try_prompt(cls, options):
        choice = int(input("Enter the number of the option you want to select: "))
        return options[choice]

    def option_desc(choice):
        assert len(ReuseChoice) == 4, "The implementation of this method assumes that there are exactly 4 enum variants"

        if choice == ReuseChoice.REUSE_BOTH_DIRS:
            return f"Reuse existing {MODEL_REPOSITORY_DIR_NAME} directory at {MODEL_REPOSITORY_PATH} and {OLLAMA_DIR_NAME} directory at {OLLAMA_PATH}"
        elif choice == ReuseChoice.REUSE_MODEL_REPO_DIR:
            return f"Reuse only the existing {MODEL_REPOSITORY_DIR_NAME} directory at {MODEL_REPOSITORY_PATH} for {MODEL_REPOSITORY_PATH_ENV_VAR} .env environment variable"
        elif choice == ReuseChoice.REUSE_OLLAMA_DIR:
            return f"Reuse only existing {OLLAMA_DIR_NAME} directory at {OLLAMA_PATH} for {OLLAMA_PATH_ENV_VAR} .env environment variable"
        # elif choice == ReuseChoice.REUSE_NONE:
        else:
            return "Do not reuse any existing directories"
        
    def to_reuse_tuple(choice):
        assert len(ReuseChoice) == 4, "The implementation of this method assumes that there are exactly 4 enum variants"

        if choice == ReuseChoice.REUSE_BOTH_DIRS:
            reuse_ollama_dir = True
            reuse_model_repo_dir = True
        elif choice == ReuseChoice.REUSE_MODEL_REPO_DIR:
            reuse_ollama_dir = False
            reuse_model_repo_dir = True
        elif choice == ReuseChoice.REUSE_OLLAMA_DIR:
            reuse_ollama_dir = True
            reuse_model_repo_dir = False
        # elif choice == ReuseChoice.REUSE_NONE:
        else:
            reuse_ollama_dir = False
            reuse_model_repo_dir = False
        
        return reuse_ollama_dir, reuse_model_repo_dir
        
    @classmethod
    def options_from_env(cls):
        options = []

        if os.path.exists(MODEL_REPOSITORY_PATH) & os.path.exists(OLLAMA_PATH):
            options.append(cls.REUSE_BOTH_DIRS)

        if os.path.exists(MODEL_REPOSITORY_PATH):
            options.append(cls.REUSE_MODEL_REPO_DIR)

        if os.path.exists(OLLAMA_PATH):
            options.append(cls.REUSE_OLLAMA_DIR)

        options.append(cls.REUSE_NONE)

        return options

def update_config_from_prompts(config):
    options = ReuseChoice.options_from_env()
    choice = ReuseChoice.REUSE_NONE

    if options != [ReuseChoice.REUSE_NONE]:
        print("Select one of the following options:")
        for i, desc in enumerate([ReuseChoice.option_desc(opt) for opt in options]):
            print(f"\t{i}: {desc}")

        # TODO: consider adding the retry logic here
        choice = ReuseChoice.try_prompt(options)

    print()
    
    reuse_ollama, reuse_model_repo = ReuseChoice.to_reuse_tuple(choice)

    if reuse_ollama:
        config[OLLAMA_PATH_ENV_VAR] = OLLAMA_PATH
    else:
        path = input(f"Enter the path where you want to create the {OLLAMA_DIR_NAME} directory. Leave empty to use {OLLAMA_PATH}:\n")
        config[OLLAMA_PATH_ENV_VAR] = path if path else OLLAMA_PATH
    
    if reuse_model_repo:
        config[MODEL_REPOSITORY_PATH_ENV_VAR] = MODEL_REPOSITORY_PATH
    else:
        path = input(f"Enter the path where you want to create the {MODEL_REPOSITORY_DIR_NAME} directory. Leave empty to use {MODEL_REPOSITORY_PATH}:\n")
        config[MODEL_REPOSITORY_PATH_ENV_VAR] = path if path else MODEL_REPOSITORY_PATH
    
if __name__ == "__main__":
    file_path = os.path.realpath(__file__)

    src, _init_py = os.path.split(file_path)

    deployment = os.path.join(src, "deployment")

    dot_env = os.path.join(deployment, ".env")

    if ("--force" not in sys.argv) & os.path.exists(dot_env):
        print(f"Found .env file at `{dot_env}`. Skipping creation.")
        exit()

    example_dot_env = os.path.join(deployment, ".env.example")

    config = dotenv_values(example_dot_env)

    if "--skip-prompts" in sys.argv:
        config[OLLAMA_PATH_ENV_VAR] = OLLAMA_PATH
        config[MODEL_REPOSITORY_PATH_ENV_VAR] = MODEL_REPOSITORY_PATH
        write_config_at_path(config, dot_env)
        exit()

    update_config_from_prompts(config)

    print("Creating an .env file with the following contents:")
    print()
    print('```.env')
    for key, value in config.items():
        print(f"{key}={escape_dot_env_value(value)}")
    print('```')
    print()

    # TODO: consider adding the retry logic here
    if input(f"Do you want to create an .env file at {dot_env} with such contents? (y/n): ") != "y":
        print("Aborted.")
        exit()
    
    write_config_at_path(config, dot_env)
    print(f"Created an .env file at `{dot_env}`")

    
    if "--skip-prompts" in sys.argv:
        os.makedirs(config[MODEL_REPOSITORY_PATH_ENV_VAR], exist_ok=True)
        os.makedirs(config[OLLAMA_PATH_ENV_VAR], exist_ok=True)
        exit()

    if (not os.path.exists(config[OLLAMA_PATH_ENV_VAR])) & input(f"Do you want to create the {config[OLLAMA_PATH_ENV_VAR]} directory?") == "y":
        os.makedirs(config[OLLAMA_PATH_ENV_VAR])
        print(f"Created the {config[OLLAMA_PATH_ENV_VAR]} directory")

    if (not os.path.exists(config[MODEL_REPOSITORY_PATH_ENV_VAR])) & input(f"Do you want to create the {config[MODEL_REPOSITORY_PATH_ENV_VAR]} directory?") == "y":
        os.makedirs(config[MODEL_REPOSITORY_PATH_ENV_VAR])
        print(f"Created the {config[MODEL_REPOSITORY_PATH_ENV_VAR]} directory")

