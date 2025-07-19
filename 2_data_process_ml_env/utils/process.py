import os
import re
import sys
import pandas as pd
import numpy as np
import traceback
import multiprocessing

from sktime.datatypes import check_raise, convert_to

from data_analysis.utils.hdf_store import read_hdf_wideDf, wideDf_to_hdf

from data_analysis.utils.embedding_pipeline.model_factory import get_embedding_model


def _make_gen(reader):
    b = reader(1024 * 1024)
    while b:
        yield b
        b = reader(1024 * 1024)


def _rawgencount(filename):
    f = open(filename, 'rb')
    f_gen = _make_gen(f.raw.read)
    return sum(buf.count(b'\n') for buf in f_gen)


def split_given_size(a, size):
    return np.split(a, np.arange(size, len(a), size))


def get_max_length(raw_data_path, logger=None):
    raw_folders = [f for f in os.listdir(
        raw_data_path) if not f.startswith('.')]
    print("Raw folders: " + str(raw_folders))
    largest_file_size = 0
    largest_file_path = ""

    for folder, _, files in os.walk(raw_data_path):
        for file in files:
            if file.endswith('.txt'):
                txt_path = os.path.join(folder, file)
                size = os.stat(txt_path).st_size
                if size > largest_file_size:
                    largest_file_size = size
                    largest_file_path = txt_path

    dataframe = pd.read_csv(
        largest_file_path, delim_whitespace=True, header=None, low_memory=False)
    max_len = dataframe.shape[0]

    return max_len


def get_mean_length(raw_data_path, logger=None):
    raw_folders = [f for f in os.listdir(
        raw_data_path) if not f.startswith('.')]
    print("Raw folders: " + str(raw_folders))
    total_len = 0
    total_files = 0
    for folder in raw_folders:
        folder_path = f"{raw_data_path}/{folder}"
        for file in os.listdir(folder_path):
            if file.endswith('.txt'):
                txt_path = os.path.join(folder_path, file)
                print(f"Processing file: {txt_path}")
                file_length = _rawgencount(txt_path)
                total_len += file_length
                total_files += 1

    return total_len / total_files


def get_median_length(raw_data_path, logger=None):
    raw_folders = [f for f in os.listdir(
        raw_data_path) if not f.startswith('.')]
    print("Raw folders: " + str(raw_folders))
    lengths = []
    for folder in raw_folders:
        folder_path = f"{raw_data_path}/{folder}"
        for file in os.listdir(folder_path):
            if file.endswith('.txt'):
                txt_path = os.path.join(folder_path, file)
                print(f"Processing file: {txt_path}")
                file_length = _rawgencount(txt_path)
                lengths.append(file_length)

    median_length = np.median(lengths)
    print(f"Median length: {median_length}")
    return median_length


