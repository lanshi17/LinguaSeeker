import { useLocation, Outlet } from "react-router-dom";

/**
 * Drop-in replacement for bare `<Outlet />` that applies a fade-in animation
 * on every route change. Uses the location pathname as a React key so the
 * page component re-mounts, and the `page-fade-in` CSS class handles the
 * visual transition (280ms, gentle upward drift).
 *
 * `prefers-reduced-motion: reduce` collapses all animations to 0.01ms.
 */
export function AnimatedOutlet() {
  const { pathname } = useLocation();

  return (
    <div key={pathname} className="page-fade-in">
      <Outlet />
    </div>
  );
}
