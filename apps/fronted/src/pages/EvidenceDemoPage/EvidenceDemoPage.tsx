/**
 * 医学证据可视化演示页面
 */
import React from 'react';
import { EvidenceViewer } from '../../components/evidence/EvidenceViewer/EvidenceViewer';
import './EvidenceDemoPage.css';

export const EvidenceDemoPage: React.FC = () => {
  return (
    <div className="evidence-demo-page">
      <header className="demo-header">
        <h1>医学证据可视化分析</h1>
        <p>TRPV1通道功能特征分析 - 交互式证据定位演示</p>
      </header>
      <EvidenceViewer 
        basePath="/demo_output" 
        documentId="" 
      />
    </div>
  );
};

export default EvidenceDemoPage;
