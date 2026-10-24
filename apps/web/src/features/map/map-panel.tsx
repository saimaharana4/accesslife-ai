"use client";
import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Place, City } from "@/lib/api/client";
export default function MapPanel({
  places,
  city,
  selected,
  onSelect,
}: {
  places: Place[];
  city: City;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [unavailable, setUnavailable] = useState(false);
  const markers = useRef<Map<string, HTMLButtonElement>>(new Map());
  useEffect(() => {
    if (!container.current) return;
    setUnavailable(false);
    let map: maplibregl.Map | undefined;
    try {
      map = new maplibregl.Map({
        container: container.current,
        style: "https://tiles.openfreemap.org/styles/liberty",
        center: [city.longitude, city.latitude],
        zoom: 11,
        attributionControl: { compact: false },
      });
      map.addControl(new maplibregl.NavigationControl(), "top-right");
      map.on("error", () => setUnavailable(true));
      places.forEach((place) => {
        const button = document.createElement("button");
        button.className = `map-pin ${selected === place.id ? "selected" : ""}`;
        button.textContent = "●";
        button.setAttribute("aria-label", `Select ${place.name}`);
        button.onclick = () => onSelect(place.id);
        markers.current.set(place.id, button);
        new maplibregl.Marker({ element: button })
          .setLngLat([place.longitude, place.latitude])
          .addTo(map!);
      });
    } catch {
      setUnavailable(true);
      if (container.current)
        container.current.textContent =
          "Map unavailable. All places and actions remain in the list.";
    }
    return () => {
      map?.remove();
      markers.current.clear();
    };
  }, [places, city, onSelect]);
  useEffect(() => {
    markers.current.forEach((button, id) =>
      button.classList.toggle("selected", id === selected),
    );
  }, [selected]);
  return (
    <div className="map-wrap">
      <div
        className="map-canvas"
        ref={container}
        aria-label={`Map of ${city.name}`}
      />
      <div className="map-note" role="status">
        {unavailable
          ? "Some map resources could not load. All places and actions remain available in the list."
          : "Approximate venue locations · No verified route geometry"}
      </div>
    </div>
  );
}
