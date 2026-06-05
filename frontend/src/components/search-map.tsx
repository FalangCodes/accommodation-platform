"use client";

import { useEffect } from "react";
import { MapPin } from "lucide-react";

interface MapItem {
  id: number;
  title: string;
  address: string;
  price_min: number;
  price_max: number;
  average_rating?: number;
}

interface SearchMapProps {
  items: MapItem[];
  isLoading: boolean;
  onMarkerClick: (id: number) => void;
}

export default function SearchMap({ items, isLoading, onMarkerClick }: SearchMapProps) {
  useEffect(() => {
    // Dynamically import Leaflet only on client
    let map: any = null;

    const initMap = async () => {
      const L = (await import("leaflet")).default;
      await import("leaflet/dist/leaflet.css");

      // Fix default marker icon paths broken by webpack
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
        iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
        shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
      });

      const container = document.getElementById("search-map-container");
      if (!container || (container as any)._leaflet_id) return;

      // Default center: SPU Kimberley
      map = L.map("search-map-container").setView([-28.7282, 24.7435], 13);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      // Custom marker icon
      const customIcon = L.divIcon({
        className: "",
        html: `<div style="
          background: #0f172a;
          color: white;
          border-radius: 50% 50% 50% 0;
          transform: rotate(-45deg);
          width: 32px;
          height: 32px;
          border: 3px solid white;
          box-shadow: 0 2px 8px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
        "></div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -36],
      });

      items.forEach((item) => {
        // NOTE: accommodation objects need lat/lng — this requires the backend
        // to return coordinates in the search response. For now we show a
        // placeholder at SPU coordinates offset by index.
        // TODO: add lat/lng fields to AccommodationOut schema.
        const lat = -28.7282 + (Math.random() - 0.5) * 0.05;
        const lng = 24.7435 + (Math.random() - 0.5) * 0.05;

        const marker = L.marker([lat, lng], { icon: customIcon }).addTo(map);

        marker.bindPopup(`
          <div style="min-width: 180px; font-family: system-ui, sans-serif;">
            <p style="font-weight: 600; font-size: 14px; margin: 0 0 4px;">${item.title}</p>
            <p style="font-size: 12px; color: #64748b; margin: 0 0 6px;">${item.address}</p>
            <p style="font-size: 13px; font-weight: 600; margin: 0 0 8px; color: #0f172a;">
              R${item.price_min.toLocaleString()} / month
            </p>
            <button
              onclick="window._accomFindNav(${item.id})"
              style="
                background: #0f172a; color: white; border: none;
                padding: 6px 14px; border-radius: 8px;
                font-size: 12px; font-weight: 500; cursor: pointer; width: 100%;
              "
            >View listing</button>
          </div>
        `);
      });

      // Expose navigation callback for popup buttons
      (window as any)._accomFindNav = onMarkerClick;
    };

    initMap();

    return () => {
      if (map) {
        map.remove();
      }
      delete (window as any)._accomFindNav;
    };
  }, [items]);

  if (isLoading) {
    return (
      <div className="w-full h-[600px] rounded-2xl bg-slate-100 animate-pulse flex items-center justify-center">
        <MapPin className="w-8 h-8 text-slate-300" />
      </div>
    );
  }

  return (
    <div className="relative">
      <div
        id="search-map-container"
        className="w-full h-[600px] rounded-2xl overflow-hidden border border-slate-200 shadow-sm z-0"
      />
      <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm rounded-xl px-3 py-2 text-xs text-slate-500 border border-slate-200 shadow-sm">
        ⚠️ Map positions are approximate until coordinates are returned from the API
      </div>
    </div>
  );
}