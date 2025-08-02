import React from "react";
import {Riple} from 'react-loading-indicators';
import './main.css';
import { IRegion, Loadable } from "../types";

interface FileSplitProps extends Loadable {
  regions: IRegion[];
  selectedRegion: number;
}

const FileSplitVisualizer: React.FC<FileSplitProps> = ({ regions, selectedRegion, loadingText }) => {
  // Calculate total height to normalize proportions
  const totalHeight = regions.reduce((sum, region) => sum + region.totalLines, 0);

  return (
    <div className="file-split-container">
      {regions.length > 0 ?
        regions.map((region, index) => {
          // Calculate normalized height percentage
          const normalizedHeight = (region.totalLines / totalHeight) * 100;
          const fillPercentage = region.buggyLines / region.totalLines * 100;
          
          const isSelected = index === selectedRegion;
          
          return (
            <div
              key={index}
              className="region"
              style={{ height: `${normalizedHeight}%` }}
            >
              <div className={"region-background" + (selectedRegion === index ? " region-selected" : "")} />
              <div
                className="region-fill"
                style={{ width: `${fillPercentage}%` }}
              />
              <div className="region-label">
                {region.description ? 
                  (isSelected ?
                    <span><b>{`${region.name} (Selected)`}</b>: {region.description}</span>
                    :
                    <span><b>{region.name}</b>: {region.description}</span> 
                  )
                  :
                  (isSelected ?
                    <span><b>{`${region.name} (Selected)`}</b></span>
                    :
                    <span>{region.name}</span> 
                  )
                }
                <span>{region.buggyLines} / {region.totalLines}</span>
              </div>
            </div>
          );
        })
        :
        (
          <div className="loading-container">
            <Riple color="#646464" size="large" text={loadingText} />
          </div>
        )
      }
    </div>
  );
};

export default FileSplitVisualizer;