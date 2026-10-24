"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { EvidenceDialog, PlaceCard } from "@/features/places/components";
import TripWorkspace from "@/features/trips/trip-workspace";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import { Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  Compass,
  Globe2,
  Heart,
  MapPin,
  Plus,
  ShieldCheck,
  Sparkles,
  X,
  ArrowUp,
  ArrowDown,
  RotateCcw,
  Clock3,
  Coffee,
  ExternalLink,
  Accessibility,
  CircleHelp,
  Layers3,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  api,
  ApiError,
  type City,
  type Place,
  type Evidence,
  type Plan,
  type PlanInput,
  type Trip,
} from "@/lib/api/client";
const MapPanel = dynamic(() => import("@/features/map/map-panel"), {
  ssr: false,
  loading: () => <div className="map-skeleton">Loading optional map…</div>,
});
const schema = z.object({
  city_id: z.string(),
  date: z.string().min(1),
  start: z.string().min(1),
  end: z.string().min(1),
  max_leg_distance_m: z.number().min(0).max(10000),
  max_total_distance_m: z.number().min(0).max(50000),
  rest_every_minutes: z.number().min(10).max(180),
  step_free: z.boolean(),
  toilet: z.boolean(),
  lift: z.boolean(),
  interests: z.string().max(500),
  intent: z.string().max(1200),
});
type FormValues = z.infer<typeof schema>;
type Progress = {
  sequence: number;
  stage: string;
  status: string;
  summary: string;
};
const today = () => new Date().toLocaleDateString("en-CA");
function iso(date: string, time: string, zone: string) {
  const nominal = new Date(`${date}T${time}:00Z`);
  const part = new Intl.DateTimeFormat("en", {
    timeZone: zone,
    timeZoneName: "longOffset",
  })
    .formatToParts(nominal)
    .find((p) => p.type === "timeZoneName")?.value;
  const offset = part?.replace("GMT", "") || "+00:00";
  return `${date}T${time}:00${offset}`;
}
const defaults: FormValues = {
  city_id: "london",
  date: today(),
  start: "10:00",
  end: "15:00",
  max_leg_distance_m: 500,
  max_total_distance_m: 2000,
  rest_every_minutes: 45,
  step_free: true,
  toilet: false,
  lift: false,
  interests: "art, history",
  intent: "",
};

