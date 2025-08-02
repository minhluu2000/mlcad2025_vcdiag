# Bug Insertion Evaluation
## Terminology
- Mutation -- a single changed line of Verilog code
- Mutation class -- The pipeline follows a class-based mutation paradigm where each mutation class represents a unique type of mutation with instructions on how it works
- Bug scenario -- a combination of mutations of size `num_mutations_per_bug` (usually 2-4)
- ROIs -- regions of interest within verilog files that engineers have determined are most likely to showcase realistic and interesting bug scenarios. These will not be shared with the model but will be used to ground evaluation.

## Criteria
### High degree of correctness
- As the pipeline will automatically rollback and fix syntactically or functionally invalid mutations, technically it will always produce a correct mutation 
- However, we can measure the overall pipeline accuracy by first-time success rate. Goal is 90% or above 
### Appreciable speed of generation
- Pipeline is already significantly faster than human efforts: generate, validate, & cache 60 bugs / minute 
- We will continue to improve this metric through parallelization & efficient roll-back 
### High surface coverage
- We will segment design files manually to isolate ROIs (regions of interest)
- Without sharing these regions with the pipeline, we run it end-to-end across each design 
- We measure if the number of injected bugs within each of these regions of interest are similar using a normalized entropy calculation, which we will aim to maximise to 0.8 or higher on average across all designs 
### Minimal redundancy
- By virtue of the pipeline’s design, structurally redundant mutations are impossible 
- To ensure functionally diverse mutations, we will check detected failure signatures for each bug scenario and calculate the percentage of unique bugs: aim for 80% or above

## Evaluated Metrics (for each design)
1. Accuracy
    - Overall first time accuracy %
    - First time accuracy % / mutation class
    - Average number of retries / mutation
    - Average number of retries / mutation class
    - Graph of how first-time accuracy changes over time
2. Speed of generation & validation
    - Overall
        - Number of detectable bugs / minute
        - Generation time: overall
        - Validation time: overall
    - Rollback time (undoing unsuccessful mutations and retrying)
        - Generation time: overall
        - Validation time: overall
    - Averages
        - Generation time: average / mutation
        - Generation time: average / bug scenario
        - Validation time: average / mutation
        - Validation time: average / bug scenario
3. Surface Coverage
    - Average coverage / ROI (region of interest) -- `avg(#number of mutated lines / len(ROI))`
    - normalized entropy calculation across ROIs
4. Redundancy
    - Redundant bug scenarios
    - Overall distribution of mutation classes
    - Distribution of mutation classes across all ROIs