def raw_data_to_rough_data(raw_data_path,
                           rough_data_path,
                           folder_name,
                           before_failure_timeframe,
                           largest_possible_val=2**32 - 1,
                           sv_logic_values={"x": 120, "z": 122}
                           ):

    raw_folder_path = f"{raw_data_path}/{folder_name}"
    raw_files = [f for f in os.listdir(raw_folder_path) if f.endswith('.txt')]

    print("Files to process: " + str(raw_files))

    # If path not exist, create it
    rough_data_path = f"{rough_data_path}/{folder_name}"
    if not os.path.exists(rough_data_path):
        os.makedirs(rough_data_path)
    # If path already exist, clean everything inside
    else:
        for f in os.listdir(rough_data_path):
            os.remove(os.path.join(rough_data_path, f))

    # Skip file with name "all_signals.txt"
    if "all_signals.txt" in raw_files:
        raw_files.remove("all_signals.txt")

    for file in raw_files:
        txt_path = os.path.join(raw_folder_path, file)

        file_delimiter_line = -1
        # Go through file to find line with = delimiter
        with open(txt_path, 'r') as f:
            for line_num, line in enumerate(f):
                if '=' in line:
                    file_delimiter_line = line_num
                    break

        if file_delimiter_line == -1:
            raw_dataframe = pd.read_csv(
                txt_path, delim_whitespace=True, header=None, low_memory=False)
        else:
            raw_dataframe = pd.read_csv(
                txt_path, delim_whitespace=True, skiprows=file_delimiter_line+1, header=None, low_memory=False)

        # Keep the last before_failure_timeframe rows
        raw_dataframe = raw_dataframe.tail(before_failure_timeframe)

        # First column is time
        raw_dataframe.rename(columns={0: 'time'}, inplace=True)

        # Convert x and z from column 1 to the end to 120 and 122
        for col in raw_dataframe.columns[1:]:
            raw_dataframe[col] = raw_dataframe[col].apply(
                lambda x: ord(x) if x in sv_logic_values.keys() else x)

        # Convert strings to hex
        for col in raw_dataframe.columns[1:]:
            raw_dataframe[col] = raw_dataframe[col].apply(
                lambda x: int(x, 16) if type(x) == str else x)

        # Add 1 to 0 and 1 values
        for col in raw_dataframe.columns[1:]:
            raw_dataframe[col] = raw_dataframe[col].apply(
                lambda x: x + 1 if x in [0, 1] else x)

        # Set all values greater than int to int
        for col in raw_dataframe.columns[1:]:
            raw_dataframe[col] = raw_dataframe[col].apply(
                lambda x: x if x <= largest_possible_val else largest_possible_val)

        # Convert all columns to int
        try:
            for col in raw_dataframe.columns:
                raw_dataframe[col] = raw_dataframe[col].astype(int)
        except Exception as e:
            print(f"Error in processing file: {txt_path}")
            print(traceback.format_exc())
            print(raw_dataframe)
            continue

        raw_dataframe.rename(columns={'time': 0}, inplace=True)

        print(f"Raw dataframe shape for file {file}: {raw_dataframe.shape}")

        # Export to hdf
        wideDf_to_hdf(os.path.join(
            rough_data_path, file.replace(".txt", "_rough.h5")), raw_dataframe)


def rough_data_to_summarized_data(rough_data_path,
                                  processed_data_path,
                                  folder_name,
                                  split_size,
                                  pad_value,
                                  transformers
                                  ):

    # Get fork process number
    process_name = multiprocessing.current_process().name
    print(f"Process name: {process_name}")
    worker_index = process_name.split("-")[-1]

    print(f"Worker index: {worker_index} received folder: {folder_name}")

    # Check if folder is empty, if so, skip
    print("Checking if folder is empty: " + folder_name)
    rough_data_path = f"{rough_data_path}/{folder_name}"
    if len(os.listdir(rough_data_path)) == 0:
        print("Folder is empty, skipping: " + folder_name)
        return

    dataframe_list = []

    processed_files = [f for f in os.listdir(
        rough_data_path) if f.endswith('.h5') and f != 'labels.txt']

    print("Files to process: " + str(processed_files))

    # If path not exist, create it
    processed_data_path = f"{processed_data_path}/{folder_name}"
    if not os.path.exists(processed_data_path):
        os.makedirs(processed_data_path)
    # If path already exist, clean everything inside
    else:
        for f in os.listdir(processed_data_path):
            os.remove(os.path.join(processed_data_path, f))

    instance = 0
    for file in processed_files:
        df = read_hdf_wideDf(os.path.join(rough_data_path, file))

        # Drop rows with some NaN or inf values
        df = df.dropna()
        # Convert df to int
        try:
            df = df.astype(int)
        except ValueError:
            print(folder_name, file)
            raise
        # Get the last split_size rows
        df = df.tail(split_size)
        # Reset index
        df.reset_index(drop=True, inplace=True)
        # If the length is less than split_size, pad it with pad_value
        if len(df) < split_size:
            df = pd.DataFrame(
                np.pad(df, ((0, split_size - len(df)), (0, 0)), constant_values=pad_value))
        # Convert df to numpy array
        df_array = df.to_numpy()
        # Add instance column
        df_array = np.insert(df_array, 0, instance, axis=1)
        # Add time column
        df_array = np.insert(df_array, 1, range(df_array.shape[0]), axis=1)
        # Convert to int
        df_array = df_array.astype(int)
        # Append to list
        dataframe_list.append((file, df_array))
        instance += 1

    # Get the dataframe with the smallest length
    try:
        cols = ["instances", "time_points"] + \
            [f"{i}" for i in range(1, dataframe_list[0][1].shape[1]-1)]
    except Exception as e:
        # print(folder_name, file)
        print(
            f"Error in processing file: {file} with folder name: {folder_name}")
        print(traceback.format_exc())
        return

    processed_df = pd.concat([pd.DataFrame(df[1], columns=cols)
                             for df in dataframe_list]).set_index(["instances", "time_points"])

    # Display full processed_df
    # Check if second index is motonically increasing
    # check_raise(processed_df, mtype="pd-multiindex")

    # convert to nested_univ
    # univ_processed_df = convert_to(processed_df, to_type="nested_univ")
    univ_processed_df_transformed = processed_df

    # Apply transformers
    for transformer in transformers:
        univ_processed_df_transformed = transformer.fit_transform(
            univ_processed_df_transformed)

    # print the first 5 rows of the transformed dataframe
    print(univ_processed_df_transformed.head())
    # print columns of the transformed dataframe
    print(univ_processed_df_transformed.columns)

    wideDf_to_hdf(os.path.join(
        processed_data_path, f"{folder_name}_processed.h5"), univ_processed_df_transformed)

    # Export to csv
    # univ_processed_df_transformed.to_csv(os.path.join(
    #     processed_data_path, f"{folder_name}_processed.csv"))

    # y_train is the same label for all instances
    # find the everything after a number in the file name and remove the rest (split by first number)
    # get label from folder name
    match = re.match(r"([a-z]+)([0-9]+)", folder_name, re.I)
    if match:
        items = match.groups()
    bug_label = items[0]

    y_train = np.array([bug_label for i in range(len(dataframe_list))])

    # Store labels in a txt file in the same directory
    with open(os.path.join(processed_data_path, "labels.txt"), "w") as f:
        for label in y_train:
            f.write(label + "\n")

    # Log the number of instances processed
    print(f"Data processed for folder {folder_name} by worker {worker_index})")


