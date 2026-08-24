import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Camera, Heart, History, LayoutDashboard, LogOut, Menu, User as UserIcon, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm font-medium transition hover:text-rose-500 ${isActive ? "text-charcoal-900 dark:text-white" : "text-charcoal-500"}`;

  return (
    <header className="sticky top-0 z-50 border-b border-charcoal-100 bg-canvas-light/90 backdrop-blur-md dark:bg-canvas-dark/90 dark:border-charcoal-700">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link to="/" className="font-display text-xl font-semibold tracking-tight text-charcoal-900 dark:text-white">
          Lumière
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          <NavLink to="/search" className={linkClass}>Search by Image</NavLink>
          <NavLink to="/catalog" className={linkClass}>Explore Styles</NavLink>
          {user && <NavLink to="/favorites" className={linkClass}>Favorites</NavLink>}
          {user && <NavLink to="/history" className={linkClass}>History</NavLink>}
          {user?.is_admin && <NavLink to="/admin" className={linkClass}>Admin</NavLink>}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          {user ? (
            <>
              <Link to="/profile" className="flex items-center gap-2 rounded-full border border-charcoal-200 px-4 py-2 text-sm font-medium text-charcoal-700 hover:border-charcoal-400 dark:border-charcoal-600 dark:text-white">
                <UserIcon size={15} /> {user.name.split(" ")[0]}
              </Link>
              <button
                onClick={() => { logout(); navigate("/"); }}
                className="flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-medium text-charcoal-500 hover:text-rose-500"
              >
                <LogOut size={15} /> Logout
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn-secondary !px-5 !py-2 text-sm">Login</Link>
              <Link to="/register" className="btn-primary !px-5 !py-2 text-sm">Sign Up</Link>
            </>
          )}
        </div>

        <button className="md:hidden" onClick={() => setOpen((o) => !o)} aria-label="Toggle menu">
          {open ? <X /> : <Menu />}
        </button>
      </div>

      {open && (
        <div className="border-t border-charcoal-100 px-6 py-4 md:hidden dark:border-charcoal-700">
          <div className="flex flex-col gap-4">
            <Link to="/search" onClick={() => setOpen(false)} className="flex items-center gap-2 text-sm font-medium"><Camera size={16} /> Search by Image</Link>
            <Link to="/catalog" onClick={() => setOpen(false)} className="text-sm font-medium">Explore Styles</Link>
            {user && <Link to="/favorites" onClick={() => setOpen(false)} className="flex items-center gap-2 text-sm font-medium"><Heart size={16} /> Favorites</Link>}
            {user && <Link to="/history" onClick={() => setOpen(false)} className="flex items-center gap-2 text-sm font-medium"><History size={16} /> History</Link>}
            {user?.is_admin && <Link to="/admin" onClick={() => setOpen(false)} className="flex items-center gap-2 text-sm font-medium"><LayoutDashboard size={16} /> Admin</Link>}
            {user ? (
              <button onClick={() => { logout(); setOpen(false); navigate("/"); }} className="text-left text-sm font-medium text-rose-500">Logout</button>
            ) : (
              <div className="flex gap-3 pt-2">
                <Link to="/login" onClick={() => setOpen(false)} className="btn-secondary flex-1 text-sm">Login</Link>
                <Link to="/register" onClick={() => setOpen(false)} className="btn-primary flex-1 text-sm">Sign Up</Link>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
