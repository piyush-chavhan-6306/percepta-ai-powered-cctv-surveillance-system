import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import {
  signInOperator,
  signUpOperator,
  signInOAuth,
  resetOperatorPassword,
} from "../lib/supabaseClient";
import { StarsBackground } from "../components/StarsBackground";
import { PerceptaLogo } from "../components/PerceptaLogo";
import { ShieldAlert, Check, ChevronRight, Menu, X } from "lucide-react";
import "../WorldMotion.css";

export default function Auth() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get("returnTo") || "/dashboard";

  const [mode, setMode] = useState<"signin" | "request">("signin");
  const [email, setEmail] = useState("callsign@defense.percepta.ai");
  const [password, setPassword] = useState("••••••••••••••••");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (mode === "request") {
      if (password !== confirmPassword) {
        setErrorMessage("PASSPHRASES DO NOT MATCH // VERIFICATION FAILED");
        return;
      }
      if (password.length < 6) {
        setErrorMessage("PASSPHRASE LENGTH INSUFFICIENT // MINIMUM 6 CHARACTERS");
        return;
      }
    }

    setIsLoading(true);

    try {
      if (mode === "signin") {
        const res = await signInOperator(email, password);
        if (res.success) {
          navigate(returnTo);
        } else {
          setErrorMessage(res.error || "ACCESS DENIED // INVALID OPERATOR CREDENTIALS");
        }
      } else {
        const res = await signUpOperator(email, password);
        if (res.success) {
          setSuccessMessage("OPERATOR CLEARANCE REGISTERED // LOGGING IN...");
          setTimeout(() => navigate(returnTo), 800);
        } else {
          setErrorMessage(res.error || "CLEARANCE REGISTRATION REJECTED");
        }
      }
    } catch (err: any) {
      setErrorMessage(err?.message || "GATEWAY HANDSHAKE TIMEOUT");
    } finally {
      setIsLoading(false);
    }
  };

  const handleOAuth = async (provider: "google" | "github" | "azure") => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await signInOAuth(provider);
      if (res.success) {
        navigate(returnTo);
      } else {
        setErrorMessage(res.error || `${provider.toUpperCase()} FEDERATION ERROR`);
      }
    } catch (err: any) {
      setErrorMessage(err?.message || "SSO GATEWAY TIMEOUT");
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async () => {
    if (!email) {
      setErrorMessage("SPECIFY OPERATOR EMAIL FIRST");
      return;
    }
    setIsLoading(true);
    const res = await resetOperatorPassword(email);
    setIsLoading(false);
    if (res.success) {
      setSuccessMessage("RECOVERY CIPHER DISPATCHED TO C2 MAIL");
    } else {
      setErrorMessage(res.error || "RECOVERY PROTOCOL FAILED");
    }
  };

  return (
    <div className="tactical-auth-page selection:bg-[#33f0b4] selection:text-black">
      {/* ── Scoped Tactical Styles (Preserving Exact Stitch Dimensions) ── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Teko:wght@500;600;700&display=swap');

        .tactical-auth-page {
          min-height: 100vh;
          width: 100%;
          background-color: #080b0e !important;
          color: #cbd5e1;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          padding: 100px 16px 40px 16px;
          box-sizing: border-box;
          font-family: 'JetBrains Mono', monospace;
          position: relative;
          overflow-x: hidden;
        }

        /* Tactical Corner Brackets */
        .tactical-bracket {
          position: relative;
        }
        .tactical-bracket::before,
        .tactical-bracket::after {
          content: "";
          position: absolute;
          width: 8px;
          height: 8px;
          pointer-events: none;
          opacity: 0.8;
          z-index: 10;
        }
        .tactical-bracket::before {
          top: -1px;
          left: -1px;
          border-top: 2px solid #33f0b4 !important;
          border-left: 2px solid #33f0b4 !important;
        }
        .tactical-bracket::after {
          bottom: -1px;
          right: -1px;
          border-bottom: 2px solid #33f0b4 !important;
          border-right: 2px solid #33f0b4 !important;
        }

        /* Tactical Card Frame */
        .tactical-card {
          width: 100%;
          max-width: 490px;
          background-color: rgba(13, 18, 23, 0.95) !important;
          border: 1px solid #1b2530 !important;
          border-radius: 2px !important;
          padding: 28px !important;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6) !important;
          backdrop-filter: blur(12px) !important;
          box-sizing: border-box !important;
          position: relative;
          z-index: 10;
        }

        /* Teko Title */
        .tactical-title {
          font-family: 'Teko', sans-serif !important;
          font-size: 48px !important;
          line-height: 1 !important;
          font-weight: 600 !important;
          text-transform: uppercase !important;
          letter-spacing: 0.025em !important;
          color: #ffffff !important;
          margin: 0 !important;
          white-space: nowrap !important;
        }

        /* Terminal Input */
        .tactical-input {
          width: 100% !important;
          background-color: #080b0f !important;
          border: 1px solid #1b2530 !important;
          color: #e2e8f0 !important;
          font-size: 12px !important;
          font-family: 'JetBrains Mono', monospace !important;
          padding: 10px 14px !important;
          height: 38px !important;
          border-radius: 0 !important;
          outline: none !important;
          box-sizing: border-box !important;
          transition: all 0.15s ease-in-out !important;
        }
        .tactical-input:focus {
          border-color: #33f0b4 !important;
          box-shadow: 0 0 10px rgba(51, 240, 180, 0.12) !important;
        }
        .tactical-input::placeholder {
          color: #475569 !important;
        }

        /* Primary CTA Button */
        .tactical-submit-btn {
          width: 100% !important;
          background-color: #33f0b4 !important;
          color: #000000 !important;
          font-family: 'Chakra Petch', sans-serif !important;
          font-weight: 700 !important;
          font-size: 13px !important;
          padding: 12px 16px !important;
          height: 44px !important;
          text-transform: uppercase !important;
          letter-spacing: 0.2em !important;
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          gap: 8px !important;
          box-shadow: 0 0 15px rgba(51, 240, 180, 0.25) !important;
          cursor: pointer !important;
          border: none !important;
          border-radius: 0 !important;
          transition: all 0.15s ease !important;
        }
        .tactical-submit-btn:hover {
          background-color: #28dfa3 !important;
        }
        .tactical-submit-btn:active {
          transform: scale(0.99) !important;
        }

        /* SSO Button */
        .tactical-sso-btn {
          background-color: #090d12 !important;
          border: 1px solid #1b2632 !important;
          color: #cbd5e1 !important;
          font-size: 10px !important;
          font-family: 'JetBrains Mono', monospace !important;
          padding: 8px 0 !important;
          height: 34px !important;
          letter-spacing: 0.05em !important;
          text-transform: uppercase !important;
          cursor: pointer !important;
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          transition: all 0.15s ease !important;
        }
        .tactical-sso-btn:hover {
          background-color: #111720 !important;
          border-color: #27384a !important;
          color: #ffffff !important;
        }
      `}</style>

      {/* ── 1. Landing Top Navigation Bar (Identical to Landing Page) ── */}
      <header className="public-nav" data-testid="public-navigation">
        <Link to="/" className="flex items-center" data-testid="brand-home">
          <PerceptaLogo size={30} showText={true} />
        </Link>

        <nav className="nav-links">
          <Link to="/#observe" data-testid="nav-features">
            FEATURES
          </Link>
          <Link to="/#track" data-testid="nav-technology">
            TECHNOLOGY
          </Link>
          <Link to="/#assess" data-testid="nav-capabilities">
            CAPABILITIES
          </Link>
          <Link to="/#command" data-testid="nav-about">
            ABOUT
          </Link>
        </nav>

        <div className="nav-actions">
          <Link to="/" className="nav-login">
            LANDING
          </Link>
          <button
            onClick={() => navigate("/dashboard")}
            className="button button-small"
            data-testid="nav-c2"
          >
            ENTER C2 <ChevronRight size={14} />
          </button>
        </div>

        <button
          className="icon-button mobile-menu"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Open menu"
        >
          {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      {/* Mobile Drawer Navigation */}
      {mobileMenuOpen && (
        <div className="mobile-nav" data-testid="mobile-navigation">
          <button onClick={() => setMobileMenuOpen(false)} data-testid="mobile-close-button">
            <X size={20} />
          </button>
          <div className="mb-6">
            <PerceptaLogo size={26} showText={true} />
          </div>
          {["observe", "detect", "track", "understand", "assess", "evidence", "incidents", "command"].map(
            (x) => (
              <Link
                key={x}
                to={`/#${x}`}
                onClick={() => setMobileMenuOpen(false)}
              >
                {x.toUpperCase()}
              </Link>
            )
          )}
          <button
            onClick={() => {
              setMobileMenuOpen(false);
              navigate("/dashboard");
            }}
            className="button mt-6 text-center w-full justify-center"
          >
            LAUNCH C2 CONSOLE →
          </button>
        </div>
      )}

      {/* ── 2. Landing Stars Background (Without Earth Mesh) ── */}
      <StarsBackground className="fixed inset-0 pointer-events-none z-0 opacity-80" speedMultiplier={0.7} />

      {/* Deep Space Vignette (Clean dark void without grid lines or square boxes) */}
      <div
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          background: "radial-gradient(circle at 50% 40%, rgba(14, 22, 32, 0.3) 0%, rgba(5, 7, 10, 0.75) 100%)",
        }}
      />

      {/* ── 3. Main Tactical Terminal Container (max-w-[490px]) ── */}
      <main style={{ width: "100%", maxWidth: "490px", position: "relative", zIndex: 10 }}>
        {/* Main Tactical Frame Card */}
        <div className="tactical-bracket tactical-card" data-purpose="auth-terminal-card">
          {/* Header Section */}
          <header style={{ marginBottom: "24px" }}>
            {/* Clearance & Access Header Line */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: "11px",
                marginBottom: "8px",
                letterSpacing: "0.05em",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: 600, color: "#33f0b4" }}>
                <span style={{ letterSpacing: "0.1em" }}>
                  {mode === "signin" ? "OPERATOR ACCESS" : "CLEARANCE REGISTRATION"}
                </span>
                <span style={{ color: "#64748b" }}>//</span>
                <span>{mode === "signin" ? "AUTH-06" : "REQ-01"}</span>
              </div>
              <div
                style={{
                  border: "1px solid #263544",
                  padding: "2px 8px",
                  fontSize: "10px",
                  color: "#94a3b8",
                  fontFamily: "'JetBrains Mono', monospace",
                  letterSpacing: "0.1em",
                  backgroundColor: "#0a0e13",
                  userSelect: "none",
                }}
              >
                [ CLEARANCE REQ. ]
              </div>
            </div>

            {/* Big Condensed Title in Teko font */}
            <h1 className="tactical-title">COMMAND PORTAL</h1>

            {/* Mode Navigation Tabs */}
            <nav
              style={{
                display: "flex",
                borderBottom: "1px solid #1b2530",
                marginTop: "20px",
                fontSize: "12px",
                fontFamily: "'JetBrains Mono', monospace",
                fontWeight: 500,
                letterSpacing: "0.05em",
              }}
            >
              {/* Active Tab: SIGN IN */}
              <button
                type="button"
                onClick={() => {
                  setMode("signin");
                  setErrorMessage(null);
                  setSuccessMessage(null);
                }}
                style={{
                  padding: "0 12px 10px 12px",
                  marginBottom: "-1px",
                  letterSpacing: "0.1em",
                  display: "flex",
                  alignItems: "center",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontWeight: 600,
                  fontSize: "12px",
                  color: mode === "signin" ? "#33f0b4" : "#64748b",
                  borderBottom: mode === "signin" ? "2px solid #33f0b4" : "2px solid transparent",
                  transition: "color 0.15s ease",
                }}
              >
                SIGN IN
              </button>
              {/* Inactive Tab: REQUEST ACCESS */}
              <button
                type="button"
                onClick={() => {
                  setMode("request");
                  setErrorMessage(null);
                  setSuccessMessage(null);
                  if (password === "••••••••••••••••") {
                    setPassword("");
                  }
                }}
                style={{
                  padding: "0 16px 10px 16px",
                  marginBottom: "-1px",
                  letterSpacing: "0.1em",
                  display: "flex",
                  alignItems: "center",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontWeight: 500,
                  fontSize: "12px",
                  color: mode === "request" ? "#33f0b4" : "#64748b",
                  borderBottom: mode === "request" ? "2px solid #33f0b4" : "2px solid transparent",
                  transition: "color 0.15s ease",
                }}
              >
                REQUEST ACCESS
              </button>
            </nav>
          </header>

          {/* Status Alert Banners */}
          {errorMessage && (
            <div
              style={{
                marginBottom: "16px",
                padding: "10px 12px",
                border: "1px solid rgba(239, 68, 68, 0.4)",
                backgroundColor: "rgba(239, 68, 68, 0.1)",
                fontSize: "11px",
                fontFamily: "'JetBrains Mono', monospace",
                color: "#fca5a5",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <ShieldAlert size={14} style={{ color: "#ef4444", flexShrink: 0 }} />
              <span>{errorMessage}</span>
            </div>
          )}
          {successMessage && (
            <div
              style={{
                marginBottom: "16px",
                padding: "10px 12px",
                border: "1px solid rgba(51, 240, 180, 0.4)",
                backgroundColor: "rgba(51, 240, 180, 0.1)",
                fontSize: "11px",
                fontFamily: "'JetBrains Mono', monospace",
                color: "#33f0b4",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <Check size={14} style={{ color: "#33f0b4", flexShrink: 0 }} />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Authentication Form */}
          <form
            style={{ display: "flex", flexDirection: "column", gap: "16px" }}
            data-purpose="operator-login-form"
            onSubmit={handleSubmit}
          >
            {/* Field: Operator Identifier */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: "10px",
                  fontFamily: "'JetBrains Mono', monospace",
                  letterSpacing: "0.05em",
                }}
              >
                <label
                  style={{ color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}
                  htmlFor="operator-id"
                >
                  OPERATOR IDENTIFIER <span style={{ color: "#475569" }}>//</span> C2 MAIL
                </label>
                <span
                  style={{
                    fontSize: "10px",
                    color: "#64748b",
                    letterSpacing: "0.1em",
                    backgroundColor: "#121820",
                    padding: "1px 6px",
                    border: "1px solid #1e2936",
                    userSelect: "none",
                  }}
                >
                  {mode === "signin" ? "ID-01" : "NEW-ID"}
                </span>
              </div>
              <input
                id="operator-id"
                name="operator_id"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@defense.percepta.ai"
                required
                className="tactical-input"
              />
            </div>

            {/* Field: Access Key / Passphrase */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: "10px",
                  fontFamily: "'JetBrains Mono', monospace",
                  letterSpacing: "0.05em",
                }}
              >
                <label
                  style={{ color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}
                  htmlFor="access-key"
                >
                  {mode === "signin" ? "ACCESS KEY" : "CREATE ACCESS KEY"}{" "}
                  <span style={{ color: "#475569" }}>//</span> PASSPHRASE
                </label>
                {mode === "signin" ? (
                  <button
                    type="button"
                    onClick={handleResetPassword}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#64748b",
                      fontSize: "10px",
                      fontFamily: "'JetBrains Mono', monospace",
                      letterSpacing: "0.05em",
                      cursor: "pointer",
                      textTransform: "uppercase",
                      padding: 0,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "#33f0b4")}
                    onMouseLeave={(e) => (e.currentTarget.style.color = "#64748b")}
                  >
                    ROTATE / RESET?
                  </button>
                ) : (
                  <span style={{ fontSize: "10px", color: "#64748b", letterSpacing: "0.05em" }}>
                    MIN 6 CHARS
                  </span>
                )}
              </div>
              <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                <input
                  id="access-key"
                  name="access_key"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "signin" ? "••••••••••••" : "Enter new passphrase"}
                  required
                  style={{ paddingRight: "56px" }}
                  className="tactical-input"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: "absolute",
                    right: "10px",
                    fontSize: "9px",
                    fontFamily: "'JetBrains Mono', monospace",
                    letterSpacing: "0.05em",
                    color: "#94a3b8",
                    padding: "2px 6px",
                    border: "1px solid #1e2a38",
                    backgroundColor: "#0c1218",
                    cursor: "pointer",
                    textTransform: "uppercase",
                  }}
                  data-purpose="password-visibility-toggle"
                >
                  [ {showPassword ? "HIDE" : "SHOW"} ]
                </button>
              </div>
            </div>

            {/* Field: Confirm Passphrase (Only in Request Access Mode) */}
            {mode === "request" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    fontSize: "10px",
                    fontFamily: "'JetBrains Mono', monospace",
                    letterSpacing: "0.05em",
                  }}
                >
                  <label
                    style={{ color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}
                    htmlFor="confirm-key"
                  >
                    CONFIRM ACCESS KEY <span style={{ color: "#475569" }}>//</span> VERIFY
                  </label>
                  <span style={{ fontSize: "10px", color: "#64748b", letterSpacing: "0.05em" }}>
                    MATCH REQUIRED
                  </span>
                </div>
                <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                  <input
                    id="confirm-key"
                    name="confirm_key"
                    type={showConfirmPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat passphrase"
                    required
                    style={{ paddingRight: "56px" }}
                    className="tactical-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    style={{
                      position: "absolute",
                      right: "10px",
                      fontSize: "9px",
                      fontFamily: "'JetBrains Mono', monospace",
                      letterSpacing: "0.05em",
                      color: "#94a3b8",
                      padding: "2px 6px",
                      border: "1px solid #1e2a38",
                      backgroundColor: "#0c1218",
                      cursor: "pointer",
                      textTransform: "uppercase",
                    }}
                  >
                    [ {showConfirmPassword ? "HIDE" : "SHOW"} ]
                  </button>
                </div>
              </div>
            )}

            {/* Primary Action Button */}
            <div style={{ paddingTop: "8px" }}>
              <button
                type="submit"
                disabled={isLoading}
                className="tactical-submit-btn"
                data-purpose="submit-command-center"
              >
                <span>
                  {isLoading
                    ? mode === "signin"
                      ? "AUTHENTICATING ENCLAVE..."
                      : "REGISTERING OPERATOR..."
                    : mode === "signin"
                    ? "ENTER COMMAND CENTER"
                    : "CREATE OPERATOR ACCOUNT"}
                </span>
                <span style={{ fontSize: "16px", fontWeight: "bold" }}>→</span>
              </button>
            </div>
          </form>

          {/* SSO Section */}
          <div style={{ marginTop: "24px", paddingTop: "16px", borderTop: "1px solid #161f28" }}>
            {/* SSO Divider Label */}
            <div style={{ textAlign: "center", marginBottom: "12px" }}>
              <span
                style={{
                  fontSize: "10px",
                  fontFamily: "'JetBrains Mono', monospace",
                  textTransform: "uppercase",
                  color: "#64748b",
                  letterSpacing: "0.1em",
                }}
              >
                OR SIGN IN WITH
              </span>
            </div>

            {/* SSO Identity Providers: GOOGLE, GITHUB, MICROSOFT */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: "8px" }}>
              <button
                type="button"
                onClick={() => handleOAuth("google")}
                disabled={isLoading}
                className="tactical-sso-btn"
              >
                GOOGLE
              </button>
              <button
                type="button"
                onClick={() => handleOAuth("github")}
                disabled={isLoading}
                className="tactical-sso-btn"
              >
                GITHUB
              </button>
              <button
                type="button"
                onClick={() => handleOAuth("azure")}
                disabled={isLoading}
                className="tactical-sso-btn"
              >
                MICROSOFT
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
