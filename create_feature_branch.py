"""
This script creates a new feature branch, sanitizes its name, and removes specified paths.
"""

import sys
import subprocess
import re
import os

# 1) Define a list of paths that should NOT be part of the feature branch.
#    These will be removed (git rm) in the new branch.
EXCLUDED_PATHS = [
    ".vscode",
    "create_feature_branch.py",
    "update.py",
    "test_scripts.py",
    "todo.txt",
]


def run_cmd(cmd, check=True):
    """
    Run a command in a subprocess. If 'check' is True, raise an exception on non-zero return code.
    Returns the completed process object, including stdout/stderr.
    """
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    if check and result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}")
        print("stdout:", result.stdout)
        print("stderr:", result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def is_git_installed():
    """
    Check if Git is installed by running 'git --version'.
    Returns True if successful, else False.
    """
    try:
        run_cmd(["git", "--version"], check=True)
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False


def can_commit():
    """
    Minimal check to see if user config for Git is set (user.name/user.email).
    If not set, commits will often fail or produce warnings.
    This is a simple heuristic; adapt as needed for your environment.
    """
    try:
        user_name = run_cmd(["git", "config", "user.name"], check=False).stdout.strip()
        user_email = run_cmd(
            ["git", "config", "user.email"], check=False
        ).stdout.strip()
        if not user_name or not user_email:
            return False
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False


def sanitize_branch_name(branch_name):
    """
    Sanitize the branch name to meet basic Git branch naming rules.
    For simplicity:
      - Replace spaces with '-'
      - Remove invalid chars like ? [ ] ~ ^ : etc.
      - Remove leading or trailing slashes
      - Avoid consecutive slashes
    This is a basic approach; real-world usage might need more robust checks.
    """
    # Replace whitespace with dashes
    clean = re.sub(r"\s+", "-", branch_name.strip())

    # Remove newline characters
    clean = clean.replace("\n", "")

    # Remove characters that are problematic in branch names:
    # e.g., ~ ^ : ? * [ ] \ etc.
    if re.search(r"[~^:\?\*\[\]\\]+", clean):
        raise ValueError(f"Branch name '{branch_name}' contains invalid characters.")

    # Remove repeated slashes
    clean = re.sub(r"/+", "/", clean)

    # Remove leading or trailing slash
    clean = clean.strip("/")

    # If the branch name contains slashes or backslashes, use the last path component
    if "/" in clean or "\\" in clean:
        clean = os.path.basename(clean)

    return clean


def main():
    """
    Main function to create a new feature branch, sanitize its name, and remove specified paths.
    """
    # 1) Check if Git is installed
    if not is_git_installed():
        print("Git does not appear to be installed or is not in PATH. Exiting.")
        sys.exit(1)

    # 2) Check if we can commit
    if not can_commit():
        print(
            "Git user.name or user.email not set. Please configure Git before committing."
        )
        print("Example:")
        print("  git config --global user.name 'Your Name'")
        print("  git config --global user.email 'you@example.com'")
        sys.exit(1)

    # 3) Read the feature branch name from command line arguments
    if len(sys.argv) < 2:
        print("Please provide a feature branch name as an argument.")
        print(f"Usage: python {sys.argv[0]} '<feature_branch_name>'")
        sys.exit(1)

    original_branch_name = sys.argv[1]
    try:
        sanitized_name = sanitize_branch_name(original_branch_name)
    except ValueError as e:
        print(e)
        sys.exit(1)

    # If the sanitized branch name differs from the original, ask user for confirmation
    if sanitized_name != original_branch_name:
        print(
            f"Branch name '{original_branch_name}' was sanitized to '{sanitized_name}'."
        )
        answer = (
            input("Do you want to continue with the sanitized branch name? [y/N]: ")
            .strip()
            .lower()
        )
        if answer not in ["y", "yes"]:
            print("Aborted by user.")
            sys.exit(0)

    # 4) Perform the Git steps
    try:
        # git checkout -b <feature_branch>
        print(f"Creating and switching to branch '{sanitized_name}' ...")
        run_cmd(["git", "checkout", "-b", sanitized_name])

        # git mv main <feature_branch>
        print(f"Renaming file 'main' to '{sanitized_name}' (git mv) ...")
        run_cmd(["git", "mv", "main", sanitized_name])

        # Remove undesired files/directories from the new branch
        for path in EXCLUDED_PATHS:
            if os.path.exists(path):
                print(f"Removing '{path}' from the new branch...")
                if os.path.isdir(path):
                    # Remove directories with 'git rm -r'
                    run_cmd(["git", "rm", "-r", path], check=False)
                else:
                    # Remove files with 'git rm'
                    run_cmd(["git", "rm", path], check=False)
            else:
                print(f"Skipping '{path}' (not found).")

        # git add <feature_branch> – technically we do 'git commit -a' below,
        # but let's mimic your steps anyway:
        print(f"Adding '{sanitized_name}'...")
        run_cmd(["git", "add", sanitized_name])

        # git commit -a -m "init branch"
        print("Committing changes with message 'init branch' ...")
        run_cmd(["git", "commit", "-a", "-m", "init branch"])

        # git push --set-upstream origin <feature_branch>
        print(f"Pushing to remote branch 'origin/{sanitized_name}' ...")
        run_cmd(["git", "push", "--set-upstream", "origin", sanitized_name])

        print("\nAll done. Branch creation and push completed successfully!")
    except subprocess.CalledProcessError:
        print(
            "\nAn error occurred during Git operations. Please check the messages above."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
