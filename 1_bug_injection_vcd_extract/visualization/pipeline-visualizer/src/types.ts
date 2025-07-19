export interface Loadable {
  loadingText: string;
}

export interface IStage {
  name: string; 
  status: 'notStarted' | 'inProgress' | 'completed';
  justification?: string;
}

export interface IVerilogLine {
  lineNumber: number;
  before: string;
  after?: string;
}

export interface IBug {
  name: string;
  description: string;
}

export interface IRegion {
  name: string;
  description?: string;
  totalLines: number;
  buggyLines: number;
}