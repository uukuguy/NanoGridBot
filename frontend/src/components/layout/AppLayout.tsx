import { Outlet } from 'react-router-dom';
import { NavRail } from './NavRail';

export function AppLayout() {
  return (
    <div className="h-screen supports-[height:100dvh]:h-dvh flex flex-row overflow-hidden">
      <div className="h-full">
        <NavRail />
      </div>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
