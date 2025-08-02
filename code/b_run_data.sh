# Create logs directory if it does not exist
if [ ! -d logs ]; then
    mkdir logs
fi

njobs=$(nproc) # nproc returns the number of processing units scheduled for use
njobs=$((njobs-2)) # use nproc-2 jobs to avoid overloading the system

design_name="opentitan" # opentitan, mesi, fabscalar
mode="data_process" # data_process is the only option for this version
ml_model="ml_knn" # ml_knn, ml_rfc, ml_lightgbm, ml_xgboost

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

# install sim_ml_requirements.txt
# python -m pip install -r python_requirements/sim_ml_requirements.txt

# run the python script
python3 -u b_data.py --design_name $design_name --mode $mode --njobs $njobs 2>&1 | tee logs/data_processing.log