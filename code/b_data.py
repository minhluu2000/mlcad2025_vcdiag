import json
import logging
import os
import argparse
import datetime
import pandas as pd

from a_bug_injection_vcd_extract.workflows.workflow_utils import copy_folder
from b_data_process_ml_env.data_process import DataProcess

import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=pd.errors.PerformanceWarning)


def main():
    # Define argument parser
    parser = argparse.ArgumentParser(
        description="Run VCD error data processing and ML classification workflows")

    # Arguments
    # process: Process raw tabular data
    # predict: Run ML classification on processed data
    parser.add_argument('--mode', type=str, default="data_process",
                        choices=["data_process", "bug_predict"],
                        help="Mode of operation (process, predict)")
    parser.add_argument('--design_name', type=str, required=True, choices=[
                        "fabscalar", "mesi", "opentitan"], help="Target design name (e.g., fabscalar, mesi, opentitan)")
    parser.add_argument('--njobs', type=int, default=1,
                        help="Number of workers for parallel processing")

    args = parser.parse_args()

    # Set up the target design
    design_name = args.design_name

    # Get current date and time for naming log files
    now = datetime.datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H-%M-%S")

    # General paths
    root_path = f"{os.path.dirname(os.path.abspath(__file__))}"
    data_storage_path = f"{root_path}/../data"
    
    # Log settings
    log_folder_path = f"{root_path}/logs"
    log_file_path = f"{log_folder_path}/processing_log_{current_date}_{current_time}.log"
    logging.basicConfig(filename=log_file_path,
                        format='%(asctime)s %(message)s',
                        filemode='w')    
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Print a test message
    logger.info("Processing log started")
    logger.info("Processing cores: " + str(args.njobs))

    # Open the configuration json file
    config_path = f"{root_path}/configs/{design_name}.json"
    with open(config_path, "r") as f:
        config = json.load(f)

    data_process_config = config["data_process"]

    njobs = args.njobs

    # Workflow for generate bugs
    if args.mode == "data_process":

        # Create an instance of the class
        data_process = DataProcess(
            data_storage_path=data_storage_path,
            data_process_config=data_process_config,
            njobs=njobs
        )

        # Run the workflow
        data_process.run()


if __name__ == "__main__":
    main()
