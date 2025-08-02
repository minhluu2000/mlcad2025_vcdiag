# Iterate through all v and sv files in the directory and run verible-verilog-format on them

import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="Format Verilog files using Verible")
    parser.add_argument("--directory", help="Directory containing Verilog files", required=True)
    args = parser.parse_args()
    
    directory = args.directory
    if not os.path.isdir(directory):
        print(f"Directory {directory} does not exist")
        return
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".v") or file.endswith(".sv"):
                file_path = os.path.join(root, file)
                print(f"Formatting {file_path}")
                os.system(f"verible-verilog-format {file_path} --inplace")
                
if __name__ == "__main__":
    main()