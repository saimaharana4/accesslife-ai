"use client";
import { useState, type Dispatch, type SetStateAction } from "react";
import { Globe2, Plus, ArrowUp, ArrowDown, X, CircleHelp } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { City, Trip, Plan } from "@/lib/api/client";
type Props = {
  cities: City[];
  trip: Trip | null;
  trips: Trip[];
  setTrip: Dispatch<SetStateAction<Trip | null>>;
  saveTrip: (next: Trip) => Promise<void>;
  newTrip: () => Promise<void>;
  plan: Plan | null;
  attachPlan: () => Promise<void>;
};
export default function TripWorkspace({
  cities,
  trip,
  trips,
  setTrip,
  saveTrip,
  newTrip,
  plan,
  attachPlan,
}: Props) {
  const [tripCity, setTripCity] = useState("london"),
    [tripDate, setTripDate] = useState(new Date().toLocaleDateString("en-CA"));
  return (
    <>
      <div className="results-heading">
        <div>
          <p className="eyebrow">ONE JOURNEY, MORE PERSPECTIVES</p>
          <h2>Your city collection</h2>
          <p>
            Local outlines together. Travel between them is yours to arrange.
          </p>
        </div>
        <Button className="secondary" onPress={newTrip}>
          <Plus size={16} />
          New collection
        </Button>
      </div>
      <div className="trip-chooser">
        {trips.map((t) => (
          <Button
            key={t.id}
            className={trip?.id === t.id ? "secondary" : "text-button"}
            onPress={() => setTrip(t)}
          >
            {t.title} · {t.segments.length} cities
          </Button>
        ))}
      </div>
      {!trip ? (
        <div className="empty-state">
          <Globe2 size={40} />
          <h3>Collect a few good days.</h3>
          <p>
            Create a collection and add city dates or attach your current local
            outline.
          </p>
        </div>
      ) : (
        <>
          <label className="field">
            Collection name
            <input
              value={trip.title}
              onChange={(e) => setTrip({ ...trip, title: e.target.value })}
              onBlur={() => saveTrip(trip)}
            />
          </label>
          <div className="trip-add">
            <label className="field">
              City
              <select
                value={tripCity}
                onChange={(e) => setTripCity(e.target.value)}
              >
                {cities.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Local date
              <input
                type="date"
                value={tripDate}
                onChange={(e) => setTripDate(e.target.value)}
              />
            </label>
            <Button
              onPress={() =>
                saveTrip({
                  ...trip,
                  segments: [
                    ...trip.segments,
                    {
                      id: crypto.randomUUID(),
                      city_id: tripCity as City["id"],
                      date: tripDate,
                    },
                  ].sort((a, b) => a.date.localeCompare(b.date)),
                })
              }
            >
              <Plus size={17} />
              Add city
            </Button>
          </div>
          {trip.segments.map((s, i) => (
            <div key={s.id}>
              <article className="trip-segment">
                <span className="step-number">0{i + 1}</span>
                <div>
                  <h3>{cities.find((c) => c.id === s.city_id)?.name}</h3>
                  <label className="field">
                    Local date
                    <input
                      type="date"
                      value={s.date}
                      onChange={(e) =>
                        saveTrip({
                          ...trip,
                          segments: trip.segments.map((x) =>
                            x.id === s.id
                              ? {
                                  ...x,
                                  date: e.target.value,
                                  plan_id: null,
                                  plan_version: null,
                                }
                              : x,
                          ),
                        })
                      }
                    />
                  </label>
                  <p className="meta">
                    {s.plan_id
                      ? `Provisional plan v${s.plan_version} attached`
                      : "No local plan attached"}
                  </p>
                </div>
                <div className="segment-actions">
                  <Button
                    className="icon secondary"
                    aria-label={`Move ${s.city_id} up`}
                    isDisabled={i === 0}
                    onPress={() => {
                      const segments = [...trip.segments];
                      [segments[i - 1], segments[i]] = [
                        segments[i],
                        segments[i - 1],
                      ];
                      saveTrip({ ...trip, segments });
                    }}
                  >
                    <ArrowUp size={16} />
                  </Button>
                  <Button
                    className="icon secondary"
                    aria-label={`Move ${s.city_id} down`}
                    isDisabled={i === trip.segments.length - 1}
                    onPress={() => {
                      const segments = [...trip.segments];
                      [segments[i + 1], segments[i]] = [
                        segments[i],
                        segments[i + 1],
                      ];
                      saveTrip({ ...trip, segments });
                    }}
                  >
                    <ArrowDown size={16} />
                  </Button>
                  <Button
                    className="icon ghost"
                    aria-label={`Remove ${s.city_id}`}
                    onPress={() =>
                      saveTrip({
                        ...trip,
                        segments: trip.segments.filter((x) => x.id !== s.id),
                      })
                    }
                  >
                    <X size={17} />
                  </Button>
                </div>
              </article>
              {i < trip.segments.length - 1 && (
                <div className="transfer-gap">
                  <CircleHelp size={16} />
                  Inter-city travel: user-arranged and unverified. Timing and
                  accessibility are not checked.
                </div>
              )}
            </div>
          ))}
          {plan && (
            <Button className="secondary" onPress={attachPlan}>
              Attach current {plan.inputs.city_id} outline <Plus size={16} />
            </Button>
          )}
        </>
      )}
    </>
  );
}
