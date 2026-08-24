import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center px-6 text-center">
      <div className="font-display text-6xl font-semibold text-charcoal-900 dark:text-white">404</div>
      <p className="mt-3 text-charcoal-500 dark:text-charcoal-300">This page doesn't exist — but your next great outfit find might.</p>
      <Link to="/" className="btn-primary mt-6">Back to Home</Link>
    </div>
  );
}
