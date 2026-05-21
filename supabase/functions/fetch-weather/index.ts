/**
 * DynaMo — fetch-weather (Supabase Edge Function)
 *
 * Fetches current temperature & precipitation from Open-Meteo for each campaign
 * city and inserts rows into `weather_readings`. Replaces unreliable GitHub
 * Actions cron for the weather-ingest step.
 *
 * Deploy (Supabase CLI):
 *   supabase functions deploy fetch-weather --no-verify-jwt
 *
 * Schedule (Dashboard → Edge Functions → fetch-weather → Schedules):
 *   every 12 minutes (cron: minute 0,12,24,36,48 — or use Supabase's schedule UI)
 *
 * Or invoke manually:
 *   curl -X POST "$SUPABASE_URL/functions/v1/fetch-weather" \
 *     -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
 *
 * Env (set in Dashboard → Edge Functions → Secrets, or auto-injected):
 *   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
 */

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

// Same coordinates as main.py
const CITY_COORDS: Record<string, { lat: number; lon: number }> = {
  Mumbai: { lat: 19.076, lon: 72.8777 },
  Delhi: { lat: 28.6139, lon: 77.209 },
  Bangalore: { lat: 12.9716, lon: 77.5946 },
  Chennai: { lat: 13.0827, lon: 80.2707 },
};

const VALID_TEMP_RANGE = [-50, 60] as const;
const VALID_PRECIP_RANGE = [0, 500] as const;
const OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast";

type WeatherReading = { temperature: number; precipitation: number };

type CityRow = { id: number; name: string };

type FetchResult = {
  city: string;
  ok: boolean;
  temperature?: number;
  precipitation?: number;
  error?: string;
};

async function fetchOpenMeteo(
  city: string,
  lat: number,
  lon: number,
): Promise<WeatherReading | null> {
  const params = new URLSearchParams({
    latitude: String(lat),
    longitude: String(lon),
    current: "temperature_2m,precipitation",
  });

  try {
    const res = await fetch(`${OPEN_METEO_URL}?${params}`, {
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) {
      console.error(`${city}: Open-Meteo HTTP ${res.status}`);
      return null;
    }

    const data = await res.json();
    const temp = data?.current?.temperature_2m;
    const precip = data?.current?.precipitation;

    if (typeof temp !== "number" || typeof precip !== "number") {
      console.error(`${city}: missing temperature_2m or precipitation`);
      return null;
    }
    if (temp < VALID_TEMP_RANGE[0] || temp > VALID_TEMP_RANGE[1]) {
      console.error(`${city}: temperature ${temp}°C out of range`);
      return null;
    }
    if (precip < VALID_PRECIP_RANGE[0] || precip > VALID_PRECIP_RANGE[1]) {
      console.error(`${city}: precipitation ${precip}mm out of range`);
      return null;
    }

    return { temperature: temp, precipitation: precip };
  } catch (err) {
    console.error(`${city}: fetch failed`, err);
    return null;
  }
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "authorization, content-type",
      },
    });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceKey) {
    return jsonResponse(
      { error: "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY" },
      500,
    );
  }

  const supabase = createClient(supabaseUrl, serviceKey);

  const { data: cities, error: citiesError } = await supabase
    .from("cities")
    .select("id, name");

  if (citiesError) {
    return jsonResponse({ error: citiesError.message }, 500);
  }

  const cityRows = (cities ?? []) as CityRow[];
  const cityIds = Object.fromEntries(cityRows.map((c) => [c.name, c.id]));
  const fetchedAt = new Date().toISOString();
  const results: FetchResult[] = [];

  for (const [city, coords] of Object.entries(CITY_COORDS)) {
    const weather = await fetchOpenMeteo(city, coords.lat, coords.lon);
    if (!weather) {
      results.push({ city, ok: false, error: "fetch or validation failed" });
      continue;
    }

    const { error: insertError } = await supabase.from("weather_readings").insert({
      city,
      city_id: cityIds[city] ?? null,
      temperature: weather.temperature,
      precipitation: weather.precipitation,
      fetched_at: fetchedAt,
    });

    if (insertError) {
      console.error(`${city}: insert failed`, insertError.message);
      results.push({
        city,
        ok: false,
        error: insertError.message,
      });
      continue;
    }

    results.push({
      city,
      ok: true,
      temperature: weather.temperature,
      precipitation: weather.precipitation,
    });
  }

  const saved = results.filter((r) => r.ok).length;
  const failed = results.length - saved;

  return jsonResponse({
    ok: failed === 0,
    fetched_at: fetchedAt,
    saved,
    failed,
    results,
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
