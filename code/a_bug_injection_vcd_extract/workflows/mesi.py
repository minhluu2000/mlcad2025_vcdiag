import os
import subprocess
import multiprocessing
import time
import signal

import logging
import vcdvcd

from contextlib import redirect_stdout
from io import StringIO

from vcd_extract.workflows.workflow_utils import find_full_path, combine_ranges, copy_file


class MESI:
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
        self.target_signals_path = target_signals_path
        self.data_path = data_path
        self.bugdb_path = bugdb_path
        self.njobs = njobs

        # Settings
        self.verbose = verbose

        if logger:
            self.logger = logger
        else:
            self.verbose = False  # disable verbose mode if logger is not provided
            pass

    def _check_buggy(self) -> bool:
        """
        Check whether the injected bug is detected by the TB.
        For MESI, 
        """
        # if self.timeout_counter > timeout_counter_threshold:
        #     return False
        return True

    def generate_signal_list(self):
        pass

    def extract_vcd(self,
                    vcd_path: str,
                    current_label: str,
                    line_limit: int):

        vcdvcd_callbacks = vcdvcd.PrintDumpsStreamParserCallbacks()

        with open(self.target_signals_path, "r") as f:
            target_signals = f.read().splitlines()

        with StringIO() as buf, redirect_stdout(buf):
            try:
                vcdvcd.VCDVCD(vcd_path, callbacks=vcdvcd_callbacks,
                              signals=target_signals)
            except Exception as e:
                print(f"Error: {e}")
                exit(1)
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

            del vcdvcd_output, signal_activities, buf

        # Write the file
        final_output_path = f"{self.data_path}/{current_label}/{os.path.basename(vcd_path).replace('.vcd', '.txt')}"
        print(f"Writing to {final_output_path}")
        with open(final_output_path, "w") as f:
            f.write(final_output)

        # Delete the vcd file to save space
        os.remove(vcd_path)

    def get_failed_logs(self) -> list:
        logs_path = f"{self.sim_path}/logs"
        analyze_bash = f"{logs_path}/analyze.bash"

        failed_logs = []

        if os.path.exists(analyze_bash):
            try:
                # Save the current working directory
                cwd = os.getcwd()

                # Change the current working directory to the location of the Bash script
                os.chdir(logs_path)

                # Run the Bash script and capture its output
                result = subprocess.run(
                    [analyze_bash], shell=True, check=True, capture_output=True)

                # Extract the output and convert it from byte to string
                output = result.stdout.decode('utf-8')

                # Replace ./ with the full path
                output = output.replace("./", logs_path + "/")

                # Put failed logs into the failed_logs list
                # Find the line number of the word "FAIL" in the output
                fail_index = [i for i, s in enumerate(
                    output.splitlines()) if 'FAIL' in s][0]
                # Find the line number of the word "QUIT" in the output
                quit_index = [i for i, s in enumerate(
                    output.splitlines()) if 'QUIT' in s][0]

                # Extract all lines below the line number of the word "FAIL" excluding the line with the word "FAIL"
                for line in output.splitlines()[fail_index+1:quit_index]:
                    failed_logs.append(line)

                # Extract all lines below the line number of the word "QUIT" excluding the line with the word "QUIT"
                for line in output.splitlines()[quit_index+1:]:
                    failed_logs.append(line)

                # Change the current working directory back to the original directory
                os.chdir(cwd)
            except subprocess.CalledProcessError as e:
                print("Bash script failed with error:", e)
            except Exception as e:
                print("Error:", e)
        else:
            print(f"The script '{analyze_bash}' does not exist.")
    
        return failed_logs

    def run_sim_and_extract(self,
                            current_label: str,
                            reruns: int = 1,
                            line_limit: int = 1000,
                            time_tag_before_failure_percent: int = 10,
                            extract_vcd: bool = False):
        if extract_vcd:
            # Create a folder for the current label
            if not os.path.exists(f"{self.data_path}/{current_label}"):
                os.makedirs(f"{self.data_path}/{current_label}")
            else:  # Clear the folder
                subprocess.run(
                    f"rm -rf {self.data_path}/{current_label}/*", shell=True)

        # cd into the sim directory
        os.chdir(self.sim_path)
        
        # Solve Permission denied by chmod current directory
        os.system(f"chmod -R 755 {self.sim_path}")

        # simulation command
        regress_bash = f"{self.sim_path}/regress.bash"
        simulation_cmd = f"{regress_bash} {reruns} 1"
        try:
            p = subprocess.Popen(simulation_cmd, shell=True)
            try:
                while p.poll() is None:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                p.terminate()
                raise
        except subprocess.CalledProcessError as e:
            print("Regression failed with error:", e)
            p.terminate()

        # Get failed logs
        self.failed_logs = self.get_failed_logs()
        print(f"Failed logs: {self.failed_logs}")
    

        # Extract VCD and store the data
        if extract_vcd:
            for log in self.failed_logs:
                fsdb_path = log.replace(".log", ".fsdb")
                if os.path.exists(fsdb_path):
                    # Execute the command to convert fsdb to vcd
                    fsdb2vcd_summary_cmd = f"fsdb2vcd {fsdb_path} -summary"
                    fsdb2vcd_cmd = f"fsdb2vcd {fsdb_path} -o {fsdb_path.replace('.fsdb', '.vcd')}"
                    fsdb_summary = subprocess.run(
                        [fsdb2vcd_summary_cmd], shell=True, check=True, capture_output=True)

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
                    final_interval = time_tag_start
                    fsdb2vcd_cmd = f"{fsdb2vcd_cmd}"

                    print(f"Converting {fsdb_path} to vcd...")
                    subprocess.run([fsdb2vcd_cmd], shell=True, check=True)

                    vcd_path = fsdb_path.replace('.fsdb', '.vcd')

                    self.extract_vcd(vcd_path=vcd_path,
                                     current_label=current_label,
                                     line_limit=line_limit)

    def generate_bugs_worker(self, label: str, area_config: dict):
        worker_index = multiprocessing.current_process().name.split("-")[-1]
        self.original_instance_path = f"{self.root_path}/designs/{self.design_name}"
        self.design_instance = f"{self.design_name}_{worker_index}"
        self.design_instance_path = f"{self.root_path}/designs/{self.design_instance}"
        self.sim_path = f"{self.design_instance_path}/sim.synopsys"

        # Get path to file for injecting bugs
        filename = area_config["filename"]
        instance_filepath = find_full_path(
            root_path=self.design_instance_path, filename=filename, keywords=["sim.synopsys"])
        original_filepath = find_full_path(
            root_path=self.original_instance_path, filename=filename, keywords=["sim.synopsys"])

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

        for training_index in training_ranges:
            # Generate bugs with LLM
            current_bug_filepath = f"{self.bugdb_path}/{label}/{filename.replace(f'.', f'_{training_index}.')}"
            current_label = f"{label}{training_index}"
            # Check if that file already exists
            if os.path.exists(current_bug_filepath):
                print(f"File {current_bug_filepath} already exists")
            else:
                print(f"{current_bug_filepath} does not exist")
                # For now, continue to the next file
                continue
                # Generate bugs

            # Inject bugs
            copy_file(source_file=current_bug_filepath,
                         target_file=instance_filepath)

            # Check syntax

            # Run simulation
            self.run_sim_and_extract(current_label=current_label, reruns=1)

            # Check if the bug is detected, keep the file if it is detected and restore the original state of the target file
            if self._check_buggy():
                print(f"Bug detected")
                copy_file(source_file=original_filepath,
                             target_file=instance_filepath)
            else:
                # Add more mutations to the same block
                print(f"Bug not detected")

        for testing_index in testing_ranges:
            # Generate bugs with LLM
            current_bug_filepath = f"{self.bugdb_path}/{label}/{filename.replace(f'.', f'_{testing_index}T.')}"
            current_label = f"{label}{testing_index}T"
            # Check if that file already exists
            if os.path.exists(current_bug_filepath):
                print(f"File {current_bug_filepath} already exists")
            else:
                print(f"{current_bug_filepath} does not exist")
                # For now, continue to the next file
                continue
                # Generate bugs

            # Inject bugs
            copy_file(source_file=current_bug_filepath,
                         target_file=instance_filepath)

            # Check syntax

            # Run simulation
            self.run_sim_and_extract(current_label=current_label, reruns=1)

            # Check if the bug is detected, keep the file if it is detected and restore the original state of the target file
            if self._check_buggy():
                print(f"Bug detected")
                copy_file(source_file=original_filepath,
                             target_file=instance_filepath)
            else:
                # Add more mutations to the same block
                print(f"Bug not detected")

    def insert_and_extract_worker(self,
                                           label: str,
                                           area_config: dict,
                                           index: int,
                                           reruns: int = 1,
                                           line_limit: int = 1000,
                                           time_tag_before_failure_percent: int = 10,
                                           training: bool = True):
        worker_index = multiprocessing.current_process().name.split("-")[-1]
        self.original_instance_path = f"{self.root_path}/designs/{self.design_name}"
        self.design_instance = f"{self.design_name}_{worker_index}"
        self.design_instance_path = f"{self.root_path}/designs/{self.design_instance}"
        self.sim_path = f"{self.design_instance_path}/sim.synopsys"

        # Get path to file for injecting bugs
        filename = area_config["filename"]
        instance_filepath = find_full_path(
            root_path=self.design_instance_path, filename=filename)
        original_filepath = find_full_path(
            root_path=self.original_instance_path, filename=filename)

        if self.verbose:
            if len(instance_filepath) == 0:
                print(
                    f"File {filename} not found. This could be due to missing design instance.")
                print(f"Instance path: {self.design_instance_path}")
                return
            else:
                print(f"Full path: {instance_filepath}")

        if training:
            current_bug_filepath = f"{self.bugdb_path}/{label}/{filename.replace(f'.', f'_{index}.')}"
            current_label = f"{label}{index}"
        else:
            current_bug_filepath = f"{self.bugdb_path}/{label}/{filename.replace(f'.', f'_{index}T.')}"
            current_label = f"{label}{index}T"

        # Check if that file already exists
        if os.path.exists(current_bug_filepath):
            print(f"File {current_bug_filepath} already exists")
        else:
            print(f"{current_bug_filepath} does not exist")
            # For now, continue to the next file
            return

        # Inject bugs
        copy_file(source_file=current_bug_filepath,
                     target_file=instance_filepath)

        # Run simulation
        self.run_sim_and_extract(
            current_label=current_label,
            reruns=reruns,
            time_tag_before_failure_percent=time_tag_before_failure_percent,
            extract_vcd=True)

        # Replace back the original file
        copy_file(source_file=original_filepath,
                     target_file=instance_filepath)

    def generate_bugs(self, generate_bugs_config: dict):
        worker_pool = multiprocessing.Pool(self.njobs)
        bugs = generate_bugs_config["bugs"]
        for label, areas_config in bugs.items():
            generate_results = [worker_pool.apply_async(self.generate_bugs_worker, args=(
                label, area_config)) for area_config in areas_config]
            # wait for all the results to finish
            [result.wait() for result in generate_results]
        worker_pool.close()
        worker_pool.join()

    def insert_and_extract(self, insert_bugs_config: dict):
        worker_pool = multiprocessing.Pool(self.njobs)
        bugs = insert_bugs_config["bugs"]
        line_limit = extract_config["line_limit"]
        time_tag_before_failure_percent = extract_config["time_tag_before_failure_percent"]
        for label, areas_config in bugs.items():
            for area_config in areas_config:
                training_ranges_list = area_config["training_ranges"]
                testing_ranges_list = area_config["testing_ranges"]

                training_ranges = combine_ranges(training_ranges_list)
                testing_ranges = combine_ranges(testing_ranges_list)

                if self.verbose:
                    print(f"Training ranges: {training_ranges}")
                    print(f"Testing ranges: {testing_ranges}")

                reruns = area_config["reruns"]

                training_results = [worker_pool.apply_async(self.insert_and_extract_worker, args=(
                    label, area_config, training_index)) for training_index in training_ranges]

                testing_results = [worker_pool.apply_async(self.insert_and_extract_worker, args=(
                    label, area_config, testing_index, False)) for testing_index in testing_ranges]

        worker_pool.close()
        worker_pool.join()
