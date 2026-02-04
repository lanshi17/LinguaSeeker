/**
 * D3.js 力导向图组件
 * 支持节点悬停显示证据摘要、点击跳转原文、导出/缩放/筛选
 */
import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { ZoomIn, ZoomOut, Maximize, Download, Filter, X } from 'lucide-react';
import type { GraphData, GraphNode, GraphEdge } from '../../types';
import { EvidenceTypeColors } from '../../types';
import './ForceGraph.css';

interface ForceGraphProps {
  data: GraphData;
  onNodeClick?: (node: GraphNode) => void;
  width?: number;
  height?: number;
}

interface TooltipData {
  node: GraphNode;
  x: number;
  y: number;
}

export const ForceGraph: React.FC<ForceGraphProps> = ({
  data,
  onNodeClick,
  width = 800,
  height = 600,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set(['keyword', 'evidence', 'document']));
  const [scale, setScale] = useState(1);
  const zoomRef = useRef<d3.ZoomBehavior<Element, unknown> | null>(null);

  // 筛选数据
  const filteredData = React.useMemo(() => {
    const filteredNodes = data.nodes.filter(n => selectedTypes.has(n.type));
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredEdges = data.edges.filter(e => nodeIds.has(e.source as string) && nodeIds.has(e.target as string));
    return { nodes: filteredNodes, edges: filteredEdges };
  }, [data, selectedTypes]);

  // 初始化力导向图
  useEffect(() => {
    if (!svgRef.current || filteredData.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    // 创建容器组
    const g = svg.append('g');

    // 创建箭头标记
    svg.append('defs').selectAll('marker')
      .data(['arrow'])
      .enter().append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#94a3b8');

    // 创建力模拟
    const simulation = d3.forceSimulation(filteredData.nodes as d3.SimulationNodeDatum[])
      .force('link', d3.forceLink(filteredData.edges).id((d: any) => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(40));

    // 绘制边
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(filteredData.edges)
      .enter().append('line')
      .attr('stroke', '#94a3b8')
      .attr('stroke-width', (d: GraphEdge) => Math.sqrt(d.weight) * 2)
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', 'url(#arrow)');

    // 绘制节点
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(filteredData.nodes)
      .enter().append('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .call(d3.drag<SVGGElement, GraphNode>()
        .on('start', (event: any, d: any) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event: any, d: any) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event: any, d: any) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }));

    // 节点圆形
    node.append('circle')
      .attr('r', (d: GraphNode) => d.type === 'keyword' ? 28 : d.type === 'evidence' ? 24 : 18)
      .attr('fill', (d: GraphNode) => {
        if (d.type === 'evidence' && d.evidenceType) {
          return EvidenceTypeColors[d.evidenceType];
        }
        if (d.type === 'keyword') return '#3b82f6';
        return '#10b981';
      })
      .attr('stroke', '#fff')
      .attr('stroke-width', 3)
      .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.2))');

    // 节点图标/文字
    node.append('text')
      .attr('dy', '.35em')
      .attr('text-anchor', 'middle')
      .text((d: GraphNode) => {
        if (d.type === 'keyword') return '🔑';
        if (d.type === 'evidence') return '📋';
        return '📄';
      })
      .style('font-size', '14px');

    // 节点标签
    node.append('text')
      .attr('dy', (d: GraphNode) => d.type === 'keyword' ? 45 : d.type === 'evidence' ? 40 : 35)
      .attr('text-anchor', 'middle')
      .text((d: GraphNode) => {
        const maxLen = 12;
        return d.label.length > maxLen ? d.label.slice(0, maxLen) + '...' : d.label;
      })
      .attr('class', 'node-label')
      .style('font-size', '12px')
      .style('font-weight', '500')
      .style('fill', '#334155')
      .style('pointer-events', 'none');

    // 悬停事件
    node.on('mouseenter', (event: any, d: GraphNode) => {
      const [x, y] = d3.pointer(event, containerRef.current);
      setTooltip({ node: d, x, y });
      
      d3.select(event.currentTarget).select('circle')
        .transition()
        .duration(200)
        .attr('r', d.type === 'keyword' ? 32 : d.type === 'evidence' ? 28 : 22);
    });

    node.on('mouseleave', (event: any, d: GraphNode) => {
      setTooltip(null);
      
      d3.select(event.currentTarget).select('circle')
        .transition()
        .duration(200)
        .attr('r', d.type === 'keyword' ? 28 : d.type === 'evidence' ? 24 : 18);
    });

    // 点击事件
    node.on('click', (event: any, d: GraphNode) => {
      event.stopPropagation();
      onNodeClick?.(d);
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

    // 缩放行为
    const zoom = d3.zoom<Element, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', (event: any) => {
        g.attr('transform', event.transform);
        setScale(event.transform.k);
      });

    zoomRef.current = zoom;
    svg.call(zoom as any);

    return () => {
      simulation.stop();
    };
  }, [filteredData, width, height, onNodeClick]);

  // 缩放控制
  const handleZoomIn = () => {
    if (!svgRef.current || !zoomRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.transition().duration(300).call(zoomRef.current.scaleBy as any, 1.3);
  };

  const handleZoomOut = () => {
    if (!svgRef.current || !zoomRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.transition().duration(300).call(zoomRef.current.scaleBy as any, 1 / 1.3);
  };

  const handleReset = () => {
    if (!svgRef.current || !zoomRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.transition().duration(500).call(zoomRef.current.transform as any, d3.zoomIdentity);
  };

  // 导出图谱
  const handleExport = () => {
    if (!svgRef.current) return;
    const svgData = new XMLSerializer().serializeToString(svgRef.current);
    const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `graph-${Date.now()}.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // 切换筛选
  const toggleType = (type: string) => {
    setSelectedTypes(prev => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  return (
    <div className="force-graph" ref={containerRef}>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="graph-svg"
      />

      {/* 缩放控制 */}
      <div className="graph-controls">
        <button onClick={handleZoomIn} title="放大">
          <ZoomIn size={18} />
        </button>
        <button onClick={handleReset} title="重置">
          <Maximize size={18} />
        </button>
        <button onClick={handleZoomOut} title="缩小">
          <ZoomOut size={18} />
        </button>
        <span className="zoom-level">{Math.round(scale * 100)}%</span>
      </div>

      {/* 筛选控制 */}
      <div className="graph-filters">
        <div className="filter-header">
          <Filter size={14} />
          <span>筛选</span>
        </div>
        {[
          { type: 'keyword', label: '关键词', color: '#3b82f6' },
          { type: 'evidence', label: '证据', color: '#f59e0b' },
          { type: 'document', label: '文献', color: '#10b981' },
        ].map(({ type, label, color }) => (
          <label key={type} className="filter-item">
            <input
              type="checkbox"
              checked={selectedTypes.has(type)}
              onChange={() => toggleType(type)}
            />
            <span className="filter-dot" style={{ background: color }} />
            <span>{label}</span>
          </label>
        ))}
      </div>

      {/* 导出按钮 */}
      <button className="export-btn" onClick={handleExport} title="导出SVG">
        <Download size={18} />
      </button>

      {/* 悬停提示 */}
      {tooltip && (
        <div
          className="graph-tooltip"
          style={{
            left: tooltip.x + 20,
            top: tooltip.y - 10,
          }}
        >
          <button className="tooltip-close" onClick={() => setTooltip(null)}>
            <X size={14} />
          </button>
          <div className="tooltip-header">
            <span
              className="tooltip-type"
              style={{
                backgroundColor:
                  tooltip.node.type === 'evidence' && tooltip.node.evidenceType
                    ? EvidenceTypeColors[tooltip.node.evidenceType] + '20'
                    : tooltip.node.type === 'keyword'
                    ? '#3b82f620'
                    : '#10b98120',
                color:
                  tooltip.node.type === 'evidence' && tooltip.node.evidenceType
                    ? EvidenceTypeColors[tooltip.node.evidenceType]
                    : tooltip.node.type === 'keyword'
                    ? '#3b82f6'
                    : '#10b981',
              }}
            >
              {tooltip.node.type === 'keyword' ? '关键词' : tooltip.node.type === 'evidence' ? '证据' : '文献'}
            </span>
          </div>
          <h4 className="tooltip-title">{tooltip.node.label}</h4>
          {tooltip.node.evidenceType && (
            <p className="tooltip-evidence">
              证据类型: <strong>{tooltip.node.evidenceType}</strong>
            </p>
          )}
          {tooltip.node.type === 'document' && (
            <p className="tooltip-hint">点击查看详情</p>
          )}
        </div>
      )}
    </div>
  );
};
