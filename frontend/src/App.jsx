import { useEffect, useState } from "react";
import { api, tokenStore } from "./api";

const Err = ({ e }) => (e ? <p className="err" role="alert">{e}</p> : null);

function useAction() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const run = async (fn) => {
    setBusy(true);
    setErr("");
    try { return await fn(); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  return { busy, err, setErr, run };
}

function ConfirmEmail() {
  const [msg, setMsg] = useState("Confirming your email...");
  useEffect(() => {
    const token = new URLSearchParams(location.search).get("token");
    api("/auth/email/confirm/", { method: "POST", body: { token } })
      .then(() => setMsg("Email confirmed. You can now log in and play."))
      .catch((e) => setMsg(e.message));
  }, []);
  return (
    <main className="center">
      <h2>Vibe Match</h2>
      <p>{msg}</p>
      <a href="/">Go to the app</a>
    </main>
  );
}

function Auth({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { busy, err, run } = useAction();
  const submit = (e) => {
    e.preventDefault();
    run(async () => {
      const d = await api(mode === "login" ? "/auth/login/" : "/auth/register/", { method: "POST", body: { email, password } });
      tokenStore.set(d.token);
      onAuth(d.user, mode === "signup");
    });
  };
  return (
    <main>
      <h1>{mode === "login" ? "Welcome back" : "Join with your university email"}</h1>
      <form onSubmit={submit} style={{ display: "contents" }}>
        <label>University email<input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Password<input className="input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        <Err e={err} />
        <button className="btn" disabled={busy}>{mode === "login" ? "Log in" : "Create account"}</button>
      </form>
      <button className="btn link" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
        {mode === "login" ? "New here? Sign up" : "Have an account? Log in"}
      </button>
    </main>
  );
}

function ProfileCard({ p }) {
  return (
    <div className="card">
      <h2>{p.display_name}, {p.age}</h2>
      <p className="muted">{[p.department, p.batch].filter(Boolean).join(" · ")}</p>
      {p.bio && <p>{p.bio}</p>}
    </div>
  );
}

function Play({ goProfile }) {
  const [s, setS] = useState(null);
  const [ready, setReady] = useState(false);
  const [guess, setGuess] = useState("");
  const [outcome, setOutcome] = useState(null);
  const [reason, setReason] = useState("harassment");
  const [note, setNote] = useState("");
  const { busy, err, setErr, run } = useAction();

  useEffect(() => {
    api("/game/sessions/current/").then(setS).catch(() => {}).finally(() => setReady(true));
  }, []);

  const post = (path, body, onOk) =>
    run(async () => {
      try {
        onOk(await api(path, { method: "POST", body }));
      } catch (e) {
        if (e.status === 409) setS(null);
        throw e;
      }
    });
  const start = () => { setOutcome(null); setNote(""); post("/game/sessions/", undefined, setS); };
  const submitGuess = (e) => { e.preventDefault(); post(`/game/sessions/${s.id}/guess/`, { text: guess }, (d) => { setS(d); setGuess(""); }); };
  const reveal = () => post(`/game/sessions/${s.id}/reveal/`, undefined, setS);
  const decide = (action) => post(`/game/sessions/${s.id}/decision/`, { action }, (d) => { setOutcome({ ...d, action }); setS(null); });
  const report = () => post("/moderation/report/", { session_id: s.id, reason }, () => setNote("Report sent. Thank you."));
  const block = () => post("/moderation/block/", { session_id: s.id }, () => { setS(null); setNote("Blocked. You will not see each other again."); });

  if (!ready) return <main className="center muted">Loading...</main>;

  if (outcome)
    return (
      <main className="center">
        <h2>{outcome.matched ? "It's a match!" : outcome.action === "like" ? "Liked" : "Passed"}</h2>
        <p className="muted">{outcome.matched ? "You both liked each other. Find them in Matches." : "On to the next mystery."}</p>
        <button className="btn" onClick={start}>Play again</button>
      </main>
    );

  if (!s)
    return (
      <main className="center">
        <span className="label">GUESS YOUR VIBE</span>
        <h1>Who is behind the clues?</h1>
        <p className="muted">Read the clues, make a guess, then meet a student who chose to play.</p>
        {note && <p className="ok">{note}</p>}
        <button className="btn play" onClick={start} disabled={busy}>Play</button>
        <Err e={err} />
        {err.includes("profile") && <button className="btn alt" onClick={goProfile}>Set up my profile</button>}
      </main>
    );

  const more = (
    <details>
      <summary className="muted">Report or block</summary>
      <div className="row" style={{ marginTop: 10 }}>
        <select className="input" value={reason} onChange={(e) => setReason(e.target.value)} aria-label="Reason">
          {["harassment", "fake", "inappropriate", "underage", "other"].map((r) => <option key={r}>{r}</option>)}
        </select>
        <button className="btn alt" onClick={report} disabled={busy}>Report</button>
        <button className="btn alt" onClick={block} disabled={busy}>Block</button>
      </div>
      {note && <p className="ok">{note}</p>}
    </details>
  );

  if (s.status === "revealed")
    return (
      <main>
        <span className="chip" style={{ alignSelf: "flex-start" }}>Revealed after {s.guesses.length} guess{s.guesses.length === 1 ? "" : "es"}</span>
        <ProfileCard p={s.profile} />
        <Err e={err} />
        <div className="row">
          <button className="btn alt" onClick={() => decide("pass")} disabled={busy}>Pass</button>
          <button className="btn" onClick={() => decide("like")} disabled={busy}>Like</button>
        </div>
        <p className="muted center" style={{ fontSize: 13 }}>A match happens only if you both like each other.</p>
        {more}
      </main>
    );

  return (
    <main>
      <h2>Mystery student</h2>
      <div className="bar" aria-label={`Clue ${s.clues_unlocked} of ${s.clues_total}`}>
        {Array.from({ length: s.clues_total }, (_, i) => <i key={i} className={i < s.clues_unlocked ? "on" : ""} />)}
      </div>
      {s.clues.map((c) => (
        <div key={c.position} className={`card ${c.position === s.clues_unlocked ? "clue-dark" : ""}`}>
          <span className="label" style={c.position === s.clues_unlocked ? { color: "#F3E8DE" } : {}}>CLUE {c.position}</span>
          <p className="clue">{c.text}</p>
        </div>
      ))}
      {s.clues_unlocked < s.clues_total && <div className="locked">Clue {s.clues_unlocked + 1} unlocks after your next guess.</div>}
      <form onSubmit={submitGuess} style={{ display: "contents" }}>
        <label>Your guess<input className="input" required maxLength={200} value={guess} onChange={(e) => setGuess(e.target.value)} placeholder="What do you think they study?" /></label>
        <Err e={err} />
        <button className="btn" disabled={busy}>Submit guess</button>
      </form>
      <button className="btn link" onClick={reveal} disabled={busy}>Reveal now</button>
      {more}
    </main>
  );
}

function Matches() {
  const [list, setList] = useState(null);
  const { err, run } = useAction();
  const load = () => run(async () => setList(await api("/matches/")));
  useEffect(() => { load(); }, []);
  const unmatch = (id) => run(async () => { await api(`/matches/${id}/unmatch/`, { method: "POST" }); load(); });
  return (
    <main>
      <h2>Matches</h2>
      <Err e={err} />
      {list && list.length === 0 && <p className="muted">No matches yet. Play Guess Your Vibe to meet someone.</p>}
      {list?.map((m) => (
        <div key={m.id}>
          <ProfileCard p={m.profile} />
          <button className="btn link" onClick={() => unmatch(m.id)}>Unmatch</button>
        </div>
      ))}
    </main>
  );
}

const EMPTY = { display_name: "", date_of_birth: "", gender: "female", looking_for: "both", department: "", batch: "", bio: "", is_discoverable: false, consent_mystery_game: false };

function Profile({ user }) {
  const [f, setF] = useState(EMPTY);
  const [exists, setExists] = useState(false);
  const [saved, setSaved] = useState(false);
  const [sent, setSent] = useState(false);
  const { busy, err, run } = useAction();
  useEffect(() => {
    api("/profiles/me/").then((p) => { setF({ ...EMPTY, ...p }); setExists(true); }).catch(() => {});
  }, []);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const save = (e) => {
    e.preventDefault();
    setSaved(false);
    run(async () => {
      const { age, ...body } = f;
      await api("/profiles/me/", { method: exists ? "PATCH" : "POST", body });
      setExists(true);
      setSaved(true);
    });
  };
  const resend = () => run(async () => { await api("/auth/email/resend/", { method: "POST" }); setSent(true); });
  return (
    <main>
      <h2>My profile</h2>
      {!user.is_university_verified && (
        <div className="card">
          <p style={{ margin: 0 }}>Confirm your university email to turn on discovery and play.</p>
          <button className="btn link" onClick={resend}>Resend confirmation email</button>
          {sent && <p className="ok">Sent. In development, the link prints in the Django terminal.</p>}
        </div>
      )}
      <form onSubmit={save} style={{ display: "contents" }}>
        <label>Display name<input className="input" required value={f.display_name} onChange={set("display_name")} /></label>
        <label>Date of birth (18+)<input className="input" type="date" required value={f.date_of_birth} onChange={set("date_of_birth")} /></label>
        <div className="row">
          <label>Gender<select className="input" value={f.gender} onChange={set("gender")}>{["female", "male", "non_binary", "other"].map((g) => <option key={g}>{g}</option>)}</select></label>
          <label>Looking for<select className="input" value={f.looking_for} onChange={set("looking_for")}>{["dating", "friendship", "both"].map((g) => <option key={g}>{g}</option>)}</select></label>
        </div>
        <div className="row">
          <label>Department<input className="input" value={f.department} onChange={set("department")} /></label>
          <label>Batch<input className="input" value={f.batch} onChange={set("batch")} /></label>
        </div>
        <label>Bio<textarea className="input" maxLength={500} value={f.bio} onChange={set("bio")} /></label>
        <label className="check"><input type="checkbox" checked={f.is_discoverable} onChange={set("is_discoverable")} /> Let other students find me</label>
        <label className="check"><input type="checkbox" checked={f.consent_mystery_game} onChange={set("consent_mystery_game")} /> I agree to appear in Guess Your Vibe</label>
        <Err e={err} />
        {saved && <p className="ok">Saved.</p>}
        <button className="btn" disabled={busy}>Save profile</button>
      </form>
      <Clues />
    </main>
  );
}

function Clues() {
  const [list, setList] = useState([]);
  const [text, setText] = useState("");
  const { err, run } = useAction();
  const load = () => api("/game/clues/").then(setList).catch(() => {});
  useEffect(() => { load(); }, []);
  const add = (e) => { e.preventDefault(); run(async () => { await api("/game/clues/", { method: "POST", body: { text } }); setText(""); load(); }); };
  const del = (id) => run(async () => { await api(`/game/clues/${id}/`, { method: "DELETE" }); load(); });
  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <h2>My clues</h2>
      <p className="muted" style={{ margin: 0 }}>Others guess who you are from these. Up to 5. Verified students only.</p>
      {list.map((c) => <div className="card" key={c.id}>{c.text} <button className="btn link" onClick={() => del(c.id)}>Remove</button></div>)}
      <form onSubmit={add} style={{ display: "contents" }}>
        <input className="input" required maxLength={200} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. I always carry a chess set" aria-label="New clue" />
        <Err e={err} />
        <button className="btn alt">Add clue</button>
      </form>
    </section>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [view, setView] = useState("play");
  const [welcome, setWelcome] = useState(false);

  useEffect(() => {
    if (!tokenStore.get()) return setReady(true);
    api("/auth/me/").then(setUser).catch(() => tokenStore.clear()).finally(() => setReady(true));
  }, []);

  if (location.pathname === "/confirm-email") return <div className="app"><ConfirmEmail /></div>;
  if (!ready) return <div className="app"><main className="center muted">Loading...</main></div>;

  const logout = () => api("/auth/logout/", { method: "POST" }).catch(() => {}).finally(() => { tokenStore.clear(); setUser(null); });
  if (!user)
    return <div className="app"><div className="top"><span className="brand">Vibe Match</span><span className="chip">UIU students · 18+</span></div>
      <Auth onAuth={(u, isNew) => { setUser(u); setWelcome(isNew); setView(isNew ? "profile" : "play"); }} /></div>;

  return (
    <div className="app">
      <div className="top"><span className="brand">Vibe Match</span><span className="chip">{user.email}</span></div>
      {welcome && view === "profile" && <p className="ok" style={{ margin: "12px 24px 0" }}>Account created. Check your email to confirm it, then set up your profile.</p>}
      {view === "play" && <Play goProfile={() => setView("profile")} />}
      {view === "matches" && <Matches />}
      {view === "profile" && <Profile user={user} />}
      <nav aria-label="Main">
        {[["play", "Play"], ["matches", "Matches"], ["profile", "Profile"]].map(([k, l]) => (
          <button key={k} className={view === k ? "on" : ""} onClick={() => setView(k)}>{l}</button>
        ))}
        <button onClick={logout}>Log out</button>
      </nav>
    </div>
  );
}
