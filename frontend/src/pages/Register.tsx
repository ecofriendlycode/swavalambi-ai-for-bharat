import { useState, FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { User, Phone, Mail, Lock } from "lucide-react";

const API_BASE = "http://localhost:8000/api";

export default function Register() {
  const navigate = useNavigate();
  const [name, setName]     = useState("");
  const [phone, setPhone]   = useState("");
  const [email, setEmail]   = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp]       = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState("");
  const [authMethod, setAuthMethod] = useState<"otp" | "password">("otp");
  const [password, setPassword] = useState("");

  // OTP is sent to phone (primary). Email is stored for records.
  const handleSendOtp = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError("Please enter your full name."); return; }
    if (!phone.trim()) { setError("Please enter your mobile number."); return; }
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Please enter a valid email address."); return;
    }
    setLoading(true);
    setError("");
    try {
      await fetch(`${API_BASE}/auth/send-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: phone, email, name }),
      });
      setOtpSent(true);
    } catch {
      setError("Could not send OTP. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async () => {
    if (!otp.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: phone, email, name, otp }),
      });
      if (!res.ok) { setError("Invalid OTP. Please try again."); return; }
      const data = await res.json();
      localStorage.setItem("swavalambi_user_id", data.user_id || phone);
      localStorage.setItem("swavalambi_name", data.name || name);
      navigate("/assistant");
    } catch {
      setError("Verification failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordRegister = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError("Please enter your full name."); return; }
    if (!phone.trim()) { setError("Please enter your mobile number."); return; }
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Please enter a valid email address."); return;
    }
    if (!password.trim() || password.length < 6) {
      setError("Password must be at least 6 characters."); return;
    }
    
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: phone, email, name, password }),
      });
      if (!res.ok) { setError("Registration failed. Please try again."); return; }
      const data = await res.json();
      localStorage.setItem("swavalambi_user_id", data.user_id || phone);
      localStorage.setItem("swavalambi_name", data.name || name);
      navigate("/assistant");
    } catch {
      setError("Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-white">
      {/* Header gradient */}
      <header
        className="pt-12 pb-14 px-6 text-center text-white"
        style={{ background: "linear-gradient(135deg, #ff8c00 0%, #ffb347 80%, #ffe0b2 100%)" }}
      >
        <h1 className="text-3xl font-extrabold tracking-tight">Swavalambi</h1>
        <p className="text-sm text-white/80 mt-1">Skills to Self-Reliance</p>
      </header>

      <section className="flex-1 bg-white px-6 pt-6 rounded-t-3xl -mt-6 overflow-y-auto shadow-[0_-4px_24px_rgba(0,0,0,0.08)]">
        {/* Title */}
        <div className="mb-5">
          <h2 className="text-2xl font-bold text-gray-800">
            {otpSent ? "Verify Phone" : "Create Account"}
          </h2>
          <p className="text-gray-500 text-sm mt-0.5">
            {otpSent
              ? `OTP sent to +91${phone} (hint: 123456)`
              : "Join our community of skilled professionals"}
          </p>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded-xl">
            {error}
          </div>
        )}

        {!otpSent ? (
          <form className="space-y-4" onSubmit={authMethod === "otp" ? handleSendOtp : handlePasswordRegister}>
            {/* Full Name */}
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                Full Name
              </label>
              <div className="relative">
                <User size={17} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  className="w-full pl-10 pr-4 py-3 border border-transparent rounded-xl outline-none bg-gray-50 text-gray-800 focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
                  placeholder="Enter your full name"
                  required type="text"
                  value={name} onChange={(e) => setName(e.target.value)}
                />
              </div>
            </div>

            {/* Mobile Number */}
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                Mobile Number <span className="text-primary">*</span>
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400 font-semibold text-sm select-none">
                  +91
                </span>
                <input
                  className="w-full pl-12 pr-4 py-3 border border-transparent rounded-xl outline-none bg-gray-50 text-gray-800 focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
                  pattern="[0-9]{10}"
                  placeholder="98765 43210"
                  required type="tel"
                  inputMode="numeric"
                  maxLength={10}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                />
              </div>
              <p className="text-[11px] text-gray-400 pl-1">OTP will be sent here for verification</p>
            </div>

            {/* Email */}
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                Email Address <span className="text-primary">*</span>
              </label>
              <div className="relative">
                <Mail size={17} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  className="w-full pl-10 pr-4 py-3 border border-transparent rounded-xl outline-none bg-gray-50 text-gray-800 focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
                  placeholder="you@example.com"
                  required type="email"
                  inputMode="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <p className="text-[11px] text-gray-400 pl-1">For account recovery and important updates</p>
            </div>

            {authMethod === "password" && (
              <div className="space-y-1 animate-in fade-in slide-in-from-top-2 duration-300">
                <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                  Create Password <span className="text-primary">*</span>
                </label>
                <div className="relative">
                  <Lock size={17} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    className="w-full pl-10 pr-4 py-3 border border-transparent rounded-xl outline-none bg-gray-50 text-gray-800 focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
                    placeholder="Create a strong password"
                    required type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              </div>
            )}

            <div className="pt-2 flex flex-col gap-3">
              <button
                type="submit" disabled={loading}
                className="bg-primary hover:bg-primary-dark text-white w-full py-4 rounded-xl font-bold text-lg shadow-md active:scale-[0.98] transition-all disabled:opacity-60"
              >
                {loading ? (authMethod === "otp" ? "Sending OTP…" : "Creating Account…") : (authMethod === "otp" ? "Get Started →" : "Create Account →")}
              </button>
              
              <button
                type="button"
                onClick={() => setAuthMethod(authMethod === "otp" ? "password" : "otp")}
                className="text-center text-sm font-semibold text-slate-500 hover:text-slate-800 transition-colors"
              >
                {authMethod === "otp" ? "Use a password instead" : "Use OTP instead"}
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-4">
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                OTP Code
              </label>
              <div className="relative">
                <Lock size={17} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  className="w-full pl-10 pr-4 py-3 border border-transparent rounded-xl outline-none bg-gray-50 text-gray-800 text-center text-2xl font-bold tracking-widest focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
                  maxLength={6}
                  placeholder="• • • • • •"
                  inputMode="numeric"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                  onKeyDown={(e) => e.key === "Enter" && handleVerifyOtp()}
                />
              </div>
            </div>
            <button
              onClick={handleVerifyOtp} disabled={loading}
              className="bg-primary hover:bg-primary-dark text-white w-full py-4 rounded-xl font-bold text-lg shadow-md active:scale-[0.98] transition-all disabled:opacity-60"
            >
              {loading ? "Verifying…" : "Verify & Create Account →"}
            </button>
            <button
              onClick={() => { setOtpSent(false); setOtp(""); setError(""); }}
              className="w-full bg-gray-100 text-gray-600 py-3 rounded-xl font-semibold hover:bg-gray-200 transition-all"
            >
              ← Back
            </button>
          </div>
        )}

        <footer className="text-center mt-6 pb-10">
          <p className="text-sm text-gray-500">
            Already have an account?{" "}
            <Link to="/login" className="text-primary font-bold hover:underline">
              Log In
            </Link>
          </p>
        </footer>
      </section>
    </div>
  );
}
