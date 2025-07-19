# Create logs directory if it does not exist
if [ ! -d logs ]; then
    mkdir logs
fi

njobs=$(nproc) # nproc returns the number of processing units scheduled for use
njobs=$((njobs-1)) # use nproc-2 jobs to avoid overloading the system

design_name="opentitan" # opentitan, mesi, fabscalar
mode="data_process" # data_process, bug_predict

# print the number of processing units
echo "Number of cores: $(nproc)"
echo "Number of processing units: $njobs"

# print the design name and mode
echo "Design name: $design_name"
echo "Mode: $mode"

# if njobs = 0, set njobs to 1
if [ $njobs -eq 0 ]; then
    njobs=1
fi

# source general environment setup
source scripts/env_general.sh

# activate conda environment
source activate sim_ml
# run the python script
# python3 -u extract.py --design_name $design_name --mode $mode --njobs $njobs 2>&1 | tee logs/extract_${SLURM_JOB_ID}.log
python3 -u data.py --design_name $design_name --mode $mode --njobs $njobs 2>&1 | tee logs/data_${SLURM_JOB_ID}.log
# send email notification
# python3 sendmail.py "Bug Extraction Done" "Job number: ${SLURM_JOB_ID}." self