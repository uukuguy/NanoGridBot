import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useChatStore } from '../stores/chat';
import { useAuthStore } from '../stores/auth';
import { WorkspaceList } from '../components/console/WorkspaceList';
import { InspectorPanel } from '../components/console/InspectorPanel';
import { BottomPanel } from '../components/console/BottomPanel';
import { ChatView } from '../components/chat/ChatView';
import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// Panel width constants
const RIGHT_PANEL_WIDTH = 300;

export function ChatPage() {
  const { groupFolder } = useParams<{ groupFolder?: string }>();
  const navigate = useNavigate();
  const { groups, currentGroup, selectGroup, inspectorOpen, toggleInspector } = useChatStore();

  // Panel visibility state
  const [leftPanelVisible, setLeftPanelVisible] = useState(true);

  // Find group jid from folder
  const routeGroupJid = useMemo(() => {
    if (!groupFolder) return null;
    const entry =
      Object.entries(groups).find(
        ([jid, info]) =>
          info.folder === groupFolder && jid.startsWith('web:') && !!info.is_home,
      ) ||
      Object.entries(groups).find(
        ([jid, info]) => info.folder === groupFolder && jid.startsWith('web:'),
      ) ||
      Object.entries(groups).find(([_, info]) => info.folder === groupFolder);
    return entry?.[0] || null;
  }, [groupFolder, groups]);

  const appearance = useAuthStore((s) => s.appearance);
  const hasGroups = Object.keys(groups).length > 0;

  // Sync URL param to store selection
  useEffect(() => {
    if (!groupFolder) return;
    if (routeGroupJid && currentGroup !== routeGroupJid) {
      selectGroup(routeGroupJid);
      return;
    }
    if (hasGroups && !routeGroupJid) {
      navigate('/chat', { replace: true });
    }
  }, [groupFolder, routeGroupJid, hasGroups, currentGroup, selectGroup, navigate]);

  const activeGroupJid = groupFolder ? routeGroupJid : currentGroup;
  const chatViewRef = useRef<HTMLDivElement>(null);

  const handleBackToList = () => {
    navigate('/chat');
  };

  // Handle workspace selection
  const handleWorkspaceSelect = (jid: string, folder: string) => {
    selectGroup(jid);
    navigate(`/chat/${folder}`);
  };

  // Default to show inspector when group is selected
  useEffect(() => {
    if (activeGroupJid && !inspectorOpen) {
      toggleInspector();
    }
  }, [activeGroupJid]);

  return (
    <div className="h-full flex">
      {/* Left Panel: Workspace List */}
      <div
        className={cn(
          'flex-shrink-0 border-r transition-all duration-200 overflow-hidden',
          leftPanelVisible ? 'w-[220px]' : 'w-0'
        )}
      >
        <WorkspaceList
          className="h-full"
          onWorkspaceSelect={handleWorkspaceSelect}
        />
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {activeGroupJid ? (
          <div ref={chatViewRef} className="h-full flex flex-col">
            {/* Header with panel toggles */}
            <div className="flex items-center justify-between px-3 py-2 border-b bg-background">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0"
                  onClick={() => setLeftPanelVisible(!leftPanelVisible)}
                  title={leftPanelVisible ? '隐藏工作区列表' : '显示工作区列表'}
                >
                  {leftPanelVisible ? (
                    <PanelLeftClose className="w-4 h-4" />
                  ) : (
                    <PanelLeftOpen className="w-4 h-4" />
                  )}
                </Button>
                <span className="text-sm font-medium">
                  {groups[activeGroupJid]?.name || '工作区'}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={toggleInspector}
                title={inspectorOpen ? '隐藏检查器' : '显示检查器'}
              >
                {inspectorOpen ? (
                  <PanelRightClose className="w-4 h-4" />
                ) : (
                  <PanelRightOpen className="w-4 h-4" />
                )}
              </Button>
            </div>

            {/* Middle Area: Chat + Inspector */}
            <div className="flex-1 flex overflow-hidden min-h-0">
              {/* Chat View */}
              <div className="flex-1 min-w-0">
                <ChatView groupJid={activeGroupJid} onBack={handleBackToList} />
              </div>

              {/* Right Panel: Inspector */}
              {inspectorOpen && (
                <div
                  className="flex-shrink-0 border-l transition-all duration-200 overflow-hidden"
                  style={{ width: RIGHT_PANEL_WIDTH }}
                >
                  <InspectorPanel
                    className="h-full"
                    groupJid={activeGroupJid}
                  />
                </div>
              )}
            </div>

            {/* Bottom Panel */}
            <div className="flex-shrink-0">
              <BottomPanel groupJid={activeGroupJid} />
            </div>
          </div>
        ) : (
          // Welcome screen when no group selected
          <div className="hidden lg:flex flex-1 items-center justify-center bg-background">
            <div className="text-center max-w-sm">
              <div className="w-16 h-16 rounded-2xl overflow-hidden mx-auto mb-6">
                <img
                  src={`${import.meta.env.BASE_URL}icons/icon-192.png`}
                  alt="NanoGridBot"
                  className="w-full h-full object-cover"
                />
              </div>
              <h2 className="text-xl font-semibold text-slate-900 mb-2">
                欢迎使用 {appearance?.appName || 'NanoGridBot'}
              </h2>
              <p className="text-slate-500 text-sm">
                从左侧选择一个工作区开始对话
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
