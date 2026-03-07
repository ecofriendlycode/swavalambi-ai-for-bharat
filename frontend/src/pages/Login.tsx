import { useState, useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ArrowLeft, Mail, Lock, Eye, EyeOff } from "lucide-react";
import heroBanner from "../assets/herobanner.png";
import carpentry from "../assets/carpentry.png";
import plumbing from "../assets/plumbing.png";
import tailor from "../assets/tailor.png";
import { API_BASE } from "../config/api";

export default function Login() {
  const [identifier, setIdentifier] = useState(""); // email
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const navigate = useNavigate();
  const scrollRef = useRef<HTMLDivElement>(null);

  const images = [heroBanner, carpentry, plumbing, tailor];

  // Check for success message from navigation state
  useEffect(() => {
    const state = window.history.state?.usr;
    if (state?.message) {
      setSuccessMessage(state.message);
      // Clear the message after 5 seconds
      setTimeout(() => setSuccessMessage(""), 5000);
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % images.length);
    }, 3000); // Auto-swipe every 3 seconds

    return () => clearInterval(interval);
  }, [images.length]);

  useEffect(() => {
    if (scrollRef.current) {
      const scrollWidth = scrollRef.current.scrollWidth / images.length;
      scrollRef.current.scrollTo({
        left: scrollWidth * currentIndex,
        behavior: 'smooth'
      });
    }
  }, [currentIndex, images.length]);

  const handlePasswordLogin = async () => {
    if (!identifier.trim() || !password.trim()) {
      setError("Please enter your email and password.");
      return;
    }
    
    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(identifier)) {
      setError("Please enter a valid email address.");
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

      {/* Hero Banner Carousel */}
      <div className="px-4 py-3">
        <div 
          ref={scrollRef}
          className="w-full overflow-x-auto overflow-y-hidden rounded-xl shadow-sm snap-x snap-mandatory hide-scrollbar"
        >
          <div className="flex min-h-[240px]">
            {images.map((img, idx) => (
              <div
                key={idx}
                className="flex-shrink-0 w-full bg-center bg-no-repeat bg-cover rounded-xl snap-center"
                style={{
                  backgroundImage: `url(${img})`,
                  minHeight: '240px'
                }}
              />
            ))}
          </div>
        </div>
        {/* Dots indicator */}
        <div className="flex justify-center gap-2 mt-3">
          {images.map((_, idx) => (
            <div
              key={idx}
              className={`h-2 rounded-full transition-all ${
                idx === currentIndex ? 'w-6 bg-primary' : 'w-2 bg-slate-300'
              }`}
            />
          ))}
        </div>
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

      {successMessage && (
        <div className="mx-6 mb-2 bg-green-50 border border-green-200 text-green-700 text-sm p-3 rounded-xl">
          {successMessage}
        </div>
      )}

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
            <input
              className="flex w-full rounded-xl text-slate-900 border-none bg-slate-200/50 focus:ring-2 focus:ring-primary h-14 placeholder:text-slate-500 px-4 text-base font-normal outline-none transition-all"
              placeholder="Enter your email"
              type="email"
              inputMode="email"
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
