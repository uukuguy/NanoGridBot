import { useState, useRef, useEffect, useCallback } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { ChevronUp, ChevronDown, Server, Network, BarChart3, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { api } from '../../api/client';
import { cn } from '@/lib/utils';
import '@xterm/xterm/css/xterm.css';

interface BottomPanelProps {
  className?: string;
  groupJid: string;
}

type TabType = 'terminal' | 'ipc' | 'metrics';

const MIN_HEIGHT = 40;
const MAX_HEIGHT = 500;
const DEFAULT_HEIGHT = 200;

export function BottomPanel({ className, groupJid }: BottomPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [height, setHeight] = useState(DEFAULT_HEIGHT);
  const [activeTab, setActiveTab] = useState<TabType>('terminal');

  // Drag state
  const containerRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);
  const dragStartYRef = useRef(0);
  const dragStartHeightRef = useRef(0);

  // Terminal refs
  const terminalRef = useRef<HTMLDivElement>(null);
  const terminalInstanceRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);

  // IPC messages (placeholder - would come from WebSocket in real implementation)
  const [ipcMessages] = useState<Array<{ time: string; type: string; data: unknown }>>([]);

  // Metrics data
  const [metrics, setMetrics] = useState<{
    totalRuns: number;
    successCount: number;
    errorCount: number;
    avgDuration: number;
  } | null>(null);

  // Load metrics on mount
  useEffect(() => {
    loadMetrics();
  }, [groupJid]);

  const loadMetrics = async () => {
    try {
      const data = await api.get<{
        total_runs: number;
        success_count: number;
        error_count: number;
        avg_duration_ms: number;
      }>(`/api/metrics/containers?group_jid=${encodeURIComponent(groupJid)}`);

      setMetrics({
        totalRuns: data.total_runs,
        successCount: data.success_count,
        errorCount: data.error_count,
        avgDuration: data.avg_duration_ms,
      });
    } catch {
      // Metrics not available
    }
  };

  // Initialize terminal
  useEffect(() => {
    if (!terminalRef.current || activeTab !== 'terminal') return;

    const terminal = new Terminal({
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
      },
      fontSize: 12,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      rows: 8,
      cursorBlink: true,
      convertEol: true,
    });

    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(terminalRef.current);
    fitAddon.fit();

    terminalInstanceRef.current = terminal;
    fitAddonRef.current = fitAddon;

    // Write welcome message
    terminal.writeln('\x1b[36mNanoGridBot Container Terminal\x1b[0m');
    terminal.writeln('Waiting for container output...');
    terminal.writeln('');

    // Handle resize
    const handleResize = () => {
      fitAddon.fit();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      terminal.dispose();
      terminalInstanceRef.current = null;
      fitAddonRef.current = null;
    };
  }, [activeTab]);

  // Drag handlers
  const startDrag = useCallback((startY: number) => {
    isDraggingRef.current = true;
    dragStartYRef.current = startY;
    dragStartHeightRef.current = height;

    const calcHeight = (currentY: number) => {
      const delta = dragStartYRef.current - currentY;
      return Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, dragStartHeightRef.current + delta));
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return;
      setHeight(calcHeight(e.clientY));
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
  }, [height]);

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    startDrag(e.clientY);
  };

  // Filter IPC messages for this group
  // Note: In real implementation, this would come from WebSocket

  return (
    <div
      ref={containerRef}
      className={cn(
        'flex flex-col bg-background border-t transition-all duration-200',
        className
      )}
      style={{ height: isExpanded ? height : MIN_HEIGHT }}
    >
      {/* Drag Handle */}
      <div
        className="h-1 flex items-center justify-center cursor-row-resize hover:bg-accent transition-colors"
        onMouseDown={handleDragStart}
      >
        <div className="w-12 h-0.5 rounded-full bg-muted-foreground/30" />
      </div>

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-1"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronUp className="w-4 h-4" />
            )}
          </Button>
          <Tabs
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as TabType)}
            className="h-7"
          >
            <TabsList className="h-7 gap-1">
              <TabsTrigger value="terminal" className="h-6 text-xs gap-1 px-2">
                <Server className="w-3 h-3" />
                终端
              </TabsTrigger>
              <TabsTrigger value="ipc" className="h-6 text-xs gap-1 px-2">
                <Network className="w-3 h-3" />
                IPC
              </TabsTrigger>
              <TabsTrigger value="metrics" className="h-6 text-xs gap-1 px-2">
                <BarChart3 className="w-3 h-3" />
                统计
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="flex-1 overflow-hidden">
          {activeTab === 'terminal' && (
            <TerminalContent terminalRef={terminalRef} />
          )}
          {activeTab === 'ipc' && (
            <IPCContent messages={ipcMessages} />
          )}
          {activeTab === 'metrics' && (
            <MetricsContent metrics={metrics} onRefresh={loadMetrics} />
          )}
        </div>
      )}
    </div>
  );
}

// Terminal content
function TerminalContent({ terminalRef }: { terminalRef: React.RefObject<HTMLDivElement | null> }) {
  return (
    <div ref={terminalRef} className="h-full w-full" />
  );
}

// IPC content
function IPCContent({ messages }: { messages: Array<{ time: string; type: string; data: unknown }> }) {
  if (messages.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
        等待 IPC 消息...
      </div>
    );
  }

  return (
    <ScrollArea className="h-full p-2">
      <div className="space-y-1">
        {messages.map((msg, i) => (
          <div key={i} className="text-xs font-mono bg-muted p-2 rounded">
            <span className="text-muted-foreground">[{msg.time}]</span>{' '}
            <span className="text-blue-500">{msg.type}</span>
            <pre className="mt-1 text-muted-foreground whitespace-pre-wrap">
              {JSON.stringify(msg.data, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}

// Metrics content
function MetricsContent({
  metrics,
  onRefresh,
}: {
  metrics: {
    totalRuns: number;
    successCount: number;
    errorCount: number;
    avgDuration: number;
  } | null;
  onRefresh: () => void;
}) {
  if (!metrics) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
        加载中...
      </div>
    );
  }

  const successRate = metrics.totalRuns > 0
    ? ((metrics.successCount / metrics.totalRuns) * 100).toFixed(1)
    : '0';

  return (
    <ScrollArea className="h-full p-3">
      <div className="flex justify-end mb-2">
        <Button variant="ghost" size="sm" onClick={onRefresh} className="h-7 gap-1">
          <RefreshCw className="w-3 h-3" />
          刷新
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="总执行次数" value={metrics.totalRuns.toString()} />
        <MetricCard label="成功次数" value={metrics.successCount.toString()} />
        <MetricCard label="失败次数" value={metrics.errorCount.toString()} />
        <MetricCard label="成功率" value={`${successRate}%`} />
        <MetricCard
          label="平均耗时"
          value={metrics.avgDuration > 0 ? `${(metrics.avgDuration / 1000).toFixed(1)}s` : '-'}
        />
      </div>
    </ScrollArea>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-muted rounded-lg p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