def rough_data_to_nonsummarized_data(rough_data_path,
                                     processed_data_path,
                                     folder_name,
                                     last_n_rows,
                                     pad_value,
                                     transformers,
                                     logger
                                     ):

    # Check if folder is empty, if so, skip
    print("Checking if folder is empty: " + folder_name)
    if len(os.listdir(rough_data_path + folder_name)) == 0:
        print("Folder is empty, skipping: " + folder_name)
        return

    print("Processing rough data for folder_name: " + folder_name)

    dataframe_list = []

    processed_files = [f for f in os.listdir(
        rough_data_path + folder_name) if f.endswith('.h5')]

    print("Files to process: " + str(processed_files))

    instance = 0
    for file in processed_files:
        # Get the last last_n_rows
        df = df.tail(last_n_rows)
        # Reset index
        df.reset_index(drop=True, inplace=True)
        # If the length is less than last_n_rows, pad it with pad_value
        if len(df) < last_n_rows:
            df = pd.DataFrame(
                np.pad(df, ((0, last_n_rows - len(df)), (0, 0)), constant_values=pad_value))
        # Convert df to numpy array
        df_array = df.to_numpy()
        # Add instance column
        df_array = np.insert(df_array, 0, instance, axis=1)
        # Add time column
        df_array = np.insert(df_array, 1, range(df_array.shape[0]), axis=1)
        # Convert to int
        df_array = df_array.astype(int)
        # Append to list
        dataframe_list.append((file, df_array))
        instance += 1

    # Get the dataframe with the smallest length
    try:
        cols = ["instances", "time_points"] + \
            [f"{i}" for i in range(1, dataframe_list[0][1].shape[1]-1)]
    except:
        print(folder_name, file)
        # stop cell execution
        raise

    processed_df = pd.concat([pd.DataFrame(df[1], columns=cols)
                             for df in dataframe_list]).set_index(["instances", "time_points"])

    # Display full processed_df
    # Check if second index is motonically increasing
    check_raise(processed_df, mtype="pd-multiindex")

    # convert to nested_univ
    univ_processed_df = convert_to(processed_df, to_type="nested_univ")

    wideDf_to_hdf(os.path.join(
        processed_data_path + folder_name, f"{folder_name}_processed.h5"), univ_processed_df, logger=logger)

    # y_train is the same label for all instances
    # find the everything after a number in the file name and remove the rest (split by first number)
    # get label from folder name
    match = re.match(r"([a-z]+)([0-9]+)", folder_name, re.I)
    if match:
        items = match.groups()
    bug_label = items[0]

    y_train = np.array([bug_label for i in range(len(dataframe_list))])

    # Store labels in a txt file in the same directory
    with open(os.path.join(processed_data_path + folder_name, "labels.txt"), "w") as f:
        for label in y_train:
            f.write(label + "\n")


