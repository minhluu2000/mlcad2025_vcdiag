import os
import subprocess
import multiprocessing
import time
from datetime import datetime
import signal

import logging
import vcdvcd

from contextlib import redirect_stdout
from io import StringIO

from vcd_extract.workflows.workflow_utils import ROI, find_full_path, combine_ranges, copy_file, copy_folder, check_config_overlaps, get_next_available_path

from vcd_extract.llm.models import *
from vcd_extract.llm.bugs.bug_insert import BugInserter
from vcd_extract.evaluation import MutationLogger, MutationRecord

import traceback

from hanging_threads import start_monitoring
# Track for any hanging threads
start_monitoring(seconds_frozen=300, test_interval=100)


class OpenTitan:

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

        # Sim and extract settings
        self.sim_and_extract_config = sim_and_extract_config
        self.ip_name = self.sim_and_extract_config["ip_name"]
        self.hjson_name = self.sim_and_extract_config["hjson_name"]
        self.test_list_name = self.sim_and_extract_config["test_list_name"]
        self.nfailures_before_stop = self.sim_and_extract_config["nfailures_before_stop"]
        self.print_interval = self.sim_and_extract_config["print_interval"]
        self.additional_flags = self.sim_and_extract_config["additional_flags"]

        # Append the ip_name to data_path, bugdb_path, and target_signals_path
        self.data_path = f"{self.data_path}/{self.ip_name}"
        self.bugdb_path = f"{self.bugdb_path}/{self.ip_name}"
        self.target_signals_path = self.target_signals_path.replace(
            "target_signals", f"{self.ip_name}/target_signals")

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

        self.rois: list[ROI] = []
        self.current_bug: list[MutationRecord] = []
        self.num_mutations = 0
        self.num_bug_scenarios = 0

        mutation_log_file = get_next_available_path(
            f'data/{design_name}/bugs_{design_name}_{self.ip_name}.csv')
        self.mutation_logger = MutationLogger(
            os.path.abspath(mutation_log_file))

    def extract_vcd(self,
                    vcd_path: str,
                    current_label: str,
                    line_limit: int,
                    extract_vcd_bool: bool = False,
                    numbered_signal_list_path: str = ""
                    ):

        # If self.target_signals_path does not exist, warn the user, provide vcd_path, and exit
        if not os.path.exists(self.target_signals_path):
            print(
                f"Error: {self.target_signals_path} does not exist. Please provide the target signals file or generate it using signals.py. Ctrl + C to exit.")
            print(f"VCD path for signals.py: {vcd_path}")
            exit(1)
            return f"Error: {self.target_signals_path} does not exist."

        vcdvcd_callbacks = vcdvcd.PrintDumpsStreamParserCallbacks()

        try:
            with open(self.target_signals_path, "r") as f:
                target_signals = f.read().splitlines()
        except Exception as e:
            return f"Error when opening and reading {self.target_signals_path}: {e}"

        if extract_vcd_bool:
            with StringIO() as buf, redirect_stdout(buf):
                try:
                    vcdvcd.VCDVCD(vcd_path=vcd_path, callbacks=vcdvcd_callbacks,
                                  signals=target_signals)
                except Exception as e:
                    # Write to a file values from buf.getvalue()
                    with open(f"{self.data_path}/{current_label}/error.txt", "w") as f:
                        f.write(buf.getvalue())
                    return f"Error: {e}. This bug causes an exception in the VCD extraction process, likely due to a mismatch between the target signals and the VCD file. Generate a different bug."
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
                final_output_path = f"{self.data_path}/{current_label}/{os.path.basename(vcd_path).replace('.vcd', '.txt')}"
                print(f"Writing to {final_output_path}")
                with open(final_output_path, "w") as f:
                    f.write(final_output)
            except Exception as e:
                return f"Error when extracting VCD, at final writing to file step: {e}"

        if len(numbered_signal_list_path) > 0 or not extract_vcd_bool:
            with StringIO() as buf, redirect_stdout(buf):
                try:
                    vcdvcd.VCDVCD(vcd_path=vcd_path, callbacks=vcdvcd_callbacks,
                                  signals=target_signals)
                except Exception as e:
                    # Write to a file values from buf.getvalue()
                    with open(f"{self.data_path}/{current_label}/error.txt", "w") as f:
                        f.write(buf.getvalue())
                    return f"Error: {e}. This bug causes an exception in the VCD extraction process, likely due to a mismatch between the target signals and the VCD file. Generate a different bug."
                vcdvcd_output = buf.getvalue()
                # split the output into two parts: the signal list and the signal activities (capture N events before failure)
                # signal list is printed before =================, capture the entire signal list
                signal_list_indices = [i for i, s in enumerate(
                    vcdvcd_output.split("\n")) if "========" in s][0]

                # Export the signal list to a file
                with open(numbered_signal_list_path, "w") as f:
                    f.write("\n".join(vcdvcd_output.split(
                        "\n")[:signal_list_indices-2]))

                del vcdvcd_output, buf

        # Delete the vcd file to save space
        os.remove(vcd_path)

        # Return success message
        return "Successfully extracted VCD for {current_label}"

    def run_sim_and_extract(self,
                            design_instance_path: str,
                            current_label: str,
                            reruns: int = 1,
                            extract_vcd_bool: bool = False,
                            extract_signal_list: bool = False,
                            generate_bugs_worker_mode: bool = False
                            ):

        error = {"code": -1, "message": "Error", "failed_ip_log_path": None}

        if extract_vcd_bool:
            # Create a folder for the current label
            if not os.path.exists(f"{self.data_path}/{current_label}"):
                os.makedirs(f"{self.data_path}/{current_label}")
            else:  # Clear the folder
                subprocess.run(
                    f"rm -rf {self.data_path}/{current_label}/*", shell=True)

        # cd to the design instance path
        try:
            os.chdir(design_instance_path)
            print(f"Changed directory to {os.getcwd()}")
        except Exception as e:
            error["code"] = -1
            error["message"] = f"Error: {e}"
            return error

        # Important design paths
        sim_path = f"{design_instance_path}/util/dvsim/dvsim.py"
        hjson_path = f"{design_instance_path}/hw/ip/{self.ip_name}/dv/{self.hjson_name}.hjson"
        logs_path = f"{design_instance_path}/scratch"
        failed_ip_log_path = None

        quick_run_cmd = f"{sim_path} {hjson_path} --proj-root {design_instance_path} -i {self.test_list_name} --reseed 1 --print-interval {self.print_interval} --run-opts +UVM_MAX_QUIT_COUNT={self.nfailures_before_stop} {self.additional_flags}"

        # Check if logs_path exists
        if not os.path.exists(logs_path):
            if self.verbose:
                print(f"Could not find log folder. Running simulation...")

            if self.verbose:
                print(f"Running simulation: {quick_run_cmd}")
            subprocess.run([quick_run_cmd], shell=True)

        # Find log folder name that contains ip_name in the logs_path
        try:
            for root, dirs, _ in os.walk(logs_path):
                for folder in dirs:
                    if self.ip_name in folder and ("vcs" in folder or "xrun" in folder):
                        ip_log_path = f"{root}/{folder}"
                        failed_ip_log_path = f"{ip_log_path}/failed"
                        if self.verbose:
                            print(f"Found log folder: {ip_log_path}")
                        break
        except Exception as e:
            error["code"] = -1
            error["message"] = f"Error: {e}"
            return error

        # If could not find the folder, run the simulation
        if ip_log_path is None:
            if self.verbose:
                print(f"Could not find log folder. Running simulation...")

            if self.verbose:
                print(f"Running simulation: {quick_run_cmd}")
            subprocess.run([quick_run_cmd], shell=True, check=True)

            # Try to find the log folder again
            try:
                for root, dirs, _ in os.walk(logs_path):
                    for folder in dirs:
                        if self.ip_name in folder and ("vcs" in folder or "xrun" in folder):
                            ip_log_path = f"{root}/{folder}"
                            failed_ip_log_path = f"{ip_log_path}/failed"
                            if self.verbose:
                                print(f"Found log folder: {ip_log_path}")
                            break
            except Exception as e:
                error["code"] = -1
                error["message"] = f"Error: {e}"
                return error

        # Run simulation
        sim_cmd = f"{sim_path} {hjson_path} --proj-root {design_instance_path} -i {self.test_list_name} --reseed {reruns} --waves fsdb --print-interval {self.print_interval} --run-opts +UVM_MAX_QUIT_COUNT={self.nfailures_before_stop} {self.additional_flags}"

        if self.verbose:
            print(f"Running simulation: {sim_cmd}")
        try:
            # Start the subprocess in a new process group
            p = subprocess.Popen(
                sim_cmd,
                shell=True,
                preexec_fn=os.setsid  # Start new process group
            )
            try:
                while p.poll() is None:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("Interrupted. Killing process group...")
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                raise

        except Exception as e:
            error["code"] = -1
            error["message"] = f"Error: {e}"
            print(error["message"])
            return error

        error["code"] = 0
        error["message"] = "Simulation completed successfully"
        error["failed_ip_log_path"] = failed_ip_log_path

        # if extract_vcd_bool:
        for folder in os.listdir(failed_ip_log_path):
            try:
                # Get fsdb and log files for each failed folder
                fsdb_path = f"{failed_ip_log_path}/{folder}/waves.fsdb"
                log_path = f"{failed_ip_log_path}/{folder}/run.log"

                # Get test name
                test_name = f"{folder.split('.')[0]}.{folder.split('.')[1]}"

                # Rename fsdb file to replace waves.fsdb with test name
                new_fsdb_path = fsdb_path.replace(
                    "waves.fsdb", f"{test_name}.fsdb")
                os.rename(fsdb_path, new_fsdb_path)
                fsdb_path = new_fsdb_path

                # Extract settings
                extract_config = self.sim_and_extract_config["extract"]
                time_tag_before_failure_percent = extract_config["time_tag_before_failure_percent"]
                time_tag_before_failure_min = extract_config["time_tag_before_failure_min"]
                time_tag_before_failure_max = extract_config["time_tag_before_failure_max"]
                scaling_adjustment = extract_config["scaling_adjustment"]
                line_limit = extract_config["line_limit"]

                if os.path.exists(fsdb_path):
                    fsdb2vcd_summary_cmd = f"fsdb2vcd {fsdb_path} -summary"
                    fsdb2vcd_cmd = f"fsdb2vcd {fsdb_path} -o {fsdb_path.replace('.fsdb', '.vcd')}"

                    fsdb_summary = subprocess.run(
                        [fsdb2vcd_summary_cmd], shell=True, check=True, capture_output=True)
                    print(fsdb_summary.stderr.decode("utf-8"))

                    # get line from stderr that contains "scale unit"
                    scale_unit = [line for line in fsdb_summary.stderr.decode(
                        "utf-8").split("\n") if "scale unit" in line][0]
                    # Get the last two characters of the scale unit
                    # example: scale unit              : 100ps then scale_unit = "ps"
                    unit = scale_unit.split(":")[-1].strip()[-2:]

                    # get line from stderr that contains "nmax xtag"
                    nmax_xtag = [line for line in fsdb_summary.stderr.decode(
                        "utf-8").split("\n") if "max xtag" in line][0]
                    # get the max interval
                    # example: max xtag		: (0 40964) then time_tag_max = 40964
                    time_tag_max = int(nmax_xtag.split(
                        ":")[-1].strip().split(" ")[-1].replace(")", ""))
                    time_tag_interval = int(
                        time_tag_max * time_tag_before_failure_percent / 100)
                    time_tag_start = time_tag_max - time_tag_interval

                    if time_tag_interval < time_tag_before_failure_min:
                        final_interval = 0
                    elif time_tag_interval < time_tag_before_failure_max:
                        final_interval = time_tag_start
                    else:
                        final_interval = time_tag_max - time_tag_before_failure_max

                    fsdb2vcd_cmd = f"{fsdb2vcd_cmd} -bt {final_interval * scaling_adjustment}{unit}"

                    if self.verbose:
                        print(f"Extracting VCD: {fsdb2vcd_cmd}")
                    subprocess.run([fsdb2vcd_cmd], shell=True)

                    vcd_path = fsdb_path.replace(".fsdb", ".vcd")

                    if extract_signal_list or generate_bugs_worker_mode:  # if we want to extract the signal list
                        self.target_signal_path = f"{'/'.join(self.target_signals_path.split('/')[:-1])}/target_signals_all.txt"
                        msg = self.extract_vcd(vcd_path=vcd_path,
                                               current_label=current_label,
                                               line_limit=line_limit,
                                               extract_vcd_bool=extract_vcd_bool,
                                               numbered_signal_list_path=f"{'/'.join(self.target_signal_path.split('/')[:-1])}/numbered_signal_list.txt")
                        # exit the for loop since we only want to extract the signal list once
                        break

                    else:  # if we want to do traditional vcd extraction
                        msg = self.extract_vcd(vcd_path=vcd_path,
                                               current_label=current_label,
                                               line_limit=line_limit,
                                               extract_vcd_bool=extract_vcd_bool)

                    if "error" in msg.lower():
                        error["code"] = -2
                        error["message"] = msg
                        return error

            except Exception as e:
                print(f"Error: {e}")
                error["code"] = -2
                error["message"] = f"Error: {e}"
                return error

        return error

    def generator(self,
                  design_file,
                  output_dir,
                  num_bugs: int,
                  rois=None,
                  model="gpt",
                  debug=False
                  ):

        design_name = design_file.split(".v")[0].split(".sv")[
            0].split("/")[-1]

        if self.reload_bug_inserter or not self.bug_inserter.is_file_loaded():
            print(design_file)
            cache_file_path = os.path.join(
                output_dir, "caches", design_name.rsplit("_", 1)[0] + ".pkl")
            self.bug_inserter.load_verilog(design_file, cache_file_path, rois)
            self.reload_bug_inserter = False

        design_extension = design_file.split(".")[-1]
        for i in range(num_bugs):
            try:
                mut_rec = self.current_bug[i]
                outpath = str(os.path.join(
                    output_dir, design_name + f'.{design_extension}'))
                _, mutation_desc = self.bug_inserter.insert_bug(
                    out_file=outpath, mut_rec=mut_rec)

                mut_rec.module_path = design_name
                for roi in self.rois:
                    if roi.includes(mut_rec.line_number):
                        mut_rec.in_roi = True
                        mut_rec.roi_id = roi.id
                        mut_rec.roi_size_lines = roi.length()

                print(f'-- Inserted bug {i+1}/{num_bugs} -> {mutation_desc}')
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
        print('we are here')
        # Hardcoded worker index for now
        worker_index = 1

        llm_dir_path = f"{self.root_path}/vcd_extract/llm"
        prompt_dir = f"{llm_dir_path}/prompts"
        self.bug_inserter = BugInserter(
            self.gpt, prompt_dir, debug=True, clear_cache=clear_bug_inserter_cache)

        # Original instance path
        original_instance_path = f"{self.root_path}/designs/{self.design_name}"
        original_instance_path_rtl = f"{original_instance_path}/hw/ip/{self.ip_name}/rtl"

        # Design instance path
        design_instance = f"{self.design_name}_{worker_index}"
        design_instance_path = f"{self.root_path}/designs/{design_instance}"
        design_instance_path_rtl = f"{design_instance_path}/hw/ip/{self.ip_name}/rtl"

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

        # Load ROIs
        verilog_name = filename.split('.')[0]
        rois_list = area_config["rois"] if "rois" in area_config else []
        self.rois = [
            ROI(
                id=f'roi_{verilog_name}_{i}',
                start_line=int(roi.split('-')[0]),
                end_line=int(roi.split('-')[1]),
            )
            for i, roi in enumerate(rois_list)
        ]

        split_rois = area_config["split_rois"] if "split_rois" in area_config else False
        rois_encoded = [
            (roi.start_line, roi.end_line)
            for roi in self.rois
        ]

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
                    continue  # Skip to the next file
                else:
                    print(
                        f"{current_bug_filepath} does not exist. Making a copy of the original file...")
                    copy_file(source_file=original_filepath,
                              target_file=current_bug_filepath)

            self.current_bug = []
            for i in range(num_bugs_per_try):
                self.current_bug.append(
                    MutationRecord(
                        mutation_id=f"mut_{current_label}_{i}",
                        bug_scenario_id=current_label,
                        design_id='opentitan',
                        module_path='',
                        mutation_class='',
                        line_number=0,
                        original_line='',
                        mutated_line='',
                        mutation_applied_successfully=False,
                        num_retries=0,
                        timestamp_first_attempt=datetime.now(),
                        timestamp_final_success=None,
                        generation_time_ms=0,
                        validation_time_ms=0,
                        rollback_time_ms=0,
                        in_roi=False,
                        roi_id='',
                        roi_size_lines=0,
                        validation_passed=False,
                        failure_signature=None,
                        signature_class=None
                    )
                )

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
                    rois=rois_encoded if split_rois else None,
                    model="gpt",
                    debug=self.verbose)

                val_t0 = time.time()
                # Put the mutated file in the design instance path
                copy_file(source_file=current_bug_filepath,
                          target_file=instance_filepath)

                # Run simulation
                result = self.run_sim_and_extract(design_instance_path=design_instance_path,
                                                  current_label=current_label, reruns=reruns, extract_vcd_bool=False, generate_bugs_worker_mode=True)

                val_t1 = time.time()
                for mutation in self.current_bug:
                    val_time_ms = (val_t1 - val_t0) * 1000
                    mutation.validation_time_ms += val_time_ms
                    if curr_try > 0:
                        mutation.rollback_time_ms += val_time_ms

                if result is not None:
                    result_code = result["code"]
                    result_message = result["message"]
                    failed_ip_log_path = result["failed_ip_log_path"]
                    print(f"Result code: {result_code}")
                    print(f"Result message: {result_message}")
                    print(f"Failed IP log path: {failed_ip_log_path}")
                else:
                    print(
                        f"Error: Simulation result is None for {current_label}")

                time.sleep(10)  # Wait a 10 seconds for clean up between runs

                # Check result
                if result_code < 0:  # compilation, simulation, or extraction error
                    if result_code == -1:  # compilation error
                        msg = f"Compilation error for {current_label}"
                    elif result_code == -2:
                        msg = f"Extraction error for {current_label}"
                    else:
                        msg = f"Simulation error for {current_label}"
                    print(msg)

                elif result_code == 0:  # simulation completed successfully
                    failed_ip_log_path = result["failed_ip_log_path"]
                    # If there is only default folder in the failed_ip_log_path
                    if len(os.listdir(failed_ip_log_path)) == 1 and "default" in os.listdir(failed_ip_log_path):
                        print(
                            f"Syntax error for current iteration of {current_label}")
                        # Find the build.log in failed_ip_log_path
                        build_log_path = find_full_path(
                            root_path=f"{failed_ip_log_path}/default", filename="build.log")

                        # Find all the first Error in the build.log and print all the lines below it
                        with open(build_log_path, "r") as f:
                            lines = f.readlines()
                            for i, line in enumerate(lines):
                                if "Error" in line:
                                    print(f"Error: {line}")
                                    print("".join(lines[i+1:]))
                                    break
                    # Check if failed_ip_log_path folder is empty or does not exist
                    elif len(os.listdir(failed_ip_log_path)) < self.acceptance_threshold or not os.path.exists(failed_ip_log_path):
                        print(f"Bug not detected for {current_label}")
                    else:
                        for mutation in self.current_bug:
                            mutation.validation_passed = True
                            mutation.mutation_applied_successfully = curr_try == 0
                        self.bug_detected = True
                        print(f"Bug detected for {current_label}")
                        design_name = current_bug_filepath.split(
                            ".v")[0].split(".sv")[0].split("/")[-1]
                        caches_path = os.path.join(bugdb_label_path, "caches")
                        if not os.path.exists(caches_path):
                            os.makedirs(caches_path)
                        self.bug_inserter.save_cache(cache_file=os.path.join(
                            caches_path, design_name.rsplit("_", 1)[0] + ".pkl"))

                if not self.bug_detected:
                    print('Failed to detect bug. Rolling back mutation')
                    for i in range(num_bugs_per_try):
                        self.bug_inserter.undo_mutation()
                        self.current_bug[i].validation_passed = False
                        self.current_bug[i].mutation_applied_successfully = False
                        self.current_bug[i].num_retries += 1

                # Remove failed_ip_log_path
                subprocess.run(f"rm -rf {failed_ip_log_path}/../*", shell=True)
                curr_try += 1

            # If bug not detected by the end, delete the current_bug_filepath and record the bug name to failed_to_insert_bug_names
            if not self.bug_detected:
                self.failed_to_insert_bug_names.append(current_label)
                print(
                    f"Failed to insert bug for {current_label}. Will try again.")
                settings.append(setting)
                self.current_bug.clear()

            else:
                for mutation in self.current_bug:
                    mutation.validation_passed = True
                    mutation.timestamp_final_success = datetime.now()
                    self.mutation_logger.log_mutation(mutation)
                    self.mutation_logger.save_to_csv()
                    print(f'Logging mutation {mutation}')
                self.current_bug.clear()

            # Replace the entire folder with the original folder to remove the injected bugs
            copy_folder(source_folder=original_instance_path_rtl,
                        target_folder=design_instance_path_rtl)

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
        original_instance_path_rtl = f"{original_instance_path}/hw/ip/{self.ip_name}/rtl"

        # Design instance path
        design_instance = f"{self.design_name}_{worker_index}"
        design_instance_path = f"{self.root_path}/designs/{design_instance}"
        design_instance_path_rtl = f"{design_instance_path}/hw/ip/{self.ip_name}/rtl"

        # if the instance path does not exist, create it
        if not os.path.exists(design_instance_path):
            print(f"Creating workspace {design_instance_path}")
            os.system(f"cp -r {original_instance_path} {design_instance_path}")
            assert os.path.exists(
                design_instance_path), f"Failed to create workspace {design_instance_path}"
            print(f"Workspace {design_instance_path} is created successfully")

        # Get path to file for injecting bugs
        filename = area_config["filename"]
        instance_filepath = find_full_path(
            root_path=design_instance_path_rtl, filename=filename)
        original_filepath = find_full_path(
            root_path=original_instance_path_rtl, filename=filename)

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

        # Inject bugs
        copy_file(source_file=current_bug_filepath,
                  target_file=instance_filepath)

        # Run simulation
        result = self.run_sim_and_extract(design_instance_path=design_instance_path,
                                          current_label=current_label, reruns=reruns, extract_vcd_bool=True,
                                          extract_signal_list=extract_signal_list
                                          )

        if result is not None:
            result_code = result["code"]
            result_message = result["message"]
            failed_ip_log_path = result["failed_ip_log_path"]
            print(f"Result code: {result_code}")
            print(f"Result message: {result_message}")
            print(f"Failed IP log path: {failed_ip_log_path}")
        else:
            print(f"Error: Simulation result is None for {current_label}")

        # Check result
        if result_code == -1:  # compilation error
            print(f"Compilation error for {current_label}")
        elif isinstance(result, dict):
            failed_ip_log_path = result["failed_ip_log_path"]
            # If there is only default folder in the failed_ip_log_path
            if len(os.listdir(failed_ip_log_path)) == 1 and "default" in os.listdir(failed_ip_log_path):
                print(
                    f"Syntax error for current iteration of {current_label}")
                # Find the build.log in failed_ip_log_path
                build_log_path = find_full_path(
                    root_path=f"{failed_ip_log_path}/default", filename="build.log")

                # Find all the first Error in the build.log and print all the lines below it
                with open(build_log_path, "r") as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines):
                        if "Error" in line:
                            print(f"Error: {line}")
                            print("".join(lines[i+1:]))
                            break
            elif len(os.listdir(failed_ip_log_path)) < self.acceptance_threshold or not os.path.exists(failed_ip_log_path):
                print(f"Bug not detected for {current_label}")
            else:
                print(f"Bug detected for {current_label}")

        # Wait a 10 seconds for clean up between runs
        time.sleep(10)

        # Replace the file with the original file to remove the injected bugs
        copy_file(source_file=original_filepath,
                  target_file=instance_filepath)

        # Wait a 10 seconds for clean up between runs
        time.sleep(10)

        # Remove failed_ip_log_path
        subprocess.run(f"rm -rf {failed_ip_log_path}/../*", shell=True)

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
