"use client";

import { useState, useEffect, useRef } from "react";
import { getStoredApiKey, setStoredApiKey, clearStoredApiKey, validateApiKey, createFreeApiKey } from "@/lib/api";

type KeyState =
  | { status: "idle" }
  | { status: "validating" }
  | { status: "valid"; plan: string; remaining: number }
  | { status: "invalid"; message: string };

type CreateState =
  | { status: "idle" }
  | { status: "creating" }
  | { status: "created"; key: string; email: string }
  | { status: "error"; code: string; message: string };

function errorForCode(code: string, message: string): string {
  if (code === "invalid_email" || code === "email_required") return "Please enter a valid email address.";
  if (code === "duplicate_key" || code === "already_active")
    return "This email already has an active FREE key. Enter it in the field above to save it to your browser.";
  if (code === "create_throttled" || code === "throttled" || code === "rate_limit")
    return "Too many requests. Please wait a few minutes and try again.";
  return message || "Something went wrong. Please try again.";
}

export default function KeysPage() {
  const [inputValue, setInputValue] = useState("");
  const [keyState, setKeyState] = useState<KeyState>({ status: "idle" });
  const [savedKey, setSavedKey] = useState<string | null>(null);

  const [emailValue, setEmailValue] = useState("");
  const [createState, setCreateState] = useState<CreateState>({ status: "idle" });
  const newKeyRef = useRef<HTMLInputElement>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    document.title = "API Key — Brazil Business Intelligence";
    const stored = getStoredApiKey();
    if (stored) {
      setSavedKey(stored);
      setInputValue(stored);
      validateStored(stored);
    }
  }, []);

  async function validateStored(key: string) {
    setKeyState({ status: "validating" });
    const result = await validateApiKey(key);
    if (result.ok) {
      setKeyState({ status: "valid", plan: result.plan, remaining: result.remaining });
    } else {
      setKeyState({ status: "invalid", message: result.message });
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const key = inputValue.trim();
    if (!key) return;

    setKeyState({ status: "validating" });
    const result = await validateApiKey(key);
    if (result.ok) {
      setStoredApiKey(key);
      setSavedKey(key);
      setKeyState({ status: "valid", plan: result.plan, remaining: result.remaining });
    } else {
      setKeyState({
        status: "invalid",
        message: result.message || "Invalid API key. Please check and try again.",
      });
    }
  }

  function handleClear() {
    clearStoredApiKey();
    setSavedKey(null);
    setInputValue("");
    setKeyState({ status: "idle" });
  }

  async function handleCreateKey(e: React.FormEvent) {
    e.preventDefault();
    const email = emailValue.trim();
    if (!email) return;

    setCreateState({ status: "creating" });
    setCopied(false);

    const result = await createFreeApiKey(email);
    if (result.ok) {
      setCreateState({ status: "created", key: result.key, email: result.email });
      setTimeout(() => newKeyRef.current?.select(), 50);
    } else {
      setCreateState({ status: "error", code: result.code, message: result.message });
    }
  }

  function handleCopyNewKey() {
    if (createState.status !== "created") return;
    navigator.clipboard.writeText(createState.key).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
  }

  function handleSaveNewKey() {
    if (createState.status !== "created") return;
    const key = createState.key;
    setStoredApiKey(key);
    setSavedKey(key);
    setInputValue(key);
    validateStored(key);
    setCreateState({ status: "idle" });
    setEmailValue("");
  }

  const isValidating = keyState.status === "validating";
  const isCreating = createState.status === "creating";

  return (
    <div
      style={{
        maxWidth: "560px",
        margin: "4rem auto",
        padding: "0 1.5rem",
        display: "flex",
        flexDirection: "column",
        gap: "2.5rem",
      }}
    >
      {/* ── Existing key form ── */}
      <div>
        <h1
          style={{
            fontSize: "1.75rem",
            fontWeight: 700,
            marginBottom: "0.5rem",
            letterSpacing: "-0.02em",
          }}
        >
          API Key
        </h1>
        <p style={{ color: "var(--muted)", marginBottom: "1.5rem" }}>
          Enter your API key to authenticate requests. Keys are stored locally in
          your browser — never sent to our servers directly.
        </p>

        <form
          id="apikey-form"
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: "1rem" }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
            <label
              htmlFor="apikey-input"
              style={{ fontSize: "0.875rem", fontWeight: 500 }}
            >
              API Key
            </label>
            <input
              id="apikey-input"
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="bbi_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              autoComplete="off"
              spellCheck={false}
              disabled={isValidating}
              style={{
                border: "1.5px solid var(--border)",
                borderRadius: "6px",
                padding: "0.6rem 0.875rem",
                fontSize: "0.875rem",
                fontFamily: "monospace",
                background: "var(--background)",
                color: "var(--foreground)",
                outline: "none",
                width: "100%",
                opacity: isValidating ? 0.6 : 1,
              }}
            />
          </div>

          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button
              type="submit"
              disabled={isValidating || !inputValue.trim()}
              style={{
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: "6px",
                padding: "0.6rem 1.25rem",
                fontWeight: 600,
                fontSize: "0.875rem",
                cursor: isValidating || !inputValue.trim() ? "not-allowed" : "pointer",
                opacity: isValidating || !inputValue.trim() ? 0.6 : 1,
              }}
            >
              {isValidating ? "Validating…" : "Save Key"}
            </button>
            {savedKey && (
              <button
                type="button"
                onClick={handleClear}
                disabled={isValidating}
                style={{
                  background: "transparent",
                  color: "var(--danger, #dc2626)",
                  border: "1.5px solid var(--border)",
                  borderRadius: "6px",
                  padding: "0.6rem 1.25rem",
                  fontWeight: 600,
                  fontSize: "0.875rem",
                  cursor: "pointer",
                }}
              >
                Remove Key
              </button>
            )}
          </div>
        </form>

        {/* Validation status */}
        {keyState.status === "valid" && (
          <div
            style={{
              marginTop: "1.25rem",
              border: "1px solid #16a34a",
              borderRadius: "8px",
              padding: "1rem 1.25rem",
              background: "rgba(22,163,74,0.05)",
            }}
          >
            <p style={{ fontWeight: 600, color: "var(--success, #16a34a)", margin: "0 0 0.5rem" }}>
              ✓ Key active
            </p>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "0.75rem",
                marginTop: "0.5rem",
              }}
            >
              <div>
                <p style={{ fontSize: "0.75rem", color: "var(--muted)", margin: 0 }}>Plan</p>
                <p style={{ fontWeight: 700, margin: 0 }}>{keyState.plan}</p>
              </div>
              <div>
                <p style={{ fontSize: "0.75rem", color: "var(--muted)", margin: 0 }}>
                  Requests remaining
                </p>
                <p style={{ fontWeight: 700, margin: 0 }}>
                  {keyState.remaining === -1 ? "Unlimited" : keyState.remaining.toLocaleString()}
                </p>
              </div>
            </div>
          </div>
        )}

        {keyState.status === "invalid" && (
          <div
            style={{
              marginTop: "1.25rem",
              border: "1px solid var(--danger, #dc2626)",
              borderRadius: "8px",
              padding: "1rem 1.25rem",
              background: "rgba(220,38,38,0.05)",
            }}
          >
            <p style={{ fontWeight: 600, color: "var(--danger, #dc2626)", margin: "0 0 0.25rem" }}>
              ✗ Validation failed
            </p>
            <p style={{ color: "var(--muted)", fontSize: "0.875rem", margin: 0 }}>
              {keyState.message}
            </p>
          </div>
        )}
      </div>

      {/* ── Self-serve FREE key creation ── */}
      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: "10px",
          padding: "1.5rem",
          background: "var(--card)",
        }}
      >
        <h2 style={{ fontSize: "1rem", fontWeight: 700, margin: "0 0 0.375rem" }}>
          Get a Free Key
        </h2>
        <p style={{ color: "var(--muted)", fontSize: "0.875rem", margin: "0 0 1.25rem" }}>
          Enter your email to instantly generate a FREE-tier API key — no credit card required.
        </p>

        {/* Show the created key — ONE TIME */}
        {createState.status === "created" ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "0.75rem",
            }}
          >
            <div
              style={{
                border: "1px solid #16a34a",
                borderRadius: "8px",
                padding: "1rem 1.25rem",
                background: "rgba(22,163,74,0.05)",
              }}
            >
              <p style={{ fontWeight: 700, color: "#15803d", fontSize: "0.875rem", margin: "0 0 0.5rem" }}>
                ✓ Key created for {createState.email}
              </p>
              <p
                style={{
                  fontSize: "0.8rem",
                  color: "#b45309",
                  fontWeight: 600,
                  margin: "0 0 0.75rem",
                  background: "rgba(180,83,9,0.08)",
                  border: "1px solid #b45309",
                  borderRadius: "5px",
                  padding: "0.35rem 0.6rem",
                  display: "inline-block",
                }}
              >
                ⚠ Shown once — copy and save it now
              </p>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <input
                  ref={newKeyRef}
                  type="text"
                  readOnly
                  value={createState.key}
                  style={{
                    flex: 1,
                    border: "1.5px solid var(--border)",
                    borderRadius: "6px",
                    padding: "0.5rem 0.75rem",
                    fontSize: "0.8rem",
                    fontFamily: "monospace",
                    background: "var(--background)",
                    color: "var(--foreground)",
                    outline: "none",
                    minWidth: 0,
                  }}
                />
                <button
                  type="button"
                  onClick={handleCopyNewKey}
                  style={{
                    border: "1.5px solid var(--border)",
                    borderRadius: "6px",
                    padding: "0.5rem 0.875rem",
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    background: copied ? "rgba(22,163,74,0.1)" : "var(--background)",
                    color: copied ? "#15803d" : "var(--foreground)",
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                  }}
                >
                  {copied ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>
            <button
              type="button"
              onClick={handleSaveNewKey}
              style={{
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: "6px",
                padding: "0.6rem 1.25rem",
                fontWeight: 600,
                fontSize: "0.875rem",
                cursor: "pointer",
                alignSelf: "flex-start",
              }}
            >
              Save to browser &amp; activate
            </button>
          </div>
        ) : (
          <form
            onSubmit={handleCreateKey}
            style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
              <label
                htmlFor="create-key-email"
                style={{ fontSize: "0.875rem", fontWeight: 500 }}
              >
                Email address
              </label>
              <input
                id="create-key-email"
                type="email"
                value={emailValue}
                onChange={(e) => setEmailValue(e.target.value)}
                placeholder="you@example.com"
                disabled={isCreating}
                autoComplete="email"
                style={{
                  border: "1.5px solid var(--border)",
                  borderRadius: "6px",
                  padding: "0.6rem 0.875rem",
                  fontSize: "0.875rem",
                  background: "var(--background)",
                  color: "var(--foreground)",
                  outline: "none",
                  width: "100%",
                  opacity: isCreating ? 0.6 : 1,
                }}
              />
            </div>

            <button
              type="submit"
              disabled={isCreating || !emailValue.trim()}
              style={{
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: "6px",
                padding: "0.6rem 1.25rem",
                fontWeight: 600,
                fontSize: "0.875rem",
                cursor: isCreating || !emailValue.trim() ? "not-allowed" : "pointer",
                opacity: isCreating || !emailValue.trim() ? 0.6 : 1,
                alignSelf: "flex-start",
              }}
            >
              {isCreating ? "Creating…" : "Create free key"}
            </button>

            {createState.status === "error" && (
              <div
                style={{
                  border: "1px solid var(--danger, #dc2626)",
                  borderRadius: "8px",
                  padding: "0.875rem 1.1rem",
                  background: "rgba(220,38,38,0.05)",
                }}
              >
                <p style={{ fontWeight: 600, color: "var(--danger, #dc2626)", margin: "0 0 0.2rem", fontSize: "0.875rem" }}>
                  ✗ Could not create key
                </p>
                <p style={{ color: "var(--muted)", fontSize: "0.85rem", margin: 0 }}>
                  {errorForCode(createState.code, createState.message)}
                </p>
              </div>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
