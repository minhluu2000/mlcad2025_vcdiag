import React, { Children, useState } from "react";
import {Riple} from 'react-loading-indicators';
import './main.css';

interface ExpandableStageProps extends React.PropsWithChildren {
  loadingText: string;
}

const ExpandableStageVisualizer: React.FC<ExpandableStageProps> = ({ children, loadingText }) => {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div 
      className={'stage-container' + (expanded ? ' expand-content' : '')}
      onClick={() => { setExpanded(!expanded); }}
    >
      {Children.count(children) > 0 ? (
        <div className="stage-content">
          {children}
        </div>
      )
      : (
        <div className="loading-container">
          <Riple color="#646464" size="large" text={loadingText} />
        </div>
      )
      }
    </div>
  );
};

export default ExpandableStageVisualizer;