import { useEffect, useState } from 'react';
import './App.css';
import FileSplitVisualizer from './components/fileSplit';
import ExpandableStageVisualizer from './components/stage';
import CodeBlock from './components/codeBlock';
import { IBug, IRegion, IVerilogLine } from './types';

const stageNames = [
  'Split File',
  'Select Region',
  'Select Bug',
  'Mutate Line',
]

interface Justifiable {
  justification?: string;
}

interface IEvaluationResult {
  status: 'success' | 'failure';
  error?: string;
}

function App() {
  const [currentProcess, setCurrentProcess] = useState("Splitting");
  const [regions, setRegions] = useState<IRegion[]>([]); 
  const [selectedRegion, setSelectedRegion] = useState(-1); 
  const [selectedBug, setSelectedBug] = useState<(IBug & Justifiable) | undefined>();
  const [selectedLine, setSelectedLine] = useState<(IVerilogLine & Justifiable) | undefined>();
  const [mutatedLine, setMutatedLine] = useState<(IVerilogLine & Justifiable) | undefined>();
  const [evaluationResult, setEvaluationResult] = useState<IEvaluationResult | undefined>();

  function renderTest(delayMs: number) {
    setCurrentProcess("Split File");
    setTimeout(() => {
      setRegions([
        { name: "Region 1", totalLines: 100, buggyLines: 0 },
        { name: "Region 2", totalLines: 200, buggyLines: 3 },
        { name: "Region 3", totalLines: 50, buggyLines: 15 },
        { name: "Region 4", totalLines: 75, buggyLines: 0 },
        { name: "Region 5", totalLines: 250, buggyLines: 0 },
      ]);
      setCurrentProcess("Select Region");
      setTimeout(() => {
        setSelectedRegion(1);
        setCurrentProcess("Select Bug");
        setTimeout(() => {
          setSelectedBug({
            name: 'missing_assignment',
            description: `When an assignment to a variable that should be there is missing. This can be achieved by commenting out an existing assignment statement. For example: assign a = b; can be changed to // assign a = b; You should not introduce new variables, but commenting out existing ones.`,
            justification: 'This was the best bug for the given region',
          })
          setSelectedLine({
            lineNumber: 153,
            before: `assign in_ready_o           = sp2v_e'(sp_in_ready);`,
          })
          setCurrentProcess("Mutate Line");
          setTimeout(() => {
            setMutatedLine({
              lineNumber: 153,
              before: `assign in_ready_o           = sp2v_e'(sp_in_ready);`,
              after: `assign in_ready_o           = sp2v_e'(~sp_in_ready);`,
              justification: 'We inverted that bish',
            })
            setTimeout(() => {
              setEvaluationResult({status: 'success'});
              setRegions(oldRegions => {
                oldRegions[1].buggyLines += 1;
                return oldRegions;
              })
            }, delayMs)
          }, delayMs);
        }, delayMs)
      }, delayMs);
    }, delayMs);
  }

  useEffect(() => {
    renderTest(1000);
  }, []);

  return (
    <>
      <h2>Status: {currentProcess}</h2>
      <div className='pipeline-container'>
        <div className='pipeline-left'>
          <FileSplitVisualizer regions={regions} selectedRegion={selectedRegion} loadingText='Split File'/>
        </div>
        <div className='pipeline-right'>
          <ExpandableStageVisualizer loadingText='Select Bug'>{
            selectedBug && selectedLine && 
            <>
              <div className='bug-container'>
                Selected <span className='bug-title'>{selectedBug.name}: </span>
                <span className='bug-description'>{selectedBug.description}</span>
              </div>
              <CodeBlock {...selectedLine}/>
              {selectedBug.justification &&
                <div className='expandable'>
                  <b>Justification: </b> {selectedBug.justification}
                </div>
              }
            </>
          }</ExpandableStageVisualizer>
          
          <ExpandableStageVisualizer loadingText='Mutate Line'>{
            selectedBug && mutatedLine && 
            <>
              <CodeBlock {...mutatedLine}/>
              {mutatedLine.justification &&
                <div className='expandable'>
                  <b>Justification: </b> {mutatedLine.justification}
                </div>
              }
            </>
          }</ExpandableStageVisualizer>

          <ExpandableStageVisualizer loadingText='Evaluate'>{
            evaluationResult && (
              evaluationResult.status === 'success' ? 
                <div>
                  <span><b>Success</b></span>
                </div>
              :
                <div>
                  <span><b>Failure:</b> {evaluationResult.error}</span>
                </div>
            )
          }</ExpandableStageVisualizer>
        </div>
      </div>
    </>
  )
}

export default App
