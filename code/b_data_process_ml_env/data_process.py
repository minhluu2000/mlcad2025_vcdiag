from sktime.transformations.series.summarize import SummaryTransformer
import os
import shutil
import multiprocessing
import math

import pandas as pd

from b_data_process_ml_env.utils.process import raw_data_to_rough_data, rough_data_to_summarized_data, rough_data_to_embedding_data
from b_data_process_ml_env.utils.process import get_max_length, get_mean_length, get_median_length
from b_data_process_ml_env.utils.package import package_data
from a_bug_injection_vcd_extract.workflows.workflow_utils import copy_folder, combine_ranges

import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=pd.errors.PerformanceWarning)


class DataProcess:
    def __init__(self,
                 data_storage_path,
                 data_process_config,
                 njobs
                 ):

        data_path = data_storage_path

        self.raw_data_path = f"{data_path}/raw_data"
        self.rough_data_path = f"{data_path}/rough_data"
        self.processed_uncompressed_data_path = f"{data_path}/processed_uncompressed_data"
        self.processed_summarized_data_path = f"{data_path}/processed_summarized_data"
        self.final_data_path_train = f"{data_path}/final_data/train"
        self.final_data_path_test = f"{data_path}/final_data/test"

        # Config
        self.data_process_config = data_process_config
        self.copy_raw_data = data_process_config["copy_raw_data"]
        self.split_mode = data_process_config["split_mode"]
        self.before_failure_timeframe = data_process_config["before_failure_timeframe"]
        self.pad_value = data_process_config["pad_value"]
        self.sv_logic_values = data_process_config["sv_logic_values"]
        self.ignore_files = data_process_config["ignore_files"]

        # Set up preprocessing transformers
        # summary_function = ['mean', 'min', 'max', 'median', 'sum',
        #                     'skew', 'kurt', 'var', 'std', 'mad', 'sem', 'nunique', 'count']
        summary_function = data_process_config["transformer"]["summary_function"]
        quantiles = data_process_config["transformer"]["quantiles"]

        # Get processing cores from arguments
        self.njobs = njobs

        # Set up transformers
        if len(summary_function) == 0:
            summary_transformer = SummaryTransformer(quantiles=quantiles)
        elif len(quantiles) == 0:
            summary_transformer = SummaryTransformer(
                summary_function=summary_function)
        elif len(summary_function) == 0 and len(quantiles) == 0:
            summary_transformer = SummaryTransformer()
        else:
            summary_transformer = SummaryTransformer(
                summary_function=summary_function, quantiles=quantiles)
        self.transformers = [
            summary_transformer
        ]

        print(f"Summary function: {summary_function}")

        self.ignore_files_list = []
        # check that ignore_files is not empty
        if len(self.ignore_files) == 0:
            print("Files to ignore: None")
        else:
            for label, areas_config in self.ignore_files.items():
                for area_config in areas_config:
                    training_ranges_list = area_config["training_ranges"]
                    testing_ranges_list = area_config["testing_ranges"]

                    training_ranges = combine_ranges(training_ranges_list)
                    testing_ranges = combine_ranges(testing_ranges_list)

                    self.ignore_files_list = self.ignore_files_list + \
                        [f"{label}{num}" for num in training_ranges]
                    self.ignore_files_list = self.ignore_files_list + \
                        [f"{label}{num}T" for num in testing_ranges]

        print(f"Files to ignore: {self.ignore_files_list}")

        # mean_length = get_mean_length(self.raw_data_path)
        # mean_length = math.ceil(mean_length)
        # self.before_failure_timeframe = mean_length
        print(f"Found length: {self.before_failure_timeframe}")

    def setup_storage_directories(self):
        if not os.path.exists(self.raw_data_path):
            os.makedirs(self.raw_data_path)
        for path in [self.rough_data_path, self.processed_uncompressed_data_path, self.processed_summarized_data_path, self.final_data_path_train, self.final_data_path_test]:
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)
            # Check if the directory is empty
            if not os.listdir(path):
                print(f"{path} is empty")
            else:
                print(f"{path} is not empty")

    def process_raw_data(self):
        # raw folders = all folders, so exclude anything not a folder
        self.raw_folders_list = [f for f in os.listdir(self.raw_data_path) if os.path.isdir(
            os.path.join(self.raw_data_path, f)) and not f.startswith(".")]
        
        # remove ignore files from self.raw_folders_list
        self.raw_folders_list = [f for f in self.raw_folders_list if f not in self.ignore_files_list]        

        # Multiprocessing pool
        pool = multiprocessing.Pool(processes=self.njobs)

        for folder in self.raw_folders_list:
            pool.apply_async(raw_data_to_rough_data, args=(
                self.raw_data_path,
                self.rough_data_path,
                folder,
                self.before_failure_timeframe,
            ))
        pool.close()
        pool.join()

    def process_rough_data(self):
        # Multiprocessing pool
        pool = multiprocessing.Pool(processes=self.njobs)
        for folder in self.raw_folders_list:
            print("Processing folder: " + folder)
            pool.apply_async(rough_data_to_summarized_data,
                             args=(
                                 self.rough_data_path,
                                 self.processed_summarized_data_path,
                                 folder,
                                 self.split_mode,
                                 self.before_failure_timeframe,
                                 self.pad_value,
                                 self.transformers
                             )
                             )
        pool.close()
        pool.join()

    def package_data(self):
        package_data(self.processed_summarized_data_path,
                     self.final_data_path_train,
                     self.final_data_path_test,
                     )

    def run(self):
        self.setup_storage_directories()
        self.process_raw_data()
        self.process_rough_data()
        self.package_data()


if __name__ == "__main__":
    pass

