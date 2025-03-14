import os
import subprocess
import tempfile
import shutil
import pytest
from pathlib import Path


@pytest.fixture(scope="module")
def setup_test_repos():
    """
    1) Clones the main repository (R1) to a temp folder (R2).
    2) Clones R2 again to a second temp folder (R3).
    3) Yields (r2_path, r3_path) to the test functions.
    4) After tests, retains temp dirs for evaluation.
    """
    # Current directory is R1 (the main repo). We'll treat this as the "source of truth".
    r1_path = Path(os.getcwd()).resolve()

    # Define base directory for temporary repositories
    base_temp_dir = Path("b:/").resolve()
    # if linux is used, use /tmp/
    if os.name == "posix":
        base_temp_dir = Path("/tmp/").resolve()

    # 1) Create R2 (a clone of R1)
    temp_dir_r2 = tempfile.mkdtemp(prefix="repo_r2_", dir=base_temp_dir)
    r2_path = Path(temp_dir_r2) / "clone_r2"
    subprocess.run(["git", "clone", str(r1_path), str(r2_path)], check=True)

    # 2) Create R3 (a clone of R2, so R2 acts as "origin" for R3)
    temp_dir_r3 = tempfile.mkdtemp(prefix="repo_r3_", dir=base_temp_dir)
    r3_path = Path(temp_dir_r3) / "clone_r3"
    subprocess.run(["git", "clone", str(r2_path), str(r3_path)], check=True)

    yield (r2_path, r3_path)

    # Retain temp dirs for evaluation
    print(f"Temporary repositories retained at:\nR2: {r2_path}\nR3: {r3_path}")


@pytest.mark.parametrize(
    "branch_input,expected_sanitized,simulate_answer",
    [
        # (user_input_branch, expected_sanitized_branch, user_confirmation_input)
        ("test", "test", ""),  # no sanitation needed, no prompt
        ("new branch", "new-branch", "y\n"),  # sanitation triggered: space -> dash
        (
            "??invalid??",
            "Branch name '??invalid??' contains invalid characters.",
            "",
        ),  # invalid characters
        ("another/bad///name", "name", "y\n"),  # use last path component
    ],
)
def test_create_feature_branch(
    setup_test_repos, branch_input, expected_sanitized, simulate_answer
):
    """
    Tests creating a feature branch with various name inputs,
    including those that trigger sanitation.
    We feed 'yes' to confirm the new sanitized name if needed.
    """
    r2_path, r3_path = setup_test_repos

    # Move into R3 working directory
    os.chdir(r3_path)

    # The script uses sys.argv and input() for yes/no. We'll call it via subprocess,
    # passing 'simulate_answer' as the input if needed.
    script_path = r3_path / "create_feature_branch.py"

    cmd = ["python", str(script_path), branch_input]
    # If no sanitation needed, the script won't prompt.
    # If sanitation is triggered, it will prompt. We'll answer with 'simulate_answer' text.

    # Run the script
    result = subprocess.run(cmd, input=simulate_answer, text=True, capture_output=True)

    # If the script didn't prompt, 'simulate_answer' is effectively ignored.
    # We'll examine 'result.stdout' to see if it recognized sanitation.

    # If user said "no", the script aborts with exit code 0 (our code says "Aborted by user." and quits).
    # But we used 'y' for the cases that do require an answer, so we expect success (returncode=0).
    # In the case of branch_input == expected_sanitized, there's no prompt and no input needed, so also success.
    if "contains invalid characters" in expected_sanitized:
        assert (
            expected_sanitized in result.stdout
        ), f"Expected error message not found. Got: {result.stdout}"
    else:
        assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"

        # Check that the new branch was created in R3
        git_branch_list = subprocess.run(
            ["git", "branch"], capture_output=True, text=True, check=True
        ).stdout
        # We expect to see 'expected_sanitized' in the local branch list
        assert (
            expected_sanitized in git_branch_list
        ), f"Branch '{expected_sanitized}' not found in local branches. Branch list:\n{git_branch_list}"

        # Optionally check that the 'main' file got renamed to 'expected_sanitized' in the repo
        # If that is part of your script logic:
        assert os.path.exists(
            os.path.join(r3_path, expected_sanitized)
        ), f"Expected file '{expected_sanitized}' was not created after git mv."

    # Switch back to main branch
    subprocess.run(["git", "checkout", "main"], check=True)


def test_propagate_readme(setup_test_repos):
    """
    Tests modifying README.md and using 'update.py' (in R3) to propagate changes
    to all existing feature branches.
    """
    r2_path, r3_path = setup_test_repos

    # Move into R3 working directory
    os.chdir(r3_path)

    # 1) Ensure we are on 'main' (or your default branch)
    subprocess.run(["git", "checkout", "main"], check=True)

    # 2) Modify README.md
    readme_path = os.path.join(r3_path, "README.md")
    with open(readme_path, "a", encoding="utf-8") as f:
        f.write("\nTest propagation line.\n")

    # Commit the change on main
    subprocess.run(["git", "add", "README.md"], check=True)
    subprocess.run(["git", "commit", "-m", "Test update to README"], check=True)

    # 3) Run the update.py script to propagate changes
    update_script_path = os.path.join(r3_path, "update.py")
    # For example, if 'update.py' doesn't need arguments:
    result = subprocess.run(
        ["python", update_script_path], capture_output=True, text=True
    )
    assert result.returncode == 0, f"update.py script failed: {result.stderr}"

    # 4) Verify that all *existing* feature branches got the updated README
    #    (We created some branches in the earlier test, so let's see if they exist.
    #     In practice, you might do 'git branch --list' or fetch them from the test itself.)
    branch_list_output = subprocess.run(
        ["git", "branch"], capture_output=True, text=True, check=True
    ).stdout
    branches = [
        line.strip("* ").strip()
        for line in branch_list_output.splitlines()
        if line.strip()
    ]

    # For each feature branch, check if README.md has the new line
    # (if your 'update.py' does that kind of cross-branch sync).
    for b in branches:
        if b != "main":
            # Checkout the branch
            subprocess.run(["git", "checkout", b], check=True)

            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert (
                    "Test propagation line." in content
                ), f"README.md was not propagated to branch {b}."

    # Return to main or do any final checks
    subprocess.run(["git", "checkout", "main"], check=True)

    print("Propagation test passed successfully.")
