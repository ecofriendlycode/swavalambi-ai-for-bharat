import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ArrowLeft, Mail, Lock, Eye, EyeOff } from "lucide-react";
import heroBanner from "../assets/herobanner.png";

const API_BASE = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : "http://localhost:8000/api";

export default function Login() {
  const [identifier, setIdentifier] = useState(""); // email
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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

      {/* Hero Banner */}
      <div className="px-4 py-3">
        <div 
          className="w-full bg-center bg-no-repeat bg-cover flex flex-col justify-end overflow-hidden rounded-xl min-h-[240px] shadow-sm"
          style={{
            backgroundImage: `url(${heroBanner})`
          }}
        />
      </div>

      {/* Welcome Text */}
      <div className="px-6 pt-6 pb-2">
        <h2 className="text-slate-900 tracking-tight text-[32px] font-bold leading-tight text-center">
          Welcome Back
        </h2>
        <p className="text-slate-600 text-base text-center mt-2">
          Log in to continue your journey
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
            Email or Phone Number
          </p>
          <div className="relative">
            <input
              className="flex w-full rounded-xl text-slate-900 border-none bg-slate-200/50 focus:ring-2 focus:ring-primary h-14 placeholder:text-slate-500 px-4 text-base font-normal outline-none transition-all"
              placeholder="Enter your email or phone"
              type="text"
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
            <input
              className="flex w-full rounded-xl text-slate-900 border-none bg-slate-200/50 focus:ring-2 focus:ring-primary h-14 placeholder:text-slate-500 px-4 pr-12 text-base font-normal outline-none transition-all"
              placeholder="Enter your password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setError("");
              }}
              onKeyDown={(e) => e.key === "Enter" && handlePasswordLogin()}
              autoComplete="current-password"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 cursor-pointer transition-colors focus:outline-none"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
            </button>
          </div>
        </label>

        {/* Forgot Password */}
        <div className="flex justify-end -mt-2">
          <Link to="#" className="text-primary text-sm font-semibold hover:underline">
            Forgot Password?
          </Link>
        </div>

        <div className="pt-2 flex flex-col gap-3">
          <button
            onClick={handlePasswordLogin}
            disabled={loading}
            className="w-full bg-primary hover:bg-primary-dark text-white font-bold py-4 rounded-xl shadow-lg transition-all active:scale-[0.98] flex justify-center disabled:opacity-60"
          >
            {loading ? "Signing in…" : "Login"}
          </button>
        </div>

        <p className="text-center text-slate-500 text-sm mt-4">
          Don't have an account?{" "}
          <Link
            to="/register"
            className="text-primary font-bold hover:underline"
          >
            Sign Up
          </Link>
        </p>

        {/* Quick skip for demo */}
        <button
          onClick={() => {
            localStorage.setItem("swavalambi_user_id", "demo");
            localStorage.setItem("swavalambi_name", "Demo User");
            navigate("/assistant");
          }}
          className="text-center text-slate-400 text-xs underline mt-2"
        >
          Skip login (demo mode)
        </button>
      </div>
    </div>
  );
}
