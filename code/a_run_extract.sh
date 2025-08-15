# Create logs directory if it does not exist
if [ ! -d logs ]; then
    mkdir logs
fi

njobs=$(nproc) # nproc returns the number of processing units scheduled for use
njobs=$((njobs-2)) # use nproc-2 jobs to avoid overloading the system

design_name="opentitan" # opentitan, mesi, fabscalar
mode="generate_bugs" # generate_bugs, insert_and_extract

# print the number of processing units
echo "Number of cores: $(nproc)"

# print the design name and mode
echo "Design name: $design_name"
echo "Mode: $mode"

# if njobs = 0, set njobs to 1
if [ $njobs -lt 1 ]; then
    njobs=1
fi

# if this is bug generation, set njobs to 1
if [ "$mode" == "generate_bugs" ]; then
    njobs=1
fi

echo "Number of processing units: $njobs"

# source general environment setup
source scripts/env_general.sh

# if design is fabscalar, use cadence, else use synopsys
if [ "$design_name" == "fabscalar" ]; then
    source scripts/env_cadence.sh
else
    source scripts/env_synopsys.sh
fi

# activate conda environment
source activate sim_extract
# run the python script
python3 -u extract.py --design_name $design_name --mode $mode --njobs 2 2>&1 | tee logs/extract_${SLURM_JOB_ID}.log
# send email notification
# python3 sendmail.py "Bug Extraction Done" "Job number: ${SLURM_JOB_ID}." self