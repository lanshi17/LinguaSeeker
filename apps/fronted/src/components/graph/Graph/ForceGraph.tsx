/**
 * D3 力导向知识图谱组件
 * 支持节点交互、缩放、筛选、导出
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import type { GraphNode, GraphEdge, EvidenceTypeValue } from '../../../types';
import { EvidenceTypeColors } from '../../../types';
import './ForceGraph.css';

interface ForceGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
  width?: number;
  height?: number;
}

export const ForceGraph: React.FC<ForceGraphProps> = ({
  nodes,
  edges,
  onNodeClick,
  width = 800,
  height = 600,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{
    visible: boolean;
    x: number;
    y: number;
    node?: GraphNode;
  }>({ visible: false, x: 0, y: 0 });

  // 初始化 D3 力导向图
  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    // 创建缩放行为
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    const g = svg.append('g');

    // 准备数据
    const simulationNodes: d3.SimulationNodeDatum & GraphNode[] = nodes.map(n => ({ ...n }));
    const simulationLinks: d3.SimulationLinkDatum<typeof simulationNodes[0]>[] = edges.map(e => ({
      source: e.source,
      target: e.target,
      value: e.weight,
    }));

    // 创建力导向模拟
    const simulation = d3.forceSimulation(simulationNodes)
      .force('link', d3.forceLink(simulationLinks).id((d: any) => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(30));

    // 绘制连线
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(simulationLinks)
      .enter()
      .append('line')
      .attr('stroke-width', (d: any) => Math.sqrt(d.value) * 2)
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6);

    // 绘制节点
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(simulationNodes)
      .enter()
      .append('g')
      .attr('class', 'node')
      .call(d3.drag<any, any>()
        .on('start', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d: any) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
      );

    // 节点圆形
    node.append('circle')
      .attr('r', (d: any) => d.type === 'keyword' ? 25 : d.type === 'evidence' ? 20 : 15)
      .attr('fill', (d: any) => {
        if (d.type === 'evidence' && d.evidenceType) {
          return EvidenceTypeColors[d.evidenceType as EvidenceTypeValue];
        }
        if (d.type === 'keyword') return '#3b82f6';
        return '#10b981';
      })
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer');

    // 节点文字
    node.append('text')
      .text((d: any) => d.label.slice(0, 10))
      .attr('x', 0)
      .attr('y', 4)
      .attr('text-anchor', 'middle')
      .attr('fill', '#fff')
      .attr('font-size', '10px')
      .attr('font-weight', 'bold');

    // 节点交互
    node
      .on('click', (event: any, d: any) => {
        event.stopPropagation();
        setSelectedNode(d.id);
        onNodeClick?.(d);
      })
      .on('mouseover', (event: any, d: any) => {
        setTooltip({
          visible: true,
          x: event.pageX + 10,
          y: event.pageY - 10,
          node: d,
        });
      })
      .on('mouseout', () => {
        setTooltip((t) => ({ ...t, visible: false }));
      });

    // 更新位置
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    return () => {
      simulation.stop();
    };
  }, [nodes, edges, width, height, onNodeClick]);

  // 导出 PNG
  const exportPNG = useCallback(() => {
    if (!svgRef.current) return;
    const svgData = new XMLSerializer().serializeToString(svgRef.current);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = width;
    canvas.height = height;

    const img = new Image();
    img.onload = () => {
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(0, 0, width, height);
      ctx.drawImage(img, 0, 0);
      const link = document.createElement('a');
      link.download = 'knowledge-graph.png';
      link.href = canvas.toDataURL('image/png');
      link.click();
    };
    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
  }, [width, height]);

  // 导出 SVG
  const exportSVG = useCallback(() => {
    if (!svgRef.current) return;
    const svgData = new XMLSerializer().serializeToString(svgRef.current);
    const blob = new Blob([svgData], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.download = 'knowledge-graph.svg';
    link.href = url;
    link.click();
    URL.revokeObjectURL(url);
  }, []);

  return (
    <div className="force-graph" ref={containerRef}>
      {/* 控制栏 */}
      <div className="graph-controls">
        <div className="control-group">
          <span className="control-label">图谱控制</span>
          <button onClick={exportPNG} title="导出 PNG">
            📷 PNG
          </button>
          <button onClick={exportSVG} title="导出 SVG">
            🎨 SVG
          </button>
        </div>
        <div className="legend">
          <div className="legend-item">
            <span className="dot keyword" />
            <span>关键词</span>
          </div>
          <div className="legend-item">
            <span className="dot evidence" />
            <span>证据</span>
          </div>
          <div className="legend-item">
            <span className="dot document" />
            <span>文献</span>
          </div>
        </div>
      </div>

      {/* SVG 画布 */}
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="graph-svg"
      />

      {/* Tooltip */}
      {tooltip.visible && tooltip.node && (
        <div
          className="graph-tooltip"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <h4>{tooltip.node.label}</h4>
          <p>类型: {tooltip.node.type}</p>
          {tooltip.node.evidenceType && (
            <p>证据类型: {tooltip.node.evidenceType}</p>
          )}
          {selectedNode === tooltip.node.id && (
            <p className="selected-hint">点击查看详情</p>
          )}
        </div>
      )}
    </div>
  );
};
