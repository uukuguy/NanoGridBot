import { useMemo, useState } from 'react';
import { Copy, Check, FileText, Cpu, Hash } from 'lucide-react';
import { useChatStore, type GroupInfo } from '../../stores/chat';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/shared/Badge';
import { cn } from '@/lib/utils';

interface InspectorPanelProps {
  className?: string;
  groupJid: string;
}

// Types for selected message
type MessageType = 'user' | 'assistant' | 'tool' | 'thinking' | 'error' | 'system';

interface ToolCallDetail {
  id: string;
  name: string;
  input: Record<string, unknown>;
  output?: unknown;
}

interface MessageDetail {
  type: MessageType;
  content?: string;
  toolCalls?: ToolCallDetail[];
  thinking?: string;
  sessionId?: string;
  tokens?: number;
  duration?: number;
  containerId?: string;
  filesChanged?: string[];
}

export function InspectorPanel({ className, groupJid }: InspectorPanelProps) {
  const selectedMessage = useChatStore((s) => s.selectedMessage);
  const groups = useChatStore((s) => s.groups);
  const group = groups[groupJid];

  // Parse selected message to get details
  const messageDetail = useMemo((): MessageDetail | null => {
    if (!selectedMessage) return null;

    const msg = selectedMessage;

    // Extract session metadata (available in any message)
    const sessionMeta = {
      sessionId: msg.session_id,
      tokens: msg.tokens,
      duration: msg.duration,
      containerId: msg.container_id,
    };

    // Determine message type
    if (msg.role === 'user') {
      return { type: 'user', content: msg.content, ...sessionMeta };
    }

    if (msg.role === 'assistant') {
      // Check for tool calls (multiple supported)
      if (msg.tool_calls && msg.tool_calls.length > 0) {
        const toolCalls: ToolCallDetail[] = msg.tool_calls.map((tc) => ({
          id: tc.id,
          name: tc.function?.name || 'unknown',
          input:
            typeof tc.function?.arguments === 'string'
              ? JSON.parse(tc.function.arguments)
              : (tc.function?.arguments as Record<string, unknown>),
          output: msg.tool_output,
        }));

        return {
          type: 'tool',
          toolCalls,
          ...sessionMeta,
        };
      }

      // Check for thinking/thought
      if (msg.thinking) {
        return { type: 'thinking', thinking: msg.thinking, ...sessionMeta };
      }

      return { type: 'assistant', content: msg.content, ...sessionMeta };
    }

    if (msg.role === 'system') {
      return { type: 'system', content: msg.content, ...sessionMeta };
    }

    return null;
  }, [selectedMessage]);

  // Workspace overview when no message selected
  if (!messageDetail) {
    return (
      <div className={cn('flex flex-col h-full bg-background border-l', className)}>
        <div className="p-3 border-b">
          <h3 className="text-sm font-semibold">检查器</h3>
        </div>
        <div className="flex-1 p-4">
          <WorkspaceOverview group={group} />
        </div>
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col h-full bg-background border-l', className)}>
      <div className="p-3 border-b">
        <h3 className="text-sm font-semibold">检查器</h3>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-3 space-y-4">
          {/* Message Type Badge */}
          <div>
            <MessageTypeBadge type={messageDetail.type} />
          </div>

          {/* Content */}
          {messageDetail.content && (
            <DetailSection title="内容" icon={<FileText className="w-4 h-4" />}>
              <pre className="text-xs whitespace-pre-wrap font-mono bg-muted p-2 rounded max-h-40 overflow-auto">
                {messageDetail.content}
              </pre>
            </DetailSection>
          )}

          {/* Thinking */}
          {messageDetail.thinking && (
            <DetailSection title="推理过程" icon={<FileText className="w-4 h-4" />}>
              <pre className="text-xs whitespace-pre-wrap font-mono bg-muted p-2 rounded max-h-60 overflow-auto">
                {messageDetail.thinking}
              </pre>
            </DetailSection>
          )}

          {/* Tool Calls - Multiple supported */}
          {messageDetail.type === 'tool' && messageDetail.toolCalls && (
            <DetailSection
              title={`工具调用 (${messageDetail.toolCalls.length})`}
              icon={<Cpu className="w-4 h-4" />}
            >
              <div className="space-y-3">
                {messageDetail.toolCalls.map((toolCall, index) => (
                  <div key={toolCall.id} className="border rounded-lg p-3 bg-muted/30">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-mono text-xs font-medium text-blue-600 dark:text-blue-400">
                        {index + 1}. {toolCall.name}
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div>
                        <div className="text-xs text-muted-foreground mb-1">输入参数:</div>
                        <CodeBlock data={toolCall.input} />
                      </div>
                      {toolCall.output !== undefined && (
                        <div>
                          <div className="text-xs text-muted-foreground mb-1">输出结果:</div>
                          <CodeBlock data={toolCall.output} />
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </DetailSection>
          )}

          {/* Session Metadata - Show only if data exists */}
          {(messageDetail.sessionId || messageDetail.tokens || messageDetail.duration || messageDetail.containerId) && (
            <DetailSection title="会话信息" icon={<Hash className="w-4 h-4" />}>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {messageDetail.sessionId && (
                  <MetadataItem label="Session ID" value={messageDetail.sessionId} />
                )}
                {messageDetail.tokens && (
                  <MetadataItem label="Tokens" value={formatTokens(messageDetail.tokens)} />
                )}
                {messageDetail.duration && (
                  <MetadataItem label="耗时" value={formatDuration(messageDetail.duration)} />
                )}
                {messageDetail.containerId && (
                  <MetadataItem label="容器" value={messageDetail.containerId} />
                )}
              </div>
            </DetailSection>
          )}

          {/* Files Changed */}
          {messageDetail.filesChanged && messageDetail.filesChanged.length > 0 && (
            <DetailSection title="文件变更" icon={<FileText className="w-4 h-4" />}>
              <div className="flex flex-wrap gap-1">
                {messageDetail.filesChanged.map((file) => (
                  <Badge key={file} variant="neutral">
                    {file}
                  </Badge>
                ))}
              </div>
            </DetailSection>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

// Workspace overview when no message is selected
function WorkspaceOverview({ group }: { group?: GroupInfo }) {
  if (!group) {
    return (
      <p className="text-sm text-muted-foreground">选择工作区查看详情</p>
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <div className="text-xs text-muted-foreground">工作区名称</div>
        <div className="text-sm font-medium">{group.name}</div>
      </div>
      {group.folder && (
        <div>
          <div className="text-xs text-muted-foreground">文件夹</div>
          <div className="text-sm font-mono">{group.folder}</div>
        </div>
      )}
      {group.execution_mode && (
        <div>
          <div className="text-xs text-muted-foreground">执行模式</div>
          <Badge variant={group.execution_mode === 'host' ? 'warning' : 'info'}>
            {group.execution_mode === 'host' ? '宿主机' : 'Docker'}
          </Badge>
        </div>
      )}
      <p className="text-xs text-muted-foreground pt-2">
        点击对话流中的消息查看详情
      </p>
    </div>
  );
}

// Detail section component
function DetailSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground mb-2">
        {icon}
        {title}
      </div>
      {children}
    </div>
  );
}

// Message type badge
function MessageTypeBadge({ type }: { type: MessageType }) {
  const config: Record<MessageType, { label: string; variant: 'success' | 'warning' | 'error' | 'info' | 'neutral' }> = {
    user: { label: '用户消息', variant: 'info' },
    assistant: { label: 'AI 回复', variant: 'neutral' },
    tool: { label: '工具调用', variant: 'warning' },
    thinking: { label: '思考过程', variant: 'info' },
    error: { label: '错误', variant: 'error' },
    system: { label: '系统', variant: 'neutral' },
  };

  const { label, variant } = config[type];
  return <Badge variant={variant}>{label}</Badge>;
}

// Code block with copy button
function CodeBlock({ data }: { data: unknown }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group">
      <pre className="text-xs whitespace-pre-wrap font-mono bg-muted p-2 rounded max-h-40 overflow-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
      <Button
        variant="ghost"
        size="sm"
        className="absolute top-1 right-1 h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={handleCopy}
      >
        {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      </Button>
    </div>
  );
}

// Metadata item
function MetadataItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-muted p-2 rounded">
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className="text-xs truncate" title={value}>
        {value}
      </div>
    </div>
  );
}

// Format helpers
function formatTokens(tokens: number): string {
  if (tokens >= 1000) {
    return `${(tokens / 1000).toFixed(1)}k`;
  }
  return tokens.toString();
}

function formatDuration(ms: number): string {
  if (ms >= 60000) {
    return `${(ms / 60000).toFixed(1)}m`;
  }
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${ms}ms`;
}
