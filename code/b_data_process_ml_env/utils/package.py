import os
import pandas as pd
import math
from b_data_process_ml_env.utils.hdf_store import read_hdf_wideDf, wideDf_to_hdf
from natsort import natsorted


def package_data(processed_bug_data_path,
                 final_bug_data_path_train,
                 final_bug_data_path_test,
                 ):

    IGNORE_LIST = [".DS_Store"]
    TEST_LIST = [folder for folder in os.listdir(
        processed_bug_data_path) if folder not in IGNORE_LIST and "T" in folder]

    print("Test list: " + str(TEST_LIST))

    print("Train dataset processing...")
    train_folder_dir_list = {}
    # Train dataset processing
    # Go through each folder in processed_bug_data_path
    for folder in os.listdir(processed_bug_data_path):
        print("Processing folder: " + folder)
        processed_bug_data_path_folder = f"{processed_bug_data_path}/{folder}"
        # Check if folder is in test list or ignore list or empty
        if folder in TEST_LIST or folder in IGNORE_LIST or len(os.listdir(processed_bug_data_path_folder)) == 0:
            print("Skipping " + folder + " for training")
            continue
        # Print folder name
        for file in os.listdir(processed_bug_data_path_folder):
            processed_bug_data_path_folder_file = f"{processed_bug_data_path_folder}/{file}"
            print("Processing file: " + file)
            if train_folder_dir_list.get(folder) is None:
                train_folder_dir_list[folder] = [
                    processed_bug_data_path_folder_file]
            else:
                train_folder_dir_list[folder].append(
                    processed_bug_data_path_folder_file)

    test_folder_dir_list = {}
    # Test dataset processing
    # Go through each folder in processed_bug_data_path
    for folder in os.listdir(processed_bug_data_path):
        processed_bug_data_path_folder = f"{processed_bug_data_path}/{folder}"
        if folder not in TEST_LIST or folder in IGNORE_LIST or len(os.listdir(processed_bug_data_path_folder)) == 0:
            print("Skipping " + folder + " for testing")
            continue
        # Print folder name
        for file in os.listdir(processed_bug_data_path_folder):
            processed_bug_data_path_folder_file = f"{processed_bug_data_path_folder}/{file}"
            if test_folder_dir_list.get(folder) is None:
                test_folder_dir_list[folder] = [
                    processed_bug_data_path_folder_file]
            else:
                test_folder_dir_list[folder].append(
                    processed_bug_data_path_folder_file)

    train_label_df_list = []
    test_label_df_list = []

    for folder in train_folder_dir_list:
        file_paths = train_folder_dir_list[folder]
        for path in file_paths:
            if path.endswith(".txt"):
                train_label_df_list.append(pd.read_csv(path, header=None))

    for folder in test_folder_dir_list:
        file_paths = test_folder_dir_list[folder]
        for path in file_paths:
            if path.endswith(".txt"):
                test_label_df_list.append(pd.read_csv(path, header=None))

    # Print the list of all headers in the dataset

    # Get all unique classes
    class_stats = {}
    unique_classes = set()
    for label_df in train_label_df_list:
        unique_classes.update(label_df[0].unique())

    # For each class, count the frequency of each class in the dataset
    for label_df in train_label_df_list:
        for class_name in unique_classes:
            class_stats[class_name] = class_stats.get(
                class_name, 0) + len(label_df[label_df[0] == class_name])

    # print("Class stats: " + str(class_stats))
    print("Class stats: " + str(class_stats))

    train_data_df_list = []
    for folder in train_folder_dir_list:
        file_paths = train_folder_dir_list[folder]
        for path in file_paths:
            if path.endswith(".h5"):
                try:
                    train_data_df_list.append(read_hdf_wideDf(path))
                except Exception as e:
                    print(f"Error reading {path}: {e}")
                    continue

    test_data_df_list = []
    for folder in test_folder_dir_list:
        file_paths = test_folder_dir_list[folder]
        for path in file_paths:
            if path.endswith(".h5"):
                try:
                    test_data_df_list.append(read_hdf_wideDf(path))
                except Exception as e:
                    print(f"Error reading {path}: {e}")
                    continue

    # Export training data to csv
    train_data_df_final = pd.concat(train_data_df_list)
    # Resort headers with natsort
    train_data_df_final = train_data_df_final.reindex(
        natsorted(train_data_df_final.columns), axis=1)
    train_data_df_final.to_csv(f"{final_bug_data_path_train}/data.csv")
    # Export label to csv
    train_label_df = pd.concat(train_label_df_list)
    train_label_df.to_csv(
        f"{final_bug_data_path_train}/label.csv", header=None)

    # Export testing data to csv
    test_data_df_final = pd.concat(test_data_df_list)
    # Resort headers with natsort
    test_data_df_final = test_data_df_final.reindex(
        natsorted(test_data_df_final.columns), axis=1)
    test_data_df_final.to_csv(f"{final_bug_data_path_test}/data.csv")
    # Export label to csv
    test_label_df = pd.concat(test_label_df_list)
    test_label_df.to_csv(f"{final_bug_data_path_test}/label.csv", header=None)
