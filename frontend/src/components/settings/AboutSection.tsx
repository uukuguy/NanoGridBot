import { Github, ExternalLink, Heart, Code2 } from 'lucide-react';

export function AboutSection() {
  return (
    <div className="space-y-6">
      {/* 项目信息 */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-1">NanoGridBot</h2>
        <p className="text-sm text-slate-500">Agent Dev Console & Lightweight Runtime</p>
      </div>

      {/* 开源地址 */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Github className="w-4 h-4 text-slate-400 shrink-0" />
          <a
            href="https://github.com/nickerso/NanoGridBot"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-teal-600 hover:text-teal-700 inline-flex items-center gap-1"
          >
            NanoGridBot
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
        <div className="flex items-center gap-3">
          <Code2 className="w-4 h-4 text-slate-400 shrink-0" />
          <span className="text-sm text-slate-700">Agent Development Console</span>
        </div>
      </div>

      <hr className="border-slate-100" />

      {/* 设计哲学 */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Heart className="w-4 h-4 text-rose-500" />
          <h3 className="text-sm font-medium text-slate-900">设计哲学</h3>
        </div>
        <p className="text-sm text-slate-600 leading-relaxed">
          站在巨人的肩膀上，基于 Claude Code（全世界最好的 Agent）构建。
          提供轻量、快速、功能强大的 Agent 开发调试控制台。
        </p>
      </div>
    </div>
  );
}
