import os
import subprocess
import multiprocessing
import time
import signal

import logging
import vcdvcd

from contextlib import redirect_stdout
from io import StringIO

from vcd_extract.workflows.workflow_utils import find_full_path, combine_ranges, copy_file, copy_folder, check_config_overlaps

from vcd_extract.llm.models import *
from vcd_extract.llm.bugs.bug_insert import BugInserter

import traceback

from hanging_threads import start_monitoring
# Track for any hanging threads
start_monitoring(seconds_frozen=300, test_interval=100)


class FabScalar:

    def __init__(self,
                 design_name: str,
                 root_path: str,
                 data_path: str,
                 bugdb_path: str,
                 target_signals_path: str,
                 general_config: dict,
                 sim_and_extract_config: dict,
                 njobs: int = 1,
                 logger: logging.Logger = None  # type: ignore
                 ):

        # Paths
        self.design_name = design_name
        self.root_path = root_path
        self.data_path = data_path
        self.bugdb_path = bugdb_path
        self.target_signals_path = target_signals_path
        self.njobs = njobs

        # General settings
        self.general_config = general_config
        self.verbose = self.general_config["verbose"]
        self.acceptance_threshold = self.general_config["acceptance_threshold"]
        print(f"Acceptance threshold: {self.acceptance_threshold}")

        # Sim and extract settings
        self.sim_and_extract_config = sim_and_extract_config
        self.sim_timeout = self.sim_and_extract_config["sim_timeout"]

        if logger:
            self.logger = logger
        else:
            self.verbose = False  # disable verbose mode if logger is not provided
            pass

        # Generate GPT and BugInserter objects
        self.gpt = None
        self.bug_inserter = None
        self.bug_detected = True
        self.reload_bug_inserter = False
        self.failed_to_insert_bug_names = []

    def extract_vcd(self,
                    vcd_path: str,
                    current_label: str,
                    line_limit: int,
                    folder: str,
                    rerun_index: int,
                    extract_vcd_bool: bool = False,
                    numbered_signal_list_path: str = ""
                    ):

        # If self.target_signals_path does not exist, warn the user, provide vcd_path, and exit
        if not os.path.exists(self.target_signals_path):
            print(
                f"Error: {self.target_signals_path} does not exist. Please provide the target signals file or generate it using signals.py. Ctrl + C to exit.")
            print(f"VCD path for signals.py: {vcd_path}")
            return f"Error: {self.target_signals_path} signal list does not exist."

        vcdvcd_callbacks = vcdvcd.PrintDumpsStreamParserCallbacks()

        try:
            with open(self.target_signals_path, "r") as f:
                target_signals = f.read().splitlines()
        except Exception as e:
            return f"Error: {e}"

        if extract_vcd_bool:
            print(
                f"Extracting VCD for {current_label} in folder {folder} (rerun {rerun_index})")
            with StringIO() as buf, redirect_stdout(buf):
                try:
                    vcdvcd.VCDVCD(vcd_path=vcd_path, callbacks=vcdvcd_callbacks,
                                  signals=target_signals)
                except Exception as e:
                    # Write to a file values from buf.getvalue()
                    with open(f"{self.data_path}/{current_label}/error.txt", "w") as f:
                        f.write(buf.getvalue())
                    return f"Error: {e}. \nBuffer content: \n{buf.getvalue()}\nThis bug causes an exception in the VCD extraction process, likely due to a mismatch between the target signals and the VCD file. Generate a different bug."
                vcdvcd_output = buf.getvalue()
                # split the output into two parts: the signal list and the signal activities (capture N events before failure)
                # signal list is printed before =================, capture the entire signal list
                signal_list_indices = [i for i, s in enumerate(
                    vcdvcd_output.split("\n")) if "========" in s][0]

                signal_activities = vcdvcd_output.split(
                    "\n")[signal_list_indices+1:][:-1]

                # Limit to N lines before failure
                signal_activities = signal_activities[-line_limit:]

                # Join the signal activities into a string
                signal_activities = "\n".join(signal_activities)

                # Combine the signal list and signal activities
                final_output = f"{signal_activities}"

                # Delete the vcdvcd_output, signal_activities, and buf to save memory
                del vcdvcd_output, signal_activities, buf

            # Write the file
            try:
                final_output_path = f"{self.data_path}/{current_label}/{folder}_run_{rerun_index}.txt"
                print(f"Writing to {final_output_path}")
                with open(final_output_path, "w") as f:
                    f.write(final_output)
            except Exception as e:
                print(f"Error when writing to {final_output_path}: {e}")
                return f"Error: {e}"

        if len(numbered_signal_list_path) > 0 or not extract_vcd_bool:
            print(
                f"Extracting signal list to {numbered_signal_list_path} for the purpose of exporting numbered signal list or checking signal list compatibility")

            with StringIO() as buf, redirect_stdout(buf):
                try:
                    vcdvcd.VCDVCD(vcd_path=vcd_path, callbacks=vcdvcd_callbacks,
                                  signals=target_signals)
                except Exception as e:
                    # Write to a file values from buf.getvalue()
                    with open(f"{self.data_path}/{current_label}/error.txt", "w") as f:
                        f.write(buf.getvalue())
                    return f"Error: {e}. \nBuffer content: \n{buf.getvalue()}\nThis bug causes an exception in the VCD extraction process, likely due to a mismatch between the target signals and the VCD file. Generate a different bug."
                vcdvcd_output = buf.getvalue()
                # split the output into two parts: the signal list and the signal activities (capture N events before failure)
                # signal list is printed before =================, capture the entire signal list
                try:
                    signal_list_indices = [i for i, s in enumerate(
                        vcdvcd_output.split("\n")) if "========" in s][0]
                except Exception as e:
                    with open(f"{self.data_path}/{current_label}/error.txt", "w") as f:
                        f.write(buf.getvalue())
                    return f"Error: {e}.\nBuffer content: \n{buf.getvalue()}\nUnable to find the signal list in the VCD output. This could be due to a mismatch between the target signals and the VCD file. Please check the target signals or generate a different bug."

                # Export the signal list to a file
                with open(numbered_signal_list_path, "w") as f:
                    f.write("\n".join(vcdvcd_output.split(
                        "\n")[:signal_list_indices-2]))

                print(
                    f"Signal list exported to {numbered_signal_list_path} successfully")

                del vcdvcd_output, buf

        # Return success message
        return f"Successfully extracted VCD for {current_label}"

    def run_sim_and_extract(self,
                            design_instance_path: str,
                            current_label: str,
                            reruns: int = 1,
                            extract_vcd_bool: bool = False,
                            extract_signal_list: bool = False,
                            generate_bugs_worker_mode: bool = False
                            ):

        error = {"code": -1, "message": "Error", "failed_ip_log_path": None}

        # Create a folder for the current label
        if not os.path.exists(f"{self.data_path}/{current_label}"):
            os.makedirs(f"{self.data_path}/{current_label}")
        else:  # Clear the folder
            subprocess.run(
                f"rm -rf {self.data_path}/{current_label}/*", shell=True)

        # Important design paths
        sim_path = f"{design_instance_path}/simulation/benchmarks"

        # Initialize timeout tracker
        timeout_tracker = []

        for rerun in range(reruns):
            timeout_tracker.append(
                dict([(folder, False)for folder in os.listdir(sim_path)]))
            skip_extract_vcd = False
            for _, folder in enumerate(os.listdir(sim_path)):
                folder_full_path = f"{sim_path}/{folder}"
                try:
                    os.chdir(folder_full_path)
                    print(f"Changed directory to {os.getcwd()}")
                except Exception as e:
                    error["code"] = -1
                    error["message"] = f"Error: {e}"
                    return error

                clean_cmd = f"make clean"
                compile_cmd = f"make compile_vcd"
                run_cmd = f"make run_nc_vcd"
                vcd_path = f"{folder_full_path}/simulate.vcd"

                # clean
                try:
                    subprocess.run(f"{clean_cmd}", shell=True, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error during cleaning: {e}")
                    error["code"] = -1
                    error["message"] = f"Error during cleaning: {e}"
                    return error

                # compile
                try:
                    subprocess.run(f"{compile_cmd}", shell=True, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error during compilation: {e}")
                    error["code"] = -1
                    error["message"] = f"Error during compilation: {e}"
                    return error

                # simulate
                start_time = time.time()
                p = subprocess.Popen(
                    run_cmd, shell=True, preexec_fn=os.setpgrp)

                try:
                    while p.poll() is None:
                        time.sleep(0.1)
                        if time.time() - start_time > self.sim_timeout:
                            print(
                                f"Process {p.pid} exceeded timeout. Killing it...")
                            timeout_tracker[rerun][folder] = True
                            # kill the child process and its children
                            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                            if os.path.exists(vcd_path):  # remove the vcd file
                                os.remove(vcd_path)
                            # exit out of the loop
                            break

                except KeyboardInterrupt:
                    print("KeyboardInterrupt detected. Killing process...")
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                    return

                # sleep for another 10 seconds
                time.sleep(10)

                # Check if p is still running
                if p.poll() is None:
                    print(f"Process {p.pid} is still running. Killing it...")
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                    timeout_tracker[rerun][folder] = True
                else:
                    print(f"Process {p.pid} completed successfully.")

                if self.verbose:
                    print(
                        f"Timeout tracker: {timeout_tracker} for label {current_label} and folder {folder}")

                extract_config = self.sim_and_extract_config["extract"]
                line_limit = extract_config["line_limit"]

                # Post processing
                if generate_bugs_worker_mode and timeout_tracker[rerun][folder] == False:
                    if not skip_extract_vcd:
                        print(
                            "Extracting VCD for the purpose of generate bugs or extract vcd data for testing")
                        self.target_signal_path = f"{'/'.join(self.target_signals_path.split('/')[:-1])}/target_signals_all.txt"
                        msg = self.extract_vcd(vcd_path=vcd_path, current_label=current_label,
                                               folder=folder, rerun_index=rerun, line_limit=line_limit,
                                               numbered_signal_list_path=f"{'/'.join(self.target_signal_path.split('/')[:-1])}/numbered_signal_list.txt")
                        print(f"message from extract_vcd: {msg}")
                    if "error" in msg.lower():
                        error["code"] = -4
                        error["message"] = msg
                        return error
                    else:
                        skip_extract_vcd = True
                        print(
                            f"Verified extraction from {current_label} does not cause any errors. Skipping extraction for the rest of the folders.")
                elif not generate_bugs_worker_mode and timeout_tracker[rerun][folder] == False:
                    print("Extracting VCD for the purpose of insert and extract")
                    msg = self.extract_vcd(vcd_path=vcd_path, current_label=current_label,
                                           folder=folder, rerun_index=rerun, line_limit=line_limit, extract_vcd_bool=extract_vcd_bool)
                if os.path.exists(vcd_path):
                    os.remove(vcd_path)
                    if self.verbose:
                        print(f"Removed {vcd_path}")

        try:
            total_trackers = sum([len(timeout_tracker[i])
                                 for i in range(reruns)])
            total_timeouts = sum(
                [len([v for v in timeout_tracker[i].values() if v == True]) for i in range(reruns)])
        except Exception as e:
            error["code"] = -4
            error["message"] = f"Error calculating timeouts: {e}"
            return error
        # return -2 means all folders have timed out -> no bug detected
        if total_timeouts == total_trackers:
            error["code"] = -2
            error["message"] = f"Bug not detected for {current_label}"
        # return -3 means some folders have timed out -> bug might not be detected
        elif (total_trackers - total_timeouts) < self.acceptance_threshold * reruns:
            print(
                f"Warning: {total_timeouts} out of {total_trackers} folders timed out. Bug might not be detected for {current_label}. The threshold is {self.acceptance_threshold} * {reruns} = {self.acceptance_threshold * reruns}")

            error["code"] = -3
            error["message"] = f"Bug might not be detected for {current_label}"
        else:
            error["code"] = 0
            error["message"] = f"Simulation completed successfully for {current_label}"
        return error

    def generator(self,
                  design_file,
                  output_dir,
                  num_bugs: int,
                  model="gpt",
                  debug=False
                  ):

        design_name = design_file.split(".v")[0].split(".sv")[
            0].split("/")[-1]

        if self.reload_bug_inserter or not self.bug_inserter.is_file_loaded():
            print(design_file)
            print(os.path.join(output_dir, "caches",
                  design_name.rsplit("_", 1)[0] + ".pkl"))
            self.bug_inserter.load_verilog(design_file, cache_file_path=os.path.join(
                output_dir, "caches", design_name.rsplit("_", 1)[0] + ".pkl"))
            self.reload_bug_inserter = False

        design_extension = design_file.split('.')[-1]
        for i in range(num_bugs):
            try:
                outpath = str(os.path.join(
                    output_dir, design_name + f".{design_extension}"))
                _, mutation_desc = self.bug_inserter.insert_bug(
                    out_file=outpath)
                print(f"-- Inserted bug {i+1}/{num_bugs} -> {mutation_desc}")
            except Exception as e:
                print(f"Bug Generation Error: {e}")
                traceback.print_exc()
                continue

    def generate_bugs_worker(self, label: str,
                             area_config: dict,
                             num_retries: int,
                             num_bugs_per_try: int,
                             overwrite=True,
                             clear_bug_inserter_cache=False):
        # Hardcoded worker index for now
        worker_index = 1

        llm_dir_path = f"{self.root_path}/vcd_extract/llm"
        prompt_dir = f"{llm_dir_path}/prompts"
        self.bug_inserter = BugInserter(
            self.gpt, prompt_dir, debug=True, clear_cache=clear_bug_inserter_cache)

        # Original instance path
        original_instance_path = f"{self.root_path}/designs/{self.design_name}"
        original_instance_path_rtl = f"{original_instance_path}/cores/core-MDQ"

        # Design instance path
        design_instance = f"{self.design_name}_{worker_index}"
        design_instance_path = f"{self.root_path}/designs/{design_instance}"
        design_instance_path_rtl = f"{design_instance_path}/cores/core-MDQ"

        # if the instance path does not exist, create it
        if not os.path.exists(design_instance_path):
            print(f"Creating workspace {design_instance_path}")
            os.system(f"cp -r {original_instance_path} {design_instance_path}")
            assert os.path.exists(
                design_instance_path), f"Failed to create workspace {design_instance_path}"
            print(f"Workspace {design_instance_path} is created successfully")

        # Get path to file for injecting bugs
        filename = area_config["filename"]
        original_filepath = find_full_path(
            root_path=original_instance_path_rtl, filename=filename)
        instance_filepath = find_full_path(
            root_path=design_instance_path_rtl, filename=filename)

        if self.verbose:
            if len(instance_filepath) == 0:
                print(
                    f"File {filename} not found. This could be due to missing design instance.")
                return
            else:
                print(f"Full path: {instance_filepath}")

        # Combine training and testing ranges
        training_ranges_list = area_config["training_ranges"]
        testing_ranges_list = area_config["testing_ranges"]

        training_ranges = combine_ranges(training_ranges_list)
        testing_ranges = combine_ranges(testing_ranges_list)

        if self.verbose:
            print(f"Training ranges: {training_ranges}")
            print(f"Testing ranges: {testing_ranges}")

        # Combine training and testing ranges
        training_settings = [(index, True) for index in training_ranges]
        testing_settings = [(index, False) for index in testing_ranges]

        bugdb_label_path = f"{self.bugdb_path}/{label}"

        # Check if the bugdb_label_path exists, if not, create it
        if not os.path.exists(bugdb_label_path):
            os.makedirs(bugdb_label_path)

        # for training and testing index, generate bugs
        settings = training_settings + testing_settings
        for setting in settings:
            # Create a new template for the bug
            if setting[1] == True:  # Training
                current_bug_filepath = f"{bugdb_label_path}/{filename.replace(f'.', f'_{setting[0]}.')}"
                current_label = f"{label}{setting[0]}"
                reruns = area_config["training_reruns"]
            else:  # Testing
                current_bug_filepath = f"{bugdb_label_path}/{filename.replace(f'.', f'_{setting[0]}T.')}"
                current_label = f"{label}{setting[0]}T"
                reruns = area_config["testing_reruns"]

            if overwrite:
                # Check if that file already exists
                if os.path.exists(current_bug_filepath):
                    print(
                        f"File {current_bug_filepath} already exists. Overwriting...")
                else:
                    print(
                        f"{current_bug_filepath} does not exist. Making a copy of the original file...")
                copy_file(source_file=original_filepath,
                          target_file=current_bug_filepath)
            else:
                if os.path.exists(current_bug_filepath):
                    print(
                        f"File {current_bug_filepath} already exists. Set to not overwrite.")
                    continue
                else:
                    print(
                        f"{current_bug_filepath} does not exist. Making a copy of the original file...")
                    copy_file(source_file=original_filepath,
                              target_file=current_bug_filepath)

            curr_try = 0
            self.bug_detected = False
            self.reload_bug_inserter = True
            while curr_try < num_retries and not self.bug_detected:
                # Generate bugs with LLMs
                # Take the current_bug_filepath and add mutations to it
                print(f"Try {curr_try+1} for {current_label}.")
                bug_gen_results = self.generator(
                    design_file=current_bug_filepath,
                    output_dir=bugdb_label_path,
                    num_bugs=num_bugs_per_try,
                    model="gpt",
                    debug=self.verbose)

                # Put the mutated file in the design instance path
                copy_file(source_file=current_bug_filepath,
                          target_file=instance_filepath)

                # Run simulation
                result = self.run_sim_and_extract(design_instance_path=design_instance_path,
                                                  current_label=current_label, reruns=reruns, extract_vcd_bool=False, generate_bugs_worker_mode=True)

                if result is not None:
                    result_code = result["code"]
                    result_message = result["message"]
                    failed_ip_log_path = None
                else:
                    print(
                        f"Error: Simulation result is None for {current_label}")

                # Check result
                if result_code < 0:  # compilation, simulation, or extraction error
                    if result_code == -1:  # compilation error
                        msg = f"Compilation error for {current_label}. Error message: {result_message}"
                    elif result_code == -2:
                        msg = f"Bug not detected for {current_label}. Error message: {result_message}"
                    elif result == -3:
                        msg = f"Bug might not be detected for {current_label}. Error message: {result_message}"
                    elif result_code == -4:
                        if "signal list does not exist" in result_message:
                            msg = f"Signal list does not exist for {current_label}. Error message: {result_message}"
                            # terminate the program
                            exit(1)
                        else:
                            msg = f"Error for {current_label}. Error message: {result_message}"
                    else:
                        msg = f"Error for {current_label}. Error message: {result_message}"
                    for _ in range(num_bugs_per_try):
                        self.bug_inserter.undo_mutation()
                elif result_code == 0:  # simulation completed successfully
                    self.bug_detected = True
                    design_name = current_bug_filepath.split(
                        ".v")[0].split(".sv")[0].split("/")[-1]
                    caches_path = os.path.join(bugdb_label_path, "caches")
                    if not os.path.exists(caches_path):
                        os.makedirs(caches_path)
                    self.bug_inserter.save_cache(cache_file=os.path.join(
                        caches_path, design_name.rsplit("_", 1)[0] + ".pkl"))
                    msg = f"Bug detected for {current_label}"
                else:
                    msg = f"Unknown error for {current_label}"
                print(msg)

                curr_try += 1

            # If bug not detected by the end, delete the current_bug_filepath and record the bug name to failed_to_insert_bug_names
            if not self.bug_detected:
                self.failed_to_insert_bug_names.append(current_label)
                print(
                    f"Failed to insert bug for {current_label}. Will try again.")
                settings.append(setting)

            # Replace the entire folder with the original folder to remove the injected bugs
            copy_file(source_file=original_filepath,
                      target_file=instance_filepath)

        print(f"Failed to insert bugs: {self.failed_to_insert_bug_names}")

    def insert_and_extract_worker(self,
                                  label: str,
                                  area_config: dict,
                                  index: int,
                                  training: bool = True,
                                  extract_signal_list: bool = False
                                  ):
        # Get the worker index
        process_name = multiprocessing.current_process().name
        print(f"Process name: {process_name}")
        worker_index = process_name.split("-")[-1]

        # Original instance path
        original_instance_path = f"{self.root_path}/designs/{self.design_name}"
        original_instance_path_rtl = f"{original_instance_path}/cores/core-MDQ"

        # Design instance path
        design_instance = f"{self.design_name}_{worker_index}"
        design_instance_path = f"{self.root_path}/designs/{design_instance}"
        design_instance_path_rtl = f"{design_instance_path}/cores/core-MDQ"

        # if the instance path does not exist, create it
        if not os.path.exists(design_instance_path):
            print(f"Creating workspace {design_instance_path}")
            os.system(f"cp -r {original_instance_path} {design_instance_path}")
            assert os.path.exists(
                design_instance_path), f"Failed to create workspace {design_instance_path}"
            print(f"Workspace {design_instance_path} is created successfully")

        # Get path to file for injecting bugs
        filename = area_config["filename"]
        original_filepath = find_full_path(
            root_path=original_instance_path_rtl, filename=filename)
        instance_filepath = find_full_path(
            root_path=design_instance_path_rtl, filename=filename)

        if self.verbose:
            if len(instance_filepath) == 0:
                print(
                    f"File {filename} not found. This could be due to missing design instance.")
                print(f"Instance path: {design_instance_path_rtl}")
                return
            else:
                print(f"Full path: {instance_filepath}")

        if training:
            current_bug_filepath = f"{self.bugdb_path}/{label}/{filename.replace(f'.', f'_{index}.')}"
            current_label = f"{label}{index}"
            reruns = area_config["training_reruns"]
        else:
            current_bug_filepath = f"{self.bugdb_path}/{label}/{filename.replace(f'.', f'_{index}T.')}"
            current_label = f"{label}{index}T"
            reruns = area_config["testing_reruns"]

        # Check if that file already exists
        if os.path.exists(current_bug_filepath):
            print(f"File {current_bug_filepath} already exists")
        else:
            print(f"{current_bug_filepath} does not exist. Skipping")
            # For now, continue to the next file
            return

        # Put the mutated file in the design instance path
        copy_file(source_file=current_bug_filepath,
                  target_file=instance_filepath)

        # Run simulation
        result = self.run_sim_and_extract(design_instance_path=design_instance_path,
                                          current_label=current_label, reruns=reruns, extract_vcd_bool=True, extract_signal_list=extract_signal_list)

        if result is not None:
            result_code = result["code"]
            result_message = result["message"]
            failed_ip_log_path = None
        else:
            print(
                f"Error: Simulation result is None for {current_label}")

        # Check result
        if result_code < 0:  # compilation, simulation, or extraction error
            if result_code == -1:  # compilation error
                msg = f"Compilation error for {current_label}. Error message: {result_message}"
            elif result_code == -2:
                msg = f"Bug not detected for {current_label}. Error message: {result_message}"
            elif result == -3:
                msg = f"Bug might not be detected for {current_label}. Error message: {result_message}"
            elif result_code == -4:
                if "signal list does not exist" in result_message:
                    msg = f"Signal list does not exist for {current_label}. Error message: {result_message}"
                    # terminate the program
                    exit(1)
                else:
                    msg = f"Error for {current_label}. Error message: {result_message}"
            else:
                msg = f"Error for {current_label}. Error message: {result_message}"
        elif result_code == 0:  # simulation completed successfully
            msg = f"Bug detected for {current_label}"
        else:
            msg = f"Unknown error for {current_label}"
        print(msg)

        # Wait a 10 seconds for clean up between runs
        time.sleep(10)

        # Replace the entire folder with the original folder to remove the injected bugs
        copy_folder(source_folder=original_instance_path_rtl,
                    target_folder=design_instance_path_rtl)

        # Wait a 10 seconds for clean up between runs
        time.sleep(10)

    def generate_bugs(self, generate_bugs_config: dict):
        num_bugs_per_try = generate_bugs_config["bugs_per_try"]
        num_retries = generate_bugs_config["retry"]
        overwrite = generate_bugs_config["overwrite"]
        clear_bug_inserter_cache = generate_bugs_config["clear_bug_inserter_cache"]
        bugs = generate_bugs_config["bugs"]

        # initialize gpt and bug inserter
        self.gpt = GPT(model_id="gpt-4o-mini")
        self.gpt.initialize()

        for label, areas_config in bugs.items():
            # check if the training ranges in the area config overlap, if so, raise an error
            config_bool, config_overlaps = check_config_overlaps(
                areas_config, "training_ranges")
            if config_bool == True:
                print(f"Training ranges overlap in {label}: {config_overlaps}")
                exit(1)

            for area_config in areas_config:
                self.generate_bugs_worker(
                    label, area_config, num_retries, num_bugs_per_try, overwrite, clear_bug_inserter_cache)

    def insert_and_extract(self, insert_bugs_config: dict):
        worker_pool = multiprocessing.Pool(self.njobs)
        bugs = insert_bugs_config["bugs"]
        for label, areas_config in bugs.items():
            # check if the training ranges in the area config overlap, if so, raise an error
            config_bool, config_overlaps = check_config_overlaps(
                areas_config, "training_ranges")
            if config_bool == True:
                print(
                    f"Training ranges overlap in {label}: {config_overlaps}")
                exit(1)
            for area_config in areas_config:
                training_ranges_list = area_config["training_ranges"]
                testing_ranges_list = area_config["testing_ranges"]

                training_ranges = combine_ranges(training_ranges_list)
                testing_ranges = combine_ranges(testing_ranges_list)

                if self.verbose:
                    print(f"Training ranges: {training_ranges}")
                    print(f"Testing ranges: {testing_ranges}")

                training_settings = [[label, area_config, index, True]
                                     for index in training_ranges]
                testing_settings = [[label, area_config, index, False]
                                    for index in testing_ranges]
                print(training_settings)
                print(testing_settings)
                combined_settings = training_settings + testing_settings
                if len(combined_settings) == 0:
                    print(
                        f"No training or testing ranges found for {label}. Skipping...")
                    continue
                last_setting = combined_settings[-1]

                # Use apply_async for explicit worker process reset handling
                for setting in combined_settings:
                    # if this is the last index of the combined ranges, extract the signal list
                    if setting == last_setting:
                        setting = tuple(setting + [True])
                        worker_pool.apply_async(
                            self.insert_and_extract_worker, setting)
                    else:
                        setting = tuple(setting + [False])
                        worker_pool.apply_async(
                            self.insert_and_extract_worker, setting)

        # Wait for worker to finish
        worker_pool.close()
        worker_pool.join()
