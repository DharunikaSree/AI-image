import { FormEvent, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { LogIn } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export default function LoginPage() {
  const { login } = useAuth();
  const { push } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      push("Welcome back!", "success");
      const pendingFile = location.state?.pendingFile;
      navigate("/search", { state: { initialFile: pendingFile } });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[80vh] max-w-md flex-col justify-center px-6 py-16">
      <div className="card p-8">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-charcoal-900 text-white">
          <LogIn size={18} />
        </div>
        <h1 className="mt-5 font-display text-2xl font-semibold text-charcoal-900 dark:text-white">Welcome back</h1>
        <p className="mt-1 text-sm text-charcoal-400">Log in to search by image and view your saved styles.</p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-charcoal-600 dark:text-charcoal-300">Email</label>
            <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-charcoal-600 dark:text-charcoal-300">Password</label>
            <input className="input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
          {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? "Logging in..." : "Log In"}
          </button>
        </form>

        <div className="mt-5 rounded-xl bg-sand-50 p-3.5 text-xs text-charcoal-600 dark:bg-charcoal-700 dark:text-charcoal-300">
          <div className="font-semibold text-charcoal-800 dark:text-white mb-1.5">Quick Test Accounts:</div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => { setEmail("demo@fashionai.dev"); setPassword("demo1234"); }}
              className="rounded-lg bg-white px-2.5 py-1 text-xs font-medium text-charcoal-800 shadow-sm transition hover:bg-rose-50 hover:text-rose-600 dark:bg-charcoal-800 dark:text-charcoal-200"
            >
              Demo User (demo@fashionai.dev)
            </button>
            <button
              type="button"
              onClick={() => { setEmail("admin@fashionai.dev"); setPassword("admin1234"); }}
              className="rounded-lg bg-white px-2.5 py-1 text-xs font-medium text-charcoal-800 shadow-sm transition hover:bg-rose-50 hover:text-rose-600 dark:bg-charcoal-800 dark:text-charcoal-200"
            >
              Admin (admin@fashionai.dev)
            </button>
          </div>
        </div>

        <p className="mt-6 text-center text-sm text-charcoal-400">
          Don't have an account? <Link to="/register" className="font-semibold text-rose-500">Sign up</Link>
        </p>
      </div>
    </div>
  );
}
