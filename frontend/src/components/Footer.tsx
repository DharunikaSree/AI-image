import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer className="border-t border-charcoal-100 py-12 dark:border-charcoal-700">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid gap-8 md:grid-cols-4">
          <div>
            <div className="font-display text-lg font-semibold text-charcoal-900 dark:text-white">Lumière</div>
            <p className="mt-3 text-sm text-charcoal-400">
              Upload a photo. Discover the style. Find where to buy it — for less.
            </p>
          </div>
          <div>
            <div className="text-sm font-semibold text-charcoal-800 dark:text-white">Product</div>
            <ul className="mt-3 space-y-2 text-sm text-charcoal-400">
              <li><Link to="/search" className="hover:text-rose-500">Search by Image</Link></li>
              <li><Link to="/catalog" className="hover:text-rose-500">Explore Styles</Link></li>
              <li><Link to="/favorites" className="hover:text-rose-500">Favorites</Link></li>
            </ul>
          </div>
          <div>
            <div className="text-sm font-semibold text-charcoal-800 dark:text-white">Account</div>
            <ul className="mt-3 space-y-2 text-sm text-charcoal-400">
              <li><Link to="/login" className="hover:text-rose-500">Login</Link></li>
              <li><Link to="/register" className="hover:text-rose-500">Sign Up</Link></li>
              <li><Link to="/profile" className="hover:text-rose-500">Preferences</Link></li>
            </ul>
          </div>
          <div>
            <div className="text-sm font-semibold text-charcoal-800 dark:text-white">About this project</div>
            <p className="mt-3 text-sm text-charcoal-400">
              A final-year engineering demo. Product catalog and AI run in demo mode unless a trained model is configured.
            </p>
          </div>
        </div>
        <div className="mt-10 border-t border-charcoal-100 pt-6 text-xs text-charcoal-300 dark:border-charcoal-700">
          © {new Date().getFullYear()} Lumière — AI Fashion Search. Built for demonstration purposes.
        </div>
      </div>
    </footer>
  );
}
