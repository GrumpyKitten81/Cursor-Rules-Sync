"""
This script propagates changes from main to all feature branches.
Merging main was intentionally not chosen to have more control.
"""

import os
import subprocess

# --- CONFIGURATION ---

FILES_TO_UPDATE = [
    # These files are updated only if they exist in the branch
    "rules/general.mdc",
]

FILES_TO_FORCE_UPDATE = [
    ".gitattributes",
]  # These files are always updated unconditionally

SKIP_BRANCHES = ["main"]  # Ignore these branches, e.g., 'main', 'master', etc.

# --- HELPER FUNCTIONS ---


def run_cmd(cmd, check=True, allow_fail=False):
    """
    Executes a shell command using subprocess and handles errors gracefully.
    If allow_fail is True, the function will not raise an exception on failure.
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error executing: {' '.join(cmd)}")
        print("stdout:", e.stdout)
        print("stderr:", e.stderr)
        if not allow_fail:
            raise
        return e  # Return the exception object for further inspection


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

        # 4) Get files from 'main' (conditional update)
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

        # 5) Get files from 'main' (unconditional update)
        for file_path in FILES_TO_FORCE_UPDATE:
            print(
                f"-> Forcing update of {file_path} from main in branch '{local_branch}'"
            )
            # Overwrite local file with the state from main
            run_cmd(["git", "checkout", "main", "--", file_path], check=True)
            changes_made = True  # Always mark changes as made for forced updates

        # 6) Commit & Push if changes were made
        if changes_made:
            print(f"-> Committing and pushing changes in branch '{local_branch}' ...")
            commit_result = run_cmd(
                ["git", "commit", "-am", "Propagate changes from main"], allow_fail=True
            )
            if commit_result.returncode != 0:
                print(
                    f"-> Commit failed in branch '{local_branch}'. Skipping push. Details:"
                )
                print(commit_result.stderr)
                continue  # Skip pushing and move to the next branch

            push_result = run_cmd(["git", "push"], allow_fail=True)
            if push_result.returncode != 0:
                print(f"-> Push failed in branch '{local_branch}'. Details:")
                print(push_result.stderr)
                continue
        else:
            print(f"-> No changes in branch '{local_branch}'.")

        # Switch back to main to cleanly switch to the next branch
        run_cmd(["git", "checkout", "main"])

    print("\nDone! All relevant branches have been updated.")


if __name__ == "__main__":
    main()
