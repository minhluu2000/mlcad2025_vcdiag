import { useEffect, useState } from 'react';
import './App.css';
import FileSplitVisualizer from './components/fileSplit';
import ExpandableStageVisualizer from './components/stage';
import CodeBlock from './components/codeBlock';
import { IBug, IRegion, IVerilogLine } from './types';
import { BarChartComponent, PieChartComponent, RadialProgress } from './components/charts';

const stageNames = [
  'Split File',
  'Select Region',
  'Select Bug',
  'Mutate Line',
  'Evaluate',
]

interface Justifiable {
  justification?: string;
}

interface IEvaluationResult {
  status: 'success' | 'failure';
  error?: string;
}

interface WebSocketMessage {
  type: 'set_current_process' | 'update_stats' | 'split_file' | 'select_region' | 'select_bug' | 'mutate_line' | 'evaluate';
  payload: any;
}

function App() {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [currentProcess, setCurrentProcess] = useState("Split File");
  const [regions, setRegions] = useState<IRegion[]>([]); 
  const [selectedRegion, setSelectedRegion] = useState(-1); 
  const [selectedBug, setSelectedBug] = useState<(IBug & Justifiable) | undefined>();
  const [selectedLine, setSelectedLine] = useState<(IVerilogLine & Justifiable) | undefined>();
  const [mutatedLine, setMutatedLine] = useState<(IVerilogLine & Justifiable) | undefined>();
  const [evaluationResult, setEvaluationResult] = useState<IEvaluationResult | undefined>();
  
  const [bugFrequencies, setBugFrequencies] = useState([
    {name: "missing_assignment", amount: 2},
    {name: "bitwise_corruption", amount: 4},
    {name: "logic_bug", amount: 3},
    {name: "wrong_assignment", amount: 1},
  ]);
  const [successRate, setSuccessRate] = useState(90.5);

  useEffect(() => {
    // Initialize WebSocket connection
    const websocket = new WebSocket('ws://localhost:7500');
    setWs(websocket);

    websocket.onopen = () => {
      // setCurrentProcess("Connected");
      console.log('WebSocket Connected');
    };

    websocket.onclose = () => {
      // setCurrentProcess("Disconnected");
      console.log('WebSocket Disconnected');
    };

    websocket.onerror = (error) => {
      console.error('WebSocket Error:', error);
      // setCurrentProcess("Error");
    };

    websocket.onmessage = (event) => {
      const message: WebSocketMessage = JSON.parse(event.data);
      handleWebSocketMessage(message);
    };

    return () => {
      websocket.close();
    };
  }, []);

  const handleWebSocketMessage = (message: WebSocketMessage) => {
    switch (message.type) {
      case 'set_current_process':
        console.log('set_current_process', message.payload);
        setCurrentProcess(message.payload.processName);
        break;
      
      case 'update_stats':
        console.log('update_stats', message.payload);
        const stats = message.payload.stats;
        console.log(stats);
        setBugFrequencies(stats.bugStats);
        setSuccessRate(stats.successes / stats.totalAttempts * 100);
        break;
      
      case 'split_file':
        console.log('split_file', message.payload);
        setRegions(message.payload.regions as IRegion[]);
        setSelectedRegion(-1);
        setSelectedBug(undefined);
        setSelectedLine(undefined);
        setMutatedLine(undefined);
        setEvaluationResult(undefined);
        break;

      case 'select_region':
        console.log('select_region', message.payload);
        setSelectedRegion(parseInt(message.payload.selectedRegion));
        break;

      case 'select_bug':
        console.log('select_bug', message.payload);
        setSelectedBug(message.payload.bug as IBug);
        setSelectedLine(message.payload.line as IVerilogLine);
        break;

      case 'mutate_line':
        console.log('mutate_line', message.payload);
        setMutatedLine(message.payload.mutatedLine as (IVerilogLine & Justifiable));
        break;

      case 'evaluate':
        console.log('evaluate', message.payload);
        setEvaluationResult(message.payload.result as IEvaluationResult);
        break;

      default:
        console.warn('Unknown message type:', message.type);
    }
  };

  function hasStageLoaded(stageName: string, currentStage: string) {
    return stageNames.indexOf(stageName) <= stageNames.indexOf(currentStage);
  }

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

  // useEffect(() => {
  //   renderTest(1000);
  // }, []);

  return (
    <>
      <h2>Status: {currentProcess}</h2>
      <div className='pipeline-container'>
        <div className='pipeline-left'>
          <FileSplitVisualizer 
            regions={regions} 
            selectedRegion={selectedRegion} 
            loadingText='Split File'
          />
        </div>
        <div className='pipeline-right'>
          <ExpandableStageVisualizer loadingText='Loading Charts'>
            <div className='charts-row'>
              <RadialProgress title="Success Rate" percentage={successRate} height={200} />
              <BarChartComponent title="Bug Frequency" data={bugFrequencies} height={200} />
            </div>
          </ExpandableStageVisualizer>

          <ExpandableStageVisualizer loadingText='Select Bug'>{
            hasStageLoaded('Select Bug', currentProcess) &&
            selectedBug && selectedLine ? 
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
            : undefined
          }</ExpandableStageVisualizer>
          
          <ExpandableStageVisualizer loadingText='Mutate Line'>{
            hasStageLoaded('Mutate Line', currentProcess) &&
            selectedBug && mutatedLine ? 
            <>
              <CodeBlock {...mutatedLine}/>
              {mutatedLine.justification &&
                <div className='expandable'>
                  <b>Justification: </b> {mutatedLine.justification}
                </div>
              }
            </>
            : undefined
          }</ExpandableStageVisualizer>

          <ExpandableStageVisualizer loadingText='Evaluate'>{
            hasStageLoaded('Evaluate', currentProcess) &&
            evaluationResult ? (
              evaluationResult.status === 'success' ? 
                <div>
                  <span><b>Success</b></span>
                </div>
              :
                <div>
                  <span><b>Failure:</b> {evaluationResult.error}</span>
                </div>
            )
            : undefined
          }</ExpandableStageVisualizer>
        </div>
      </div>
    </>
  )
}

export default App
