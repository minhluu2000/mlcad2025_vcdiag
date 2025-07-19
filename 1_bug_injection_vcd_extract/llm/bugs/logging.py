from difflib import unified_diff
from termcolor import colored

def print_diff(file_content1, file_content2, context_size=3):
    lines1 = file_content1.splitlines()
    lines2 = file_content2.splitlines()

    diff = list(unified_diff(lines1, lines2, n=context_size))

    if not diff:
        print("No differences found.")
        return

    for line in diff:
        if line.startswith("---") or line.startswith("+++"):
            print(colored(line.strip(), 'cyan'))
        elif line.startswith("@@"):
            print(colored(line.strip(), 'yellow'))
        elif line.startswith("-"):
            print(colored(line, 'red'))
        elif line.startswith("+"):
            print(colored(line, 'green'))
        else:
            print(line)

if __name__ == '__main__':
    file1 = """Line 1: This is a test.
    Line 2: Here is another line.
    Line 3: This line is unchanged."""

    file2 = """Line 1: This is a test.
    Line 2: Here is a modified line.
    Line 3: This line is unchanged.
    Line 4: This is a new addition."""

    print_diff(file1, file2)
