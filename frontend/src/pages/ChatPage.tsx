import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useChatStore } from '../stores/chat';
import { useAuthStore } from '../stores/auth';
import { WorkspaceList } from '../components/console/WorkspaceList';
import { InspectorPanel } from '../components/console/InspectorPanel';
import { BottomPanel } from '../components/console/BottomPanel';
import { ChatView } from '../components/chat/ChatView';
import {
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Menu,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger, SheetClose } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';

// Panel width constants
const RIGHT_PANEL_WIDTH = 300;

export function ChatPage() {
  const { groupFolder } = useParams<{ groupFolder?: string }>();
  const navigate = useNavigate();
  const { groups, currentGroup, selectGroup, inspectorOpen, toggleInspector } = useChatStore();

  // Responsive breakpoints: lg (≥1024px), md (≥768px)
  const [isDesktop, setIsDesktop] = useState(true);
  const [isTablet, setIsTablet] = useState(false);
  const [leftPanelVisible, setLeftPanelVisible] = useState(true);
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);
  const [inspectorDrawerOpen, setInspectorDrawerOpen] = useState(false);

  // Detect screen size
  useEffect(() => {
    const checkScreenSize = () => {
      const width = window.innerWidth;
      setIsDesktop(width >= 1024);
      setIsTablet(width >= 768 && width < 1024);
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

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
      {/* Desktop: Left Panel (always visible) */}
      {isDesktop && (
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
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {activeGroupJid ? (
          <div ref={chatViewRef} className="h-full flex flex-col">
            {/* Header with panel toggles */}
            <div className="flex items-center justify-between px-3 py-2 border-b bg-background">
              <div className="flex items-center gap-2">
                {/* Mobile/Tablet: Menu button to open workspace drawer */}
                {!isDesktop && (
                  <Sheet open={leftDrawerOpen} onOpenChange={setLeftDrawerOpen}>
                    <SheetTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0"
                        title="工作区列表"
                      >
                        <Menu className="w-4 h-4" />
                      </Button>
                    </SheetTrigger>
                    <SheetContent side="left" className="w-[280px] p-0">
                      <div className="h-full flex flex-col">
                        <div className="flex items-center justify-between px-3 py-2 border-b">
                          <span className="text-sm font-medium">工作区</span>
                          <SheetClose asChild>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                              <X className="w-4 h-4" />
                            </Button>
                          </SheetClose>
                        </div>
                        <div className="flex-1 overflow-hidden">
                          <WorkspaceList
                            className="h-full"
                            onWorkspaceSelect={(jid, folder) => {
                              handleWorkspaceSelect(jid, folder);
                              setLeftDrawerOpen(false);
                            }}
                          />
                        </div>
                      </div>
                    </SheetContent>
                  </Sheet>
                )}

                {/* Desktop: Toggle left panel */}
                {isDesktop && (
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
                )}

                <span className="text-sm font-medium truncate max-w-[150px] sm:max-w-[200px]">
                  {groups[activeGroupJid]?.name || '工作区'}
                </span>
              </div>

              {/* Desktop/Tablet: Toggle inspector button */}
              {(isDesktop || isTablet) && (
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
              )}
            </div>

            {/* Middle Area: Chat + Inspector */}
            <div className="flex-1 flex overflow-hidden min-h-0">
              {/* Chat View */}
              <div className="flex-1 min-w-0">
                <ChatView groupJid={activeGroupJid} onBack={handleBackToList} />
              </div>

              {/* Desktop: Inline Inspector Panel */}
              {isDesktop && inspectorOpen && (
                <div
                  className="flex-shrink-0 border-l transition-all duration-200 overflow-hidden"
                  style={{ width: RIGHT_PANEL_WIDTH }}
                >
                  <InspectorPanel className="h-full" groupJid={activeGroupJid} />
                </div>
              )}

              {/* Tablet: Inspector as Sheet drawer */}
              {isTablet && (
                <Sheet open={inspectorDrawerOpen} onOpenChange={setInspectorDrawerOpen}>
                  <SheetTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute right-2 top-2 h-8 w-8 p-0"
                      title="检查器"
                    >
                      <PanelRightOpen className="w-4 h-4" />
                    </Button>
                  </SheetTrigger>
                  <SheetContent side="right" className="w-[300px] p-0">
                    <div className="h-full flex flex-col">
                      <div className="flex items-center justify-between px-3 py-2 border-b">
                        <span className="text-sm font-medium">检查器</span>
                        <SheetClose asChild>
                          <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                            <X className="w-4 h-4" />
                          </Button>
                        </SheetClose>
                      </div>
                      <div className="flex-1 overflow-hidden">
                        <InspectorPanel className="h-full" groupJid={activeGroupJid} />
                      </div>
                    </div>
                  </SheetContent>
                </Sheet>
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
