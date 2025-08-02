import React from 'react';
import { diffChars, diffLines, diffWordsWithSpace } from 'diff';
import './codeBlock.css';
import { IVerilogLine } from '../types';

function stripLines(lines: string[]) : string[] {
  return lines.map(line => line.split('//')[0].trim());
}

const CodeBlock: React.FC<IVerilogLine> = ({ before, after, lineNumber }) => {
  const isDifferent = after && before !== after;
  const beforeLines = stripLines(before.split('\n'));
  const afterLines = after ? stripLines(after.split('\n')) : [];

  if (!isDifferent) {
    return (
      <div className="code-block">
        <pre className="code-content">
          {beforeLines.map((line, index) => (
            <div key={index} className="line-unchanged">
              <span className="line-number">{lineNumber + index}</span> {line}
            </div>
          ))}
        </pre>
      </div>
    );
  }

  const lineDiffs = diffLines(beforeLines.join('\n'), afterLines.join('\n'));

  return (
    <div className="code-block">
      <pre className="code-content">
        {lineDiffs.map((lineDiff, index) => {
          if (!lineDiff.added && !lineDiff.removed) {
            return (
              <div key={index} className="line-unchanged">
                <span className="line-number">{lineNumber + index}</span> {lineDiff.value}
              </div>
            );
          }

          const charDiffs = diffChars(lineDiff.removed ? lineDiff.value : '', lineDiff.added ? lineDiff.value : '');

          return (
            <div key={index} className={lineDiff.removed ? "line-removed" : "line-added"}>
              <span className="line-number">{lineNumber + index}</span> {lineDiff.removed ? '-' : '+'}
              {charDiffs.map((part, i) => (
                <span key={i} className={part.added ? 'char-added' : part.removed ? 'char-removed' : ''}>
                  {part.value}
                </span>
              ))}
            </div>
          );
        })}
      </pre>
    </div>
  );
};


export default CodeBlock;

