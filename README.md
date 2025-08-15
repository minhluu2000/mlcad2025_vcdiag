# Paper 8 - VCDiag: Classifying Erroneous Waveforms for Failure Triage Acceleration
## Also containing codes for Paper 17 - BugGen: A Self-Correcting Multi-Agent LLM Pipeline for Realistic RTL Bug Synthesis

This document outlines the setup and usage of **VCDiag**. The workflow involves two key stages:  
1. **Bug Injection and VCD Extraction**  
2. **VCD Processing and ML Training/Inference**

**Note**: Due to the lack of access to commercial simulators (e.g., Cadence Xcelium and Synopsys VCS), we provide **[pre-packaged OpenTitan and FabScalar designs](https://zenodo.org/records/16735572)** and **[raw VCD ASCII datasets](https://zenodo.org/records/16791965)** for running the data processing and ML flow. However, the details of bug injection and VCD extraction flow are explained here for adaptation to your own environment.

---

## Prerequisites

- Install **Python 3.12** on your Linux system.  
- Create two Python virtual environments:
  - `sim_extract` for bug injection and VCD extraction
  - `sim_ml` for VCD processing and ML operations  
- The dependencies for each environment are specified in `requirements.txt` files located in the `python_requirements` folder.

---

## Setup Instructions

### 1. Create Virtual Environments

Run the following commands in your terminal:

```bash
python3 -m venv sim_extract
python3 -m venv sim_ml
```

### 2. Activate Virtual Environments

Activate sim_extract:

```bash
source sim_extract/bin/activate
```

Activate sim_ml:

```bash
source sim_ml/bin/activate
```

Deactivate the environment once done:

```bash
deactivate
```

---

## Bug Injection and VCD Extraction Flow

### 1. Core Selection and Modes in `a_run_extract.sh`

- Select an appropriate number of cores. Each worker is assigned to a core, leaving two cores unused for other processes.
- Two available modes:
  - **generate_bugs**: LLM-powered bug injection and checking (single-core).
  - **insert_and_extract**: Bug insertion and waveform extraction (multi-core).

### 2. Flow Details:

The flow is driven by a configuration file for each design. For example, in the case of OpenTitan, the configuration file is duplicated and customized for each IP. To switch between configurations, simply overwrite the `opentitan.json` file. The script `a_extract.py` reads the design's config file and sets up the specific flow. The entire workflow for each design is contained in `a_bug_injection_vcd_extract/workflows/design.py`.

The workflow follows a standard bottom-up structure:  

- **generate_bugs** → **generate_bugs_worker** → **generator** → **run_sim_and_extract** → **extract_vcd** (check only)  
- **insert_and_extract** → **insert_and_extract_worker** → **run_sim_and_extract** → **extract_vcd** (check and extract)  

#### Generate Bugs:

The flow begins with injecting a bug into the design. If no signal list exists, the flow halts and provide you with a path to the VCD. You will need to run the `signal.py` script using the provided path. Update the configuration file to include this VCD file path and specify which modules to extract signals from. Set `generate_raw_signals` to `true` in the configuration file to generate the raw signal list. Once this is done, switch `generate_raw_signals` to `false` and run the flow again to generate the `target_signal_list`.

Once the `target_signal_list.txt` is ready, return to the injection flow. Refer to the original configuration file for details on specifying the module(s) to inject, the label name, the number of bugs to inject per scenario, and the total number of scenarios. You can define specific regions for the LLM to target during bug injection or allow it to partition the module automatically. Each bug scenario will be stored in the `a_bug_injection_vcd_extract/bugdb` directory.

**Notes**:  

- Create a secret file to store your OpenAI key.  
- Monitor the injection process during early phases to ensure it reaches terminal conditions. If the process keeps failing to inject bugs, address the issue to avoid wasting credits.  
- This is a single-core operation, so it will take time. However, this is a one-time cost, and you can use the pre-generated scenarios in `bugdb` for testing purposes.

#### Insert and Extract:

Similar to the **Generate Bugs** flow, this stage uses verified scenarios from the previous step, injects them into the design, runs multiple reseeds, and extracts all VCDs into raw ASCII representations. This pipeline is fully independent and, in theory, can scale infinitely. However, keep in mind the computational resources available, license limitations (as each worker runs an entire simulation flow), and storage quotas.

The final ASCII .txt are stored in a specified folder written in a_extract.py. Specific paths are written in `a_extract.py`. Leave them as they are or modify this file to your specific needs.

**Notes**:  

- In the configuration file, the `line_limit` parameter under the `sim_and_extract` settings specifies the number of simulation ticks to capture before failure. From the research paper, 2000 ticks is excessive, and ML prediction accuracy can be achieved with just 200 ticks. Reducing this value saves significant storage space.
- We provide a slightly modified version for each design, bundled with the datasets. These modifications are specific to environment configurations and test selection. For example, in the case of OpenTitan, only the verification `.hjson` file is adjusted to reduce the number of tests. The RTL and testbench (TB) remain unchanged.

### 3. Additional Info:

TBD

---

## VCD Processing and ML Training/Inference

### 1. Run the Flow

This stage is adapted from MLCAD's Artifact Submission Instructions. To run the flow:  

1. Extract the dataset and place it in the `data` folder.  
2. Perform a reproducible run to generate the final tabular data.  
3. To train and test the model, navigate to the `b_data_process_ml_env/ml_models` directory, select a model, update the paths as needed, and execute the Jupyter Notebook.

**Notes**:  

- This flow does not rely on proprietary tools and can be executed in any environment of your choice.  
- Once again, in `b_run_data.sh`, specify the number of cores and design. There's only one mode, `data_process`, and `ml_model` is for display only.
- Due to the large size of the datasets, they exceed CodeOcean's storage quota. You will need to download both the dataset and the flow and execute them locally. Make sure to change `data_storage_path = f"{root_path}/../data"` in `b_data.py` to point to where the data folder is.

### 2. About the Flow

The flow consists of two main stages: **Processing** and **ML Training/Inference**.

For the **processing** step, raw VCD data goes through:

- **Raw VCD** → **Clean and trim** → **Statistical compression** → **Final tabular dataset**

While trimming is not strictly necessary, since statistical compression reduces each VCD of *n* signals to a single *n*-dimensional datapoint, we include it to support potential use in time-series deep learning models.

The final tabular dataset can be used in any **ML training/inference** pipeline, such as Jupyter Notebook. Thanks to the standardized VCD format, this flow operates consistently across all designs, eliminating the need for design-specific scripts as in the bug injection and vcd extraction stage.

**Program Flow**:  
- **b_data.py** → **b_data_process_ml_env/data_process.py** → **process_raw_data** → **process_rough_data** → **package_data**  
(All functions are located in `b_data_process_ml_env/utils`.)

The data processing pipeline is parallelized. Ensure you specify the number of cores to use in `b_run_data.sh`.

### 3. Explain the Data Structure in 

Inside the `data_storage_path` folder (or where your raw ASCII VCDs are stored), rename the dataset's folder (e.g., `aes_raw_data` or `fabscalar_raw_data`) to `raw_data`.

The following path variables are defined in `b_data_process_ml_env/data_process.py`:

```
  data_path = data_storage_path  # where the data is stored
  self.raw_data_path = f"{data_path}/raw_data" # starting raw ASCII VCDs
  self.rough_data_path = f"{data_path}/rough_data" # the cleaned and trimmed ASCII VCDs
  self.processed_uncompressed_data_path = f"{data_path}/processed_uncompressed_data" # for future expansion only
  self.processed_summarized_data_path = f"{data_path}/processed_summarized_data" # statistically compressed data
  self.final_data_path_train = f"{data_path}/final_data/train" # final packaging into train set
  self.final_data_path_test = f"{data_path}/final_data/test" # final packaging into test set
```

You can modify these paths if necessary. The program will automatically clean and re-create everything except the raw_data folder to process a new dataset. Alternatively, you can adjust the flow to process only specific steps by `modifying b_data_process_ml_env/data_process.py`.

---

## Additional Information

This framework is part of an ongoing development effort. For future updates, please refer to **[our GitHub page](https://your-dataset-link.com)**.  

For questions, feel free to email **minhdanhluu2000@gmail.com**. While I will do my best to respond promptly, please understand that responses may be delayed due to limited availability.  

Thank you for your interest in our work!