def rough_data_to_embedding_data(
    rough_data_path,
    processed_data_path,
    folder_name,
    split_size,
    pad_value,
    embedding_model_name="ts2vec",
    output_dims=512
):
    def log(msg):
        print(f"[{multiprocessing.current_process().name}] {msg}")

    worker_index = multiprocessing.current_process().name.split("-")[-1]
    log(f"Worker index: {worker_index} received folder: {folder_name}")

    folder_path = os.path.join(rough_data_path, folder_name)
    if not os.listdir(folder_path):
        log(f"Folder is empty, skipping: {folder_name}")
        return

    processed_files = [
        f for f in os.listdir(folder_path)
        if f.endswith('.h5') and f != 'labels.txt'
    ]
    log(f"Files to process: {processed_files}")

    output_folder = os.path.join(processed_data_path, folder_name)
    os.makedirs(output_folder, exist_ok=True)
    for f in os.listdir(output_folder):
        os.remove(os.path.join(output_folder, f))

    dataframe_list = []
    for instance, file in enumerate(processed_files):
        df = read_hdf_wideDf(os.path.join(folder_path, file)).dropna()
        try:
            df = df.astype(int)
        except ValueError:
            log(f"ValueError in file: {file}")
            raise

        df = df.tail(split_size).reset_index(drop=True)
        if len(df) < split_size:
            df = pd.DataFrame(
                np.pad(df, ((0, split_size - len(df)), (0, 0)),
                       constant_values=pad_value)
            )

        df_array = df.to_numpy()
        df_array = np.insert(df_array, 0, instance, axis=1)
        df_array = np.insert(df_array, 1, range(df_array.shape[0]), axis=1)
        dataframe_list.append((file, df_array.astype(int)))

    try:
        num_features = dataframe_list[0][1].shape[1] - 2
        cols = ["instances", "time_points"] + \
            [f"{i}" for i in range(1, num_features + 1)]
    except Exception:
        log(f"Error in processing file: {file} with folder name: {folder_name}")
        log(traceback.format_exc())
        return

    processed_df = pd.concat(
        [pd.DataFrame(df[1], columns=cols) for df in dataframe_list]
    ).set_index(["instances", "time_points"])

    embedding_model = get_embedding_model(
        embedding_model_name,
        input_dims=processed_df.shape[1],
        output_dims=output_dims
    )

    embeddings_list = []
    instance_ids = processed_df.index.get_level_values(0).unique()
    for instance_id in instance_ids:
        instance_df = processed_df.loc[instance_id].values
        embedding = embedding_model.encode(instance_df)
        embeddings_list.append(embedding)

    embedding_columns = [f"embedding_{i}" for i in range(output_dims)]
    embeddings_df = pd.DataFrame(
        embeddings_list, index=instance_ids, columns=embedding_columns)
    print(embeddings_df.head())

    wideDf_to_hdf(os.path.join(
        output_folder, f"{folder_name}_processed.h5"), embeddings_df)

    match = re.match(r"([a-z]+)([0-9]+)", folder_name, re.I)
    bug_label = match.groups()[0] if match else "unknown"
    y_train = [bug_label] * len(dataframe_list)

    with open(os.path.join(output_folder, "labels.txt"), "w") as f:
        f.writelines(label + "\n" for label in y_train)

    log(f"Data processed for folder {folder_name} by worker {worker_index}")
