"""
This script propagates changes from main to all feature branches.
Merging main was intentionally not chosen to have more control.
"""

import os
import subprocess

# --- CONFIGURATION ---

FILES_TO_UPDATE = [
    "README.md",
    "rules/general.mdc",
]

SKIP_BRANCHES = ["main"]  # Ignore these branches, e.g., 'main', 'master', etc.

# --- HELPER FUNCTIONS ---


def run_cmd(cmd, check=True):
    """
    Executes a shell command using subprocess and
    prints stdout + stderr if check=True and the command fails.
    """
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    if check and result.returncode != 0:
        print(f"Error executing: {' '.join(cmd)}")
        print("stdout:", result.stdout)
        print("stderr:", result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def get_remote_branches(skip_branches):
    """
    Retrieves all remote branches and filters them by skip_branches.
    Returns a list of branch names (without the "origin/" prefix).
    """
    # Fetch git info for comparison
    run_cmd(["git", "fetch", "--all"])

    # Retrieve all remote branches
    result = run_cmd(["git", "branch", "-r"], check=True)
    lines = result.stdout.splitlines()

    remote_branches = []
    for line in lines:
        line = line.strip()
        if "->" in line:
            # Ignore "origin/HEAD -> origin/main" etc.
            continue

        if line.startswith("origin/"):
            branch_name = line.replace("origin/", "")
            if branch_name not in skip_branches:
                remote_branches.append(branch_name)

    return remote_branches


def local_branch_exists(branch_name):
    """
    Checks if a local branch with the given name exists.
    """
    result = run_cmd(["git", "branch", "--list", branch_name], check=False)
    return bool(result.stdout.strip())


# --- MAIN FUNCTION ---


def main():
    """
    Main function to propagate changes from main to all feature branches.
    """
    # 1) Switch to 'main' (locally) to have a consistent base
    run_cmd(["git", "checkout", "main"])
    # Optional: Update 'main'
    # run_cmd(["git", "pull", "--rebase"])

    # 2) Retrieve remote branches
    config_branches = get_remote_branches(SKIP_BRANCHES)
    print(f"Retrieved remote branches (filtered): {config_branches}")

    # 3) Iterate through all relevant branches
    for branch in config_branches:
        local_branch = branch

        # Does this branch already exist locally? If not, create it
        if not local_branch_exists(local_branch):
            print(f"Local branch '{local_branch}' does not exist – creating ...")
            run_cmd(["git", "checkout", "-b", local_branch, f"origin/{branch}"])
        else:
            print(f"Local branch '{local_branch}' already exists. Switching to it ...")
            run_cmd(["git", "checkout", local_branch])

        changes_made = False

        # 4) Get files from 'main' (if they exist in the branch at all)
        for file_path in FILES_TO_UPDATE:
            if os.path.exists(file_path):
                print(f"-> Updating {file_path} from main in branch '{local_branch}'")
                # Overwrite local file with the state from main
                run_cmd(["git", "checkout", "main", "--", file_path], check=True)

                # **IMPORTANT**: Compare against HEAD to detect *all* changes (staged or unstaged)
                diff_result = run_cmd(
                    ["git", "diff", "HEAD", "--name-only", file_path], check=False
                )
                if diff_result.stdout.strip():
                    changes_made = True
            else:
                print(
                    f"-> {file_path} does not exist in branch '{local_branch}', skipping."
                )

        # 5) Commit & Push if changes were made
        if changes_made:
            print(f"-> Committing and pushing changes in branch '{local_branch}' ...")
            run_cmd(["git", "commit", "-am", "Propagate changes from main"])
            run_cmd(["git", "push"])
        else:
            print(f"-> No changes in branch '{local_branch}'.")

        # Switch back to main to cleanly switch to the next branch
        run_cmd(["git", "checkout", "main"])

    print("\nDone! All relevant branches have been updated.")


if __name__ == "__main__":
    main()