function ApplicationContent() {
  const [cities, setCities] = useState<City[]>([]),
    [places, setPlaces] = useState<Place[]>([]),
    [plan, setPlan] = useState<Plan | null>(null),
    [evidence, setEvidence] = useState<Evidence[]>([]);
  const [selected, setSelected] = useState<string | null>(null),
    [details, setDetails] = useState<Place | null>(null),
    [view, setView] = useState("list"),
    [tab, setTab] = useState("explore");
  const [providerStatus, setProviderStatus] = useState({
    taste: "development",
    qloo_configured: false,
  });
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState<Progress[]>([]),
    [runId, setRunId] = useState<string | null>(null),
    [ready, setReady] = useState(false);
  const [trips, setTrips] = useState<Trip[]>([]),
    [trip, setTrip] = useState<Trip | null>(null);
  const [history, setHistory] = useState<
      { id: string; version: number; city_id: string }[]
    >([]),
    [contrast, setContrast] = useState(false),
    [osmState, setOsmState] = useState("");
  const events = useRef<EventSource | null>(null),
    started = useRef(false),
    lastSequence = useRef(0),
    restoring = useRef(false);
  const {
    register,
    handleSubmit,
    watch,
    reset,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
  });
  const cityId = watch("city_id"),
    city = cities.find((c) => c.id === cityId);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const session = await api<{
          active_run?: { run_id: string; plan_id: string };
        }>("/sessions/current").catch((error) => {
          if (!(error instanceof ApiError) || error.status !== 401) throw error;
          return api<{ active_run?: { run_id: string; plan_id: string } }>(
            "/sessions",
            { method: "POST" },
          );
        });
        setCities(await api<City[]>("/cities"));
        setProviderStatus(await api<typeof providerStatus>("/providers"));
        setTrips(await api<Trip[]>("/trips"));
        setHistory(await api<typeof history>("/plans"));
        setReady(true);
        if (session.active_run) watchRun(session.active_run);
      } catch (e) {
        setError((e as Error).message);
      }
    })();
    return () => events.current?.close();
  }, []);
  const placeQuery = useQuery({
    queryKey: ["places", cityId],
    queryFn: ({ signal }) =>
      api<Place[]>(`/places?city_id=${cityId}`, { signal }),
    staleTime: 60000,
  });
  useEffect(() => {
    if (placeQuery.data) setPlaces(placeQuery.data);
  }, [placeQuery.data]);
  useEffect(() => {
    if (!restoring.current) setPlan(null);
    restoring.current = false;
    setSelected(null);
    setOsmState("");
  }, [cityId]);
  useEffect(() => {
    document.documentElement.dataset.contrast = contrast ? "high" : "normal";
  }, [contrast]);
  const selectPlace = useCallback((id: string) => setSelected(id), []);
  async function showEvidence(place: Place) {
    setDetails(place);
    const ids = place.facts.flatMap((f) => f.evidence_ids ?? []);
    setEvidence(
      (
        await Promise.all(
          ids.map((id) => api<Evidence>(`/evidence/${id}`).catch(() => null)),
        )
      ).filter((e): e is Evidence => !!e),
    );
  }
  function inputs(values: FormValues): PlanInput {
    const zone = city?.time_zone || "Europe/London";
    return {
      city_id: values.city_id as PlanInput["city_id"],
      window: {
        starts_at: iso(values.date, values.start, zone),
        ends_at: iso(values.date, values.end, zone),
        time_zone: zone,
      },
      mobility: {
        required_features: [
          ...(values.step_free ? ["step_free_entrance" as const] : []),
          ...(values.toilet ? ["accessible_toilet" as const] : []),
          ...(values.lift ? ["lift" as const] : []),
        ],
        accepted_limitations: [],
        max_leg_distance_m: values.max_leg_distance_m,
        max_total_distance_m: values.max_total_distance_m,
        rest_every_minutes: values.rest_every_minutes,
        max_transfers: 1,
      },
      interests: values.interests
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, 12)
        .map((name) => ({ name, kind: "culture" })),
      intent: values.intent,
    };
  }
  function watchRun(result: { run_id: string; plan_id: string }) {
    setBusy(true);
    setProgress([]);
    lastSequence.current = 0;
    events.current?.close();
    setRunId(result.run_id);
    setTab("plan");
    const source = new EventSource(`/api/v1/runs/${result.run_id}/events`);
    events.current = source;
    source.onmessage = async (event) => {
      const item = JSON.parse(event.data) as Progress;
      if (item.sequence <= lastSequence.current) return;
      lastSequence.current = item.sequence;
      setProgress((old) => [...old, item]);
      if (
        ["completed", "failed", "cancelled", "superseded"].includes(
          item.status,
        ) &&
        item.stage === "supervisor"
      ) {
        source.close();
        setBusy(false);
        if (item.status === "completed") {
          await restorePlan(result.plan_id);
          setHistory(await api<typeof history>("/plans"));
        } else setError(item.summary);
      }
    };
    source.onerror = () =>
      setProgress((old) =>
        old.at(-1)?.status === "reconnecting"
          ? old
          : [
              ...old,
              {
                sequence: 0,
                stage: "connection",
                status: "reconnecting",
                summary: "Reconnecting to saved progress…",
              },
            ],
      );
  }
  async function submit(values: FormValues) {
    setError("");
    setBusy(true);
    setProgress([]);
    lastSequence.current = 0;
    events.current?.close();
    try {
      const data = inputs(values);
      const result = await api<{ plan_id: string; run_id: string }>(
        plan ? `/plans/${plan.id}/replan` : "/plans",
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify(
            plan ? { expected_version: plan.version, inputs: data } : data,
          ),
        },
      );
      watchRun(result);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  function persona(kind: "culture" | "rest" | "caregiver") {
    reset({
      ...defaults,
      city_id: cityId,
      ...(kind === "rest"
        ? {
            max_leg_distance_m: 200,
            max_total_distance_m: 800,
            rest_every_minutes: 30,
            step_free: false,
            interests: "art, quiet",
          }
        : kind === "caregiver"
          ? { toilet: true, interests: "history, food, world cultures" }
          : {}),
    });
    document.getElementById("planner-form")?.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  }
  async function saveTrip(next: Trip) {
    try {
      const result = await api<Trip>(`/trips/${next.id}`, {
        method: "PATCH",
        body: JSON.stringify({ ...next, expected_revision: next.revision }),
      });
      setTrip(result);
      setTrips((old) => old.map((t) => (t.id === result.id ? result : t)));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function restorePlan(id: string, version?: number) {
    try {
      const saved = await api<Plan>(
        `/plans/${id}${version ? `?version=${version}` : ""}`,
      );
      restoring.current = cityId !== saved.inputs.city_id;
      const mobility = saved.inputs.mobility;
      reset({
        ...defaults,
        city_id: saved.inputs.city_id,
        date: saved.inputs.window.starts_at.slice(0, 10),
        start: saved.inputs.window.starts_at.slice(11, 16),
        end: saved.inputs.window.ends_at.slice(11, 16),
        max_leg_distance_m: mobility?.max_leg_distance_m ?? 500,
        max_total_distance_m: mobility?.max_total_distance_m ?? 2000,
        rest_every_minutes: mobility?.rest_every_minutes ?? 45,
        step_free:
          !!mobility?.required_features?.includes("step_free_entrance"),
        toilet: !!mobility?.required_features?.includes("accessible_toilet"),
        lift: !!mobility?.required_features?.includes("lift"),
        interests: (saved.inputs.interests ?? []).map((i) => i.name).join(", "),
        intent: saved.inputs.intent ?? "",
      });
      setPlan(saved);
      setTab("plan");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function newTrip() {
    try {
      const created = await api<Trip>("/trips", {
        method: "POST",
        body: JSON.stringify({ title: "My cultural journey", segments: [] }),
      });
      setTrip(created);
      setTrips((old) => [...old, created]);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function attachPlan() {
    if (!trip || !plan) return;
    const existing = trip.segments.find(
      (s) =>
        s.city_id === plan.inputs.city_id &&
        s.date === plan.inputs.window.starts_at.slice(0, 10),
    );
    const segment = {
      id: existing?.id || crypto.randomUUID(),
      city_id: plan.inputs.city_id,
      date: plan.inputs.window.starts_at.slice(0, 10),
      plan_id: plan.id,
      plan_version: plan.version,
    };
    await saveTrip({
      ...trip,
      segments: [
        ...trip.segments.filter((s) => s.id !== existing?.id),
        segment,
      ].sort((a, b) => a.date.localeCompare(b.date)),
    });
    setTab("trips");
  }
  return (
    <>
      <header className="site-header">
        <a className="brand" href="/" aria-label="AccessLife home">
          <span className="brand-mark">
            <Compass size={25} />
          </span>
          <span className="brand-word">
            access
            <wbr />
            life<span className="brand-dot">.</span>
          </span>
        </a>
        <nav aria-label="Main navigation">
          {[
            ["explore", "Explore"],
            ["plan", "Your plan"],
            ["trips", "City collection"],
          ].map(([id, name]) => (
            <Button
              key={id}
              className={`nav-button ${tab === id ? "current" : ""}`}
              onPress={() => {
                setTab(id);
                document.getElementById("workspace")?.scrollIntoView();
              }}
            >
              {name}
            </Button>
          ))}
        </nav>
        <div className="header-right">
          <span className="development">
            <span />
            {plan?.taste.live
              ? "Qloo live"
              : plan
                ? "Development taste engine"
                : providerStatus.taste === "qloo"
                  ? "Qloo configured"
                  : "Development taste engine"}
          </span>
          <Button
            className="icon ghost"
            aria-label="Toggle high contrast"
            aria-pressed={contrast}
            onPress={() => setContrast(!contrast)}
          >
            <CircleHelp size={20} />
          </Button>
        </div>
      </header>
      <main id="main">
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">
              <span className="tiny-line" /> A LITTLE MORE WORLD. A LITTLE LESS
              WORRY.
            </p>
            <h1>
              Your kind of day.
              <br />
              <span>Thoughtfully planned.</span>
            </h1>
            <p className="hero-description">
              Places that speak to your interests. Information that respects
              your needs. Make room for what you love, with the details in view.
            </p>
            <div className="hero-actions">
              <Button
                onPress={() =>
                  document.getElementById("planner-form")?.scrollIntoView({
                    behavior: window.matchMedia(
                      "(prefers-reduced-motion: reduce)",
                    ).matches
                      ? "auto"
                      : "smooth",
                  })
                }
              >
                Find your next outing <ArrowRight size={18} />
              </Button>
              <span className="hero-trust">
                <ShieldCheck size={18} />
                Evidence before assumptions
              </span>
            </div>
            <div className="city-strip">
              {cities.map((c) => (
                <button
                  key={c.id}
                  className={cityId === c.id ? "selected" : ""}
                  onClick={() => setValue("city_id", c.id)}
                >
                  {c.name}
                  <ArrowUpRight size={12} />
                </button>
              ))}
            </div>
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="sun" />
            <div className="city-building b1" />
            <div className="city-building b2" />
            <div className="city-building b3" />
            <div className="city-building b4" />
            <div className="city-building b5" />
            <div className="art-ground" />
            <div className="floating-note">
              <span className="note-icon">
                <Heart size={17} />
              </span>
              <div>
                A day that feels like you
                <small>Culture, curiosity & a little breathing room</small>
              </div>
            </div>
            <span className="art-caption">OPEN TO POSSIBILITY</span>
          </div>
        </section>
        <div className="content-shell" id="workspace">
          <div className="section-top">
            <div>
              <p className="eyebrow">MAKE IT YOURS</p>
              <h2>A good day starts with the details.</h2>
            </div>
            <span className="quiet-label">
              <Globe2 size={16} /> Five cities. Your pace.
            </span>
          </div>
          <div className="workspace">
            <aside className="setup-panel">
              <div className="setup-title">
                <span className="step-number">01</span>
                <div>
                  <h3>Your outing, your terms</h3>
                  <p>Start fresh or try a sample profile.</p>
                </div>
              </div>
              <div className="persona-row">
                <Button className="persona" onPress={() => persona("culture")}>
                  Culture lover
                </Button>
                <Button className="persona" onPress={() => persona("rest")}>
                  Gentle pace
                </Button>
                <Button
                  className="persona"
                  onPress={() => persona("caregiver")}
                >
                  With a companion
                </Button>
              </div>
              <form
                id="planner-form"
                onSubmit={handleSubmit(submit)}
                noValidate
              >
                <label className="field">
                  Where are we exploring?
                  <select {...register("city_id")}>
                    {cities.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="field-help">
                  {city?.district} · {city?.time_zone}
                </p>
                <div className="coverage-note">
                  <CircleHelp size={16} />
                  <span>
                    Limited coverage. Venue information is curated; accessible
                    journeys are not verified.
                  </span>
                </div>
                <label className="field">
                  Outing date
                  <input type="date" {...register("date")} />
                </label>
                <div className="two-fields">
                  <label className="field">
                    From
                    <input type="time" {...register("start")} />
                  </label>
                  <label className="field">
                    Until
                    <input type="time" {...register("end")} />
                  </label>
                </div>
                <fieldset>
                  <legend>What does a place need?</legend>
                  <label className="check-field">
                    <input type="checkbox" {...register("step_free")} />
                    Step-free entrance
                  </label>
                  <label className="check-field">
                    <input type="checkbox" {...register("toilet")} />
                    Accessible toilet
                  </label>
                  <label className="check-field">
                    <input type="checkbox" {...register("lift")} />
                    Lift access
                  </label>
                </fieldset>
                <div className="two-fields">
                  <label className="field">
                    Per-leg limit (m)
                    <input
                      type="number"
                      min="0"
                      max="10000"
                      {...register("max_leg_distance_m", {
                        valueAsNumber: true,
                      })}
                    />
                  </label>
                  <label className="field">
                    Total limit (m)
                    <input
                      type="number"
                      min="0"
                      max="50000"
                      {...register("max_total_distance_m", {
                        valueAsNumber: true,
                      })}
                    />
                  </label>
                </div>
                <p className="field-help">
                  A leg is one walking or rolling part of your journey. Unknown
                  route lengths cannot pass these checks.
                </p>
                <label className="field">
                  Rest every (minutes)
                  <input
                    type="number"
                    min="10"
                    max="180"
                    {...register("rest_every_minutes", { valueAsNumber: true })}
                  />
                </label>
                <label className="field">
                  What do you enjoy?
                  <input
                    {...register("interests")}
                    placeholder="For example: art, history, coffee"
                  />
                </label>
                <p className="field-help">
                  Separate interests with commas. Matching uses explicit
                  categories in development mode. Live Qloo ranking uses
                  resolved place tags or cultural entities, when available. Use
                  entity:Radiohead for a named cultural seed.
                </p>
                <label className="field">
                  Anything else? <span className="optional">Optional</span>
                  <textarea
                    rows={2}
                    {...register("intent")}
                    placeholder="Describe the kind of day you have in mind"
                  />
                </label>
                <Button
                  className="secondary full"
                  onPress={async () => {
                    try {
                      const result = await api<{
                        interests: string[];
                        clarification: string | null;
                      }>("/intent", {
                        method: "POST",
                        body: JSON.stringify({ text: watch("intent") }),
                      });
                      if (result.interests.length)
                        setValue("interests", result.interests.join(", "));
                      else
                        setError(
                          result.clarification ||
                            "Review the structured controls before planning.",
                        );
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Suggest interests from my note <Sparkles size={16} />
                </Button>
                {Object.entries(errors).map(([field, issue]) => (
                  <p className="form-error" key={field} role="alert">
                    {field.replaceAll("_", " ")}: {issue.message}
                  </p>
                ))}
                <Button
                  type="submit"
                  className="full generate"
                  isDisabled={
                    !ready ||
                    busy ||
                    !!(
                      plan &&
                      history.find(
                        (p) => p.id === plan.id && p.version > plan.version,
                      )
                    )
                  }
                >
                  {busy
                    ? "Building your outline…"
                    : plan
                      ? "Replan with these details"
                      : "Create my outing"}
                  <ArrowRight size={18} />
                </Button>
                {plan &&
                  history.some(
                    (p) => p.id === plan.id && p.version > plan.version,
                  ) && (
                    <Button
                      className="text-button"
                      onPress={() => restorePlan(plan.id)}
                    >
                      Return to latest version to replan
                    </Button>
                  )}
                <p className="privacy-note">
                  No sign-up. Your active session expires in 24 hours.
                </p>
              </form>
            </aside>
            <section className="results-panel" aria-label="Outing workspace">
              {error && (
                <div role="alert" className="error-banner">
                  <span>{error}</span>
                  {!ready && (
                    <Button onPress={() => location.reload()}>
                      Retry connection
                    </Button>
                  )}
                  <Button
                    className="icon ghost"
                    aria-label="Dismiss message"
                    onPress={() => setError("")}
                  >
                    <X size={18} />
                  </Button>
                </div>
              )}
              <div
                className="workspace-tabs"
                role="tablist"
                aria-label="Workspace"
              >
                {[
                  ["explore", "Discover"],
                  ["plan", "Itinerary"],
                  ["trips", "City collection"],
                ].map(([id, label]) => (
                  <button
                    key={id}
                    role="tab"
                    aria-selected={tab === id}
                    onClick={() => setTab(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {tab === "explore" && (
                <>
                  <div className="results-heading">
                    <div>
                      <h2>
                        A little inspiration in {city?.name || "your city"}
                      </h2>
                      <p>
                        {places.length} places to explore. Get to know the
                        evidence first.
                      </p>
                    </div>
                    <div className="view-switch" aria-label="Results view">
                      <Button
                        className={view === "list" ? "selected" : "ghost"}
                        aria-pressed={view === "list"}
                        onPress={() => setView("list")}
                      >
                        List
                      </Button>
                      <Button
                        className={view === "map" ? "selected" : "ghost"}
                        aria-pressed={view === "map"}
                        onPress={() => setView("map")}
                      >
                        Map
                      </Button>
                    </div>
                  </div>
                  {view === "map" && city && (
                    <MapPanel
                      places={places}
                      city={city}
                      selected={selected}
                      onSelect={selectPlace}
                    />
                  )}
                  {(!ready || placeQuery.isPending) && (
                    <p role="status">
                      Loading the city catalogue and recorded evidence...
                    </p>
                  )}
                  {placeQuery.isError && (
                    <div role="alert" className="notice">
                      The catalogue could not load.{" "}
                      <Button
                        onPress={() => {
                          void placeQuery.refetch();
                        }}
                      >
                        Retry discovery
                      </Button>
                    </div>
                  )}
                  <div className="place-grid" aria-busy={placeQuery.isFetching}>
                    {places.map((p, i) => (
                      <PlaceCard
                        key={p.id}
                        place={p}
                        index={i}
                        selected={selected === p.id}
                        onSelect={() => setSelected(p.id)}
                        onEvidence={() => showEvidence(p)}
                      />
                    ))}
                  </div>
                  <div className="source-footer">
                    <span>More places, with uncertainty kept visible.</span>
                    <Button
                      className="text-button"
                      onPress={async () => {
                        setOsmState("Searching OpenStreetMap…");
                        try {
                          const r = await api<{
                            status: string;
                            places: Place[];
                          }>(`/cities/${cityId}/discover`);
                          if (r.status === "live")
                            setPlaces((old) => [
                              ...old.filter((p) => !p.id.startsWith("osm-")),
                              ...r.places,
                            ]);
                          setOsmState(
                            r.status === "live"
                              ? `${r.places.length} OSM discovery previews found. Only the curated catalogue is used for planning.`
                              : "OpenStreetMap is temporarily unavailable. Curated places remain usable.",
                          );
                        } catch {
                          setOsmState(
                            "Discovery unavailable. Curated places remain usable.",
                          );
                        }
                      }}
                    >
                      Check nearby OSM coverage <ArrowUpRight size={16} />
                    </Button>
                  </div>
                  {osmState && (
                    <p role="status" className="coverage-note">
                      {osmState}
                    </p>
                  )}
                </>
              )}
              {tab === "plan" && (
                <>
                  <div className="results-heading">
                    <div>
                      <p className="eyebrow">A DAY WITH ROOM TO BREATHE</p>
                      <h2>Your outing outline</h2>
                    </div>
                    {plan && (
                      <span className="badge warn">
                        Version {plan.version} · Provisional
                      </span>
                    )}
                  </div>
                  {progress.length > 0 && (
                    <section className="activity">
                      <h3>
                        <Layers3 size={17} />
                        Planning activity
                      </h3>
                      <ol>
                        {progress
                          .filter((e) => e.status !== "reconnecting")
                          .map((e) => (
                            <li key={`${e.sequence}-${e.stage}`}>
                              <span className={`activity-dot ${e.status}`} />
                              {e.summary}
                            </li>
                          ))}
                      </ol>
                      {busy && runId && (
                        <Button
                          className="secondary"
                          onPress={async () => {
                            await api(`/runs/${runId}/cancel`, {
                              method: "POST",
                            });
                          }}
                        >
                          Cancel planning
                        </Button>
                      )}
                      <p role="status" aria-live="polite">
                        {progress.at(-1)?.summary}
                      </p>
                    </section>
                  )}
                  {!plan && !busy && (
                    <div className="empty-state">
                      <Compass size={40} />
                      <h3>Your next good day starts here.</h3>
                      <p>
                        Choose your interests and requirements, then create an
                        outing. We’ll keep known facts and open questions
                        separate.
                      </p>
                    </div>
                  )}
                  {plan && (
                    <>
                      <div className="notice">
                        <ShieldCheck size={22} />
                        <div>
                          <h3>This outline needs your checks.</h3>
                          <p>
                            Venue evidence is separate from journey
                            verification. Opening hours, travel duration and
                            door-to-door access remain unverified.
                          </p>
                        </div>
                      </div>
                      <p className="plan-summary">{plan.explanation.summary}</p>
                      <p className="meta">
                        Explanation: {plan.explanation.provider}
                        {plan.explanation.error
                          ? " · Language service unavailable; factual template retained"
                          : ""}
                      </p>
                      <ol className="timeline">
                        {plan.stops.map((stop, i) => (
                          <li key={stop.place.id}>
                            <span className="timeline-number">{i + 1}</span>
                            <div>
                              <p className="eyebrow">
                                SUGGESTED STOP · TIME TO CONFIRM
                              </p>
                              <h3>{stop.place.name}</h3>
                              {plan.verification_needed.some(
                                (p) => p.id === stop.place.id,
                              ) && (
                                <p className="leg-warning">
                                  Verification-needed alternative: this venue
                                  does not meet your mandatory evidence
                                  requirements and is excluded from eligible
                                  recommendations.
                                </p>
                              )}
                              <p>
                                {stop.suggested_visit_minutes} min suggested
                                visit · opening window unknown
                              </p>
                              <Button
                                className="text-button"
                                onPress={() => showEvidence(stop.place)}
                              >
                                Check venue evidence <ArrowUpRight size={15} />
                              </Button>
                              <div className="rest-note">
                                <Coffee size={16} />
                                Plan a rest after {stop.rest_every_minutes}{" "}
                                minutes; seating availability needs checking.
                              </div>
                              {plan.legs[i] && (
                                <p className="leg-warning">
                                  ↳ At least{" "}
                                  {plan.legs[i].distance_lower_bound_m} m
                                  straight-line separation to the next stop.
                                  Actual route and duration unknown.
                                </p>
                              )}
                            </div>
                          </li>
                        ))}
                      </ol>
                      {!plan.stops.length && (
                        <div className="empty-state">
                          There is not enough time or distance allowance for an
                          outline. Edit your requirements; no confirmed plan was
                          published.
                        </div>
                      )}
                      {plan.diff && (
                        <section className="soft-panel">
                          <h3>
                            What changed from version {plan.diff.from_version}?
                          </h3>
                          <p>
                            Added: {plan.diff.added.join(", ") || "none"}.
                            Removed: {plan.diff.removed.join(", ") || "none"}.
                          </p>
                          <Button
                            className="text-button"
                            onPress={() =>
                              restorePlan(plan.id, plan.diff!.from_version)
                            }
                          >
                            View previous version <ArrowUpRight size={14} />
                          </Button>
                        </section>
                      )}
                      <section className="soft-panel">
                        <h3>
                          {plan.taste.live
                            ? "Qloo Impact Lab"
                            : "Development ranking comparison"}
                        </h3>
                        <p>
                          {plan.taste.warning ||
                            "Comparing the same eligible candidate set. Unscored candidates keep stable place order."}
                        </p>
                        <div className="comparison">
                          <div>
                            <h4>Baseline</h4>
                            <ol>
                              {plan.baseline_order.map((id) => (
                                <li key={id}>
                                  {places.find((p) => p.id === id)?.name || id}
                                </li>
                              ))}
                            </ol>
                          </div>
                          <div>
                            <h4>
                              {plan.taste.live
                                ? "Qloo-informed"
                                : "Category matching"}
                            </h4>
                            <ol>
                              {plan.taste.order.map((id) => (
                                <li key={id}>
                                  {places.find((p) => p.id === id)?.name || id}
                                  {plan.taste.live &&
                                  plan.taste.unmapped?.includes(id)
                                    ? " ? unscored"
                                    : ""}
                                </li>
                              ))}
                            </ol>
                          </div>
                        </div>
                        {!plan.baseline_order.length && (
                          <p>
                            No venue meets all your mandatory evidence
                            requirements. Preview stops are verification-needed
                            alternatives, not eligible recommendations.
                          </p>
                        )}
                        <p className="meta">
                          Baseline uses stable place order because verified
                          travel durations are unavailable. Qloo scores are
                          relative to this request, not enjoyment probabilities.
                          Unmapped candidates have no Qloo score.
                        </p>
                      </section>
                      {plan.environment.knowledge?.passages.length ? (
                        <section className="soft-panel">
                          <h3>From the recorded sources</h3>
                          <p>
                            Retrieved guidance supports venue context, not
                            current route or opening verification.
                          </p>
                          {plan.environment.knowledge.passages.map((p) => (
                            <div key={p.id}>
                              <p>{p.text}</p>
                              <a
                                href={p.source_url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {p.source_title} <ExternalLink size={14} />
                              </a>
                            </div>
                          ))}
                        </section>
                      ) : null}
                      <div className="provider-row">
                        <span>
                          Weather: {String(plan.environment.weather.status)}
                        </span>
                        <span>
                          Transport:{" "}
                          {String(plan.environment.transport.provider)} ·
                          unverified routes
                        </span>
                      </div>
                      <div className="plan-actions">
                        <Button
                          className="secondary"
                          onPress={() =>
                            document
                              .getElementById("planner-form")
                              ?.scrollIntoView()
                          }
                        >
                          Edit & replan <RotateCcw size={16} />
                        </Button>
                        {trip ? (
                          <Button onPress={attachPlan}>
                            Add to {trip.title} <Plus size={16} />
                          </Button>
                        ) : (
                          <Button
                            className="secondary"
                            onPress={async () => {
                              await newTrip();
                              setTab("trips");
                            }}
                          >
                            Start a city collection <Plus size={16} />
                          </Button>
                        )}
                      </div>
                    </>
                  )}
                  {history.length > 0 && (
                    <section className="history">
                      <h3>Saved in this session</h3>
                      {history.map((p) => (
                        <Button
                          key={p.id}
                          className="text-button"
                          onPress={() => restorePlan(p.id)}
                        >
                          {p.city_id} · version {p.version}{" "}
                          <ArrowUpRight size={14} />
                        </Button>
                      ))}
                    </section>
                  )}
                </>
              )}
              {tab === "trips" && (
                <TripWorkspace
                  cities={cities}
                  trip={trip}
                  trips={trips}
                  setTrip={setTrip}
                  saveTrip={saveTrip}
                  newTrip={newTrip}
                  plan={plan}
                  attachPlan={attachPlan}
                />
              )}
            </section>
          </div>
          <section className="principles">
            <div>
              <ShieldCheck />
              <h3>See what we know.</h3>
              <p>Every recorded access feature links to its source.</p>
            </div>
            <div>
              <Heart />
              <h3>Keep your interests.</h3>
              <p>Personal taste matters, after mandatory needs are checked.</p>
            </div>
            <div>
              <Clock3 />
              <h3>Leave a little room.</h3>
              <p>Rest, unknowns and changing plans belong in the picture.</p>
            </div>
          </section>
        </div>
      </main>
      <footer className="site-footer">
        <a className="brand" href="/">
          <span className="brand-word">
            access
            <wbr />
            life.
          </span>
        </a>
        <p>
          Evidence-led planning with Qloo when available. Live journey
          validation remains pending.
        </p>
        <Button
          className="text-button"
          onPress={async () => {
            events.current?.close();
            await api("/sessions/current", { method: "DELETE" });
            location.reload();
          }}
        >
          Clear my session
        </Button>
        <a
          href="https://github.com/saimaharana4/accesslife-ai"
          target="_blank"
          rel="noreferrer"
        >
          Source & limitations <ArrowUpRight size={14} />
        </a>
      </footer>
      <EvidenceDialog
        place={details}
        records={evidence}
        onClose={() => setDetails(null)}
      />
    </>
  );
}

export default function Application() {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <ApplicationContent />
    </QueryClientProvider>
  );
}
