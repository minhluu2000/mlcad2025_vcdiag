import json
import logging
import os
import argparse

from vcd_extract.workflows.fabscalar import FabScalar
from vcd_extract.workflows.mesi import MESI
from vcd_extract.workflows.opentitan import OpenTitan

from vcd_extract.workflows.workflow_utils import clean_design_env

from hanging_threads import start_monitoring
# Track for any hanging threads
start_monitoring(seconds_frozen=300, test_interval=100)


def main():
    # Define argument parser
    parser = argparse.ArgumentParser(
        description="Run VCD error data processing and ML classification workflows")

    # Arguments
    # generate_bugs: Generate bugs for the target design
    # insert_and_extract: Run simulations for the target design and extract VCDs
    parser.add_argument('--mode', type=str, default="inject",
                        choices=["generate_bugs", "insert_and_extract"],
                        help="Mode of operation (generate_bug, insert_and_extract)")
    parser.add_argument('--design_name', type=str, required=True, choices=[
                        "fabscalar", "mesi", "opentitan"], help="Target design name (e.g., fabscalar, mesi, opentitan)")
    parser.add_argument('--njobs', type=int, default=1,
                        help="Number of workers for parallel processing")

    args = parser.parse_args()

    # Set up the target design
    design_name = args.design_name

    # Set up logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # General paths
    root_path = f"{os.path.dirname(os.path.abspath(__file__))}"
    data_path = f"{root_path}/data_storage/{design_name}"
    bugdb_path = f"{root_path}/vcd_extract/bugdb/{design_name}"
    target_signals_path = f"{root_path}/vcd_extract/signals/{design_name}/target_signals.txt"

    # Open the configuration json file
    config_path = f"{root_path}/configs/{design_name}.json"
    with open(config_path, "r") as f:
        config = json.load(f)

    general_config = config["general"]
    clean_environment_setup = general_config["clean_environment_setup"]
    sim_and_extract_config = config["sim_and_extract"]
    generate_bugs_config = config["generate_bugs"]
    insert_bugs_config = config["insert_bugs"]

    njobs = args.njobs

    if clean_environment_setup:
        clean_design_env(root_path=root_path, design_name=design_name)

    if design_name == "fabscalar":
        # Set up the FabScalar workflow
        worker = FabScalar(design_name=design_name,
                           root_path=root_path,
                           data_path=data_path,
                           bugdb_path=bugdb_path,
                           target_signals_path=target_signals_path,
                           general_config=general_config,
                           sim_and_extract_config=sim_and_extract_config,
                           njobs=njobs,
                           logger=logger
                           )
    elif design_name == "mesi":
        # Set up the MESI workflow
        worker = MESI(design_name=design_name,
                      root_path=root_path,
                      data_path=data_path,
                      bugdb_path=bugdb_path,
                      target_signals_path=target_signals_path,
                      general_config=general_config,
                      sim_and_extract_config=sim_and_extract_config,
                      njobs=njobs,
                      logger=logger
                      )
    elif design_name == "opentitan":
        # Set up the OpenTitan workflow
        worker = OpenTitan(design_name=design_name,
                           root_path=root_path,
                           data_path=data_path,
                           bugdb_path=bugdb_path,
                           target_signals_path=target_signals_path,
                           general_config=general_config,
                           sim_and_extract_config=sim_and_extract_config,
                           njobs=njobs,
                           logger=logger
                           )

    # Workflow for generate bugs
    if args.mode == "generate_bugs":
        worker.generate_bugs(
            generate_bugs_config=generate_bugs_config)
    elif args.mode == "insert_and_extract":
        worker.insert_and_extract(
            insert_bugs_config=insert_bugs_config)
    else:
        print("Invalid mode of operation")
        return

    # Clean up the workspace
    if clean_environment_setup:
        clean_design_env(root_path=root_path, design_name=design_name)


if __name__ == "__main__":
    main()
