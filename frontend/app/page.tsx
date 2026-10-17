// frontend/app/page.tsx
// PURPOSE: The AquaPredict Pro dashboard. It asks the backend (port 8000)
// for ocean data and displays it. Nothing here is hardcoded.

"use client";
// WHY: pages that react to clicks and load data in the browser must be
// marked "use client" in Next.js.

import { useEffect, useState } from "react";
import { Compass, Send, Users, Waves } from "lucide-react"; // small icons

// Where the backend lives. ONE place to change when you deploy online.
const API_URL = "http://localhost:8000";

// ---- TYPES: the shape of our data. Catches typos before you run the page.
type Zone = {
  sector: string;
  lat: number;
  lon: number;
  sst: number; // sea surface temperature
  chlorophyll: number;
  yield_index: number;
  status: string;
};

type Catch = {
  bmu: string;
  composition: string;
  volume_kg: number;
  status: string;
};

type Tab = "map" | "broadcast" | "market";

export default function Dashboard() {
  // ---- STATE: the page's memory. When a value changes, React redraws.
  const [tab, setTab] = useState<Tab>("map");
  const [zones, setZones] = useState<Zone[]>([]);
  const [best, setBest] = useState<Zone | null>(null);
  const [dataSource, setDataSource] = useState("");
  const [catches, setCatches] = useState<Catch[]>([]);
  const [error, setError] = useState("");
  const [phones, setPhones] = useState("+2348012345678");
  const [message, setMessage] = useState(""); // empty = use auto-generated one
  const [result, setResult] = useState("");
  const [sending, setSending] = useState(false);

  // ---- LOAD DATA FROM THE BACKEND (runs once when the page opens)
  useEffect(() => {
    async function load() {
      try {
        const [oceanRes, marketRes] = await Promise.all([
          fetch(`${API_URL}/api/ocean-metrics`),
          fetch(`${API_URL}/api/market-catches`),
        ]);
        const ocean = await oceanRes.json();
        const market = await marketRes.json();

        // Array.isArray = "is this really a list?" If not, use an empty
        // list instead of crashing the whole page.
        setZones(Array.isArray(ocean.data) ? ocean.data : []);
        setBest(ocean.best_zone ?? null);
        setDataSource(ocean.data_source ?? "unknown");
        setCatches(Array.isArray(market.catches) ? market.catches : []);
      } catch {
        setError("Cannot reach the backend. Is uvicorn running on port 8000?");
      }
    }
    load();
  }, []);
  
  // ---- THE ADVISORY MESSAGE: built only from real data. We make no claims
  // about weather or swell because we have no weather data yet.
  const autoMessage = best
    ? `AquaPredict Advisory: Highest fishing potential today near ${best.sector} ` +
      `(Lat ${best.lat.toFixed(2)}, Lon ${best.lon.toFixed(2)}). ` +
      `Sea surface temp ${best.sst}C. Check sea conditions before departure.`
    : "";
  const finalMessage = message || autoMessage;

  // ---- SEND THE ADVISORY
  async function sendAdvisory() {
    setSending(true);
    setResult("");
    try {
      const res = await fetch(`${API_URL}/api/broadcast-advisory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          zone: best?.sector ?? "all",
          message: finalMessage,
          // "a, b" becomes ["a", "b"], trimmed, empties dropped
          phone_numbers: phones.split(",").map((p) => p.trim()).filter(Boolean),
        }),
      });
      const data = await res.json();
      // Show the backend's honest answer: sent, demo_mode, or error.
      setResult(`${data.status}: ${data.message ?? "Handed to the SMS gateway."}`);
    } catch {
      setResult("error: could not reach the backend.");
    }
    setSending(false);
  }

  // ---- THE MAP: each zone becomes a circle placed by its lat/lon.
  const W = 640, H = 360, PAD = 50;
  const lats = zones.map((z) => z.lat);
  const lons = zones.map((z) => z.lon);
  // Safety net: Math.min of an empty list is Infinity, which breaks drawing.
  const minLat = lats.length ? Math.min(...lats) : 0;
  const maxLat = lats.length ? Math.max(...lats) : 1;
  const minLon = lons.length ? Math.min(...lons) : 0;
  const maxLon = lons.length ? Math.max(...lons) : 1;

  // Convert real coordinates into pixel positions.
  const px = (lon: number) =>
    PAD + ((lon - minLon) / (maxLon - minLon || 1)) * (W - 2 * PAD);
  // Latitude is flipped: on screen "up" is smaller numbers, but north is up.
  const py = (lat: number) =>
    H - PAD - ((lat - minLat) / (maxLat - minLat || 1)) * (H - 2 * PAD);

  // Shared styling for the three tab buttons
  const tabStyle = (t: Tab) =>
    `w-full flex items-center px-4 py-3 text-sm font-medium rounded-lg transition ${
      tab === t
        ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
        : "text-slate-300 hover:bg-slate-800/50"
    }`;

  const highCount = zones.filter((z) => z.status === "High Yield").length;
  
  // ---- WHAT APPEARS ON SCREEN (JSX: HTML-like; className = Tailwind styling)
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Top bar */}
      <header className="border-b border-slate-800 bg-slate-900/60 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center space-x-3">
          <Waves className="h-8 w-8 text-cyan-400" />
          <h1 className="text-xl font-bold tracking-wider">
            AQUAPREDICT <span className="text-cyan-400">PRO</span>
          </h1>
        </div>
        <span className="text-xs text-slate-400">
          Data source:{" "}
          <span className="text-amber-400 font-semibold">{dataSource || "loading..."}</span>
        </span>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-4 min-h-[calc(100vh-73px)]">
        {/* Sidebar */}
        <aside className="bg-slate-900/40 border-r border-slate-800 p-6 space-y-6">
          <nav className="space-y-1">
            <button onClick={() => setTab("map")} className={tabStyle("map")}>
              <Compass className="mr-3 h-5 w-5" /> Ocean Yield Map
            </button>
            <button onClick={() => setTab("broadcast")} className={tabStyle("broadcast")}>
              <Send className="mr-3 h-5 w-5" /> SMS Advisory
            </button>
            <button onClick={() => setTab("market")} className={tabStyle("market")}>
              <Users className="mr-3 h-5 w-5" /> Catch Marketplace
            </button>
          </nav>

          {/* Figures calculated from the data, not invented */}
          <div className="bg-slate-900 p-4 rounded-xl border border-slate-800">
            <h4 className="text-xs font-bold text-cyan-400 uppercase mb-2">Today&apos;s Summary</h4>
            <div className="text-2xl font-black">{best ? best.sector : "..."}</div>
            <p className="text-xs text-slate-400 mt-1">
              Top zone. {highCount} of {zones.length} zones rated High Yield.
            </p>
          </div>
        </aside>

        {/* Main panel */}
        <main className="lg:col-span-3 p-6 space-y-6">
          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/30 text-red-300 rounded-xl text-sm">
              {error}
            </div>
          )}
          
          {/* ---------- TAB 1: MAP ---------- */}
          {tab === "map" && zones.length > 0 && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold">Gulf of Guinea: Fish Aggregation Zones</h2>
              <div className="bg-slate-900 rounded-2xl border border-slate-800 p-4 overflow-x-auto">
                <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[480px]">
                  {zones.map((z) => (
                    <g key={z.sector}>
                      <circle
                        cx={px(z.lon)}
                        cy={py(z.lat)}
                        r={10 + z.yield_index * 14}
                        fill={z.status === "High Yield" ? "#22d3ee" : "#f59e0b"}
                        fillOpacity={0.35}
                        stroke={z.status === "High Yield" ? "#22d3ee" : "#f59e0b"}
                        strokeWidth={best?.sector === z.sector ? 4 : 1.5}
                      />
                      <text x={px(z.lon)} y={py(z.lat) + 38} textAnchor="middle" fill="#cbd5e1" fontSize="12">
                        {z.sector.replace("Sector ", "")} ({z.yield_index})
                      </text>
                    </g>
                  ))}
                </svg>
                <p className="text-xs text-slate-500 mt-2">
                  Circle size = fishing score. Cyan = High Yield, amber = Promising. Thick ring = best zone today.
                </p>
              </div>

              {/* Table of the exact numbers behind the picture */}
              <div className="bg-slate-900 rounded-2xl border border-slate-800 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-950 text-slate-400 text-xs uppercase">
                    <tr>
                      <th className="px-4 py-3">Zone</th>
                      <th className="px-4 py-3">Temp (C)</th>
                      <th className="px-4 py-3">Chlorophyll</th>
                      <th className="px-4 py-3">Score</th>
                      <th className="px-4 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {zones.map((z) => (
                      <tr key={z.sector}>
                        <td className="px-4 py-3 font-medium">{z.sector}</td>
                        <td className="px-4 py-3">{z.sst}</td>
                        <td className="px-4 py-3">{z.chlorophyll}</td>
                        <td className="px-4 py-3">{z.yield_index}</td>
                        <td className="px-4 py-3">{z.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          
          {/* ---------- TAB 2: SMS BROADCAST ---------- */}
          {tab === "broadcast" && (
            <div className="space-y-4 max-w-2xl">
              <h2 className="text-lg font-bold">Send Fisher Advisory</h2>
              <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">
                    Phone numbers (separate with commas)
                  </label>
                  <input
                    value={phones}
                    onChange={(e) => setPhones(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">
                    Message (auto-written from today&apos;s data; you can edit it)
                  </label>
                  <textarea
                    rows={4}
                    value={finalMessage}
                    onChange={(e) => setMessage(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-sm"
                  />
                </div>
                <button
                  onClick={sendAdvisory}
                  disabled={sending || !finalMessage}
                  className="w-full bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold py-3 rounded-xl flex items-center justify-center space-x-2"
                >
                  <Send className="h-4 w-4" />
                  <span>{sending ? "Sending..." : "Send Advisory"}</span>
                </button>
                {result && (
                  <div className="p-3 bg-slate-950 border border-slate-700 text-slate-300 text-xs rounded-xl">
                    {result}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ---------- TAB 3: MARKETPLACE ---------- */}
          {tab === "market" && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold">Coastal Catch Marketplace (sample data)</h2>
              <div className="bg-slate-900 rounded-2xl border border-slate-800 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-950 text-slate-400 text-xs uppercase">
                    <tr>
                      <th className="px-4 py-3">Landing Site</th>
                      <th className="px-4 py-3">Catch</th>
                      <th className="px-4 py-3">Volume</th>
                      <th className="px-4 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {catches.map((c) => (
                      <tr key={c.bmu}>
                        <td className="px-4 py-3 font-medium">{c.bmu}</td>
                        <td className="px-4 py-3">{c.composition}</td>
                        <td className="px-4 py-3">{c.volume_kg} kg</td>
                        <td className="px-4 py-3">{c.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
