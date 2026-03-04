import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ArrowLeft, Mail, Lock } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : "http://localhost:8000/api";

export default function Login() {
  const [identifier, setIdentifier] = useState(""); // email
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handlePasswordLogin = async () => {
    if (!identifier.trim() || !password.trim()) {
      setError("Please enter your email and password.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Invalid credentials. Please try again.");
        return;
      }
      const data = await res.json();
      localStorage.setItem("swavalambi_user_id", data.user_id || identifier);
      localStorage.setItem("swavalambi_name", data.name || "");
      navigate("/assistant");
    } catch {
      setError("Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex h-auto min-h-screen w-full flex-col bg-background-light overflow-x-hidden">
      {/* Header */}
      <div className="flex items-center p-4 pb-2 justify-between">
        <div className="text-slate-900 flex size-12 shrink-0 items-center justify-start">
          <ArrowLeft
            size={24}
            onClick={() => navigate(-1)}
            className="cursor-pointer"
          />
        </div>
        <h2 className="text-slate-900 text-lg font-bold leading-tight tracking-[-0.015em] flex-1 text-center pr-12">
          Swavalambi
        </h2>
      </div>

      {/* Form */}
      <div className="px-6 pt-6 pb-2">
        <h2 className="text-slate-900 tracking-tight text-[28px] font-bold leading-tight text-center">
          Sign In
        </h2>
        <p className="text-slate-600 text-base text-center mt-2">
          Enter your email and password to continue
        </p>
      </div>

      {error && (
        <div className="mx-6 mb-2 bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded-xl">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-y-4 px-6 py-4 max-w-[480px] mx-auto w-full">
        {/* Email field */}
        <label className="flex flex-col w-full">
          <p className="text-slate-700 text-sm font-semibold leading-normal pb-2">
            Email Address
          </p>
          <div className="relative">
            <Mail size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              className="flex w-full rounded-xl text-slate-900 border border-slate-200 bg-slate-100/60 focus:border-primary focus:ring-2 focus:ring-primary/20 h-14 placeholder:text-slate-400 pl-11 pr-4 text-base font-normal outline-none transition-all"
              placeholder="name@email.com"
              type="email"
              value={identifier}
              onChange={(e) => {
                setIdentifier(e.target.value);
                setError("");
              }}
              autoComplete="username"
            />
          </div>
        </label>

        {/* Password field */}
        <label className="flex flex-col w-full">
          <p className="text-slate-700 text-sm font-semibold leading-normal pb-2">
            Password
          </p>
          <div className="relative">
            <Lock size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              className="flex w-full rounded-xl text-slate-900 border border-slate-200 bg-slate-100/60 focus:border-primary focus:ring-2 focus:ring-primary/20 h-14 placeholder:text-slate-400 pl-11 pr-4 text-base font-normal outline-none transition-all"
              placeholder="Enter your password"
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setError("");
              }}
              onKeyDown={(e) => e.key === "Enter" && handlePasswordLogin()}
              autoComplete="current-password"
            />
          </div>
        </label>

        <div className="pt-1 flex flex-col gap-3">
          <button
            onClick={handlePasswordLogin}
            disabled={loading}
            className="w-full bg-primary hover:bg-primary-dark text-white font-bold py-4 rounded-xl shadow-lg transition-all active:scale-[0.98] flex justify-center disabled:opacity-60"
          >
            {loading ? "Signing in…" : "Sign In →"}
          </button>
        </div>

        <p className="text-center text-slate-500 text-sm">
          Don't have an account?{" "}
          <Link
            to="/register"
            className="text-primary font-bold hover:underline"
          >
            Register
          </Link>
        </p>

        {/* Quick skip for demo */}
        <button
          onClick={() => {
            localStorage.setItem("swavalambi_user_id", "demo");
            localStorage.setItem("swavalambi_name", "Demo User");
            navigate("/assistant");
          }}
          className="text-center text-slate-400 text-xs underline"
        >
          Skip login (demo mode)
        </button>
      </div>
    </div>
  );
}
