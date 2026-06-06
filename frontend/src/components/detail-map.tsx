"use client";

import { useEffect } from "react";

interface DetailMapProps {
  lat: number;
  lng: number;
  title: string;
}

export default function DetailMap({ lat, lng, title }: DetailMapProps) {
  useEffect(() => {
    let map: any = null;

    const init = async () => {
      const L = (await import("leaflet")).default;
      await import("leaflet/dist/leaflet.css");

      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
        iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
        shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
      });

      const container = document.getElementById("detail-map");
      if (!container || (container as any)._leaflet_id) return;

      map = L.map("detail-map").setView([lat, lng], 15);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      const icon = L.divIcon({
        className: "",
        html: `<div style="
          background:#0f172a;border-radius:50% 50% 50% 0;transform:rotate(-45deg);
          width:32px;height:32px;border:3px solid white;
          box-shadow:0 2px 8px rgba(0,0,0,0.3);
        "></div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 32],
      });

      L.marker([lat, lng], { icon })
        .addTo(map)
        .bindPopup(title)
        .openPopup();
    };

    init();
    return () => { if (map) map.remove(); };
  }, [lat, lng, title]);

  return <div id="detail-map" className="w-full h-64 rounded-xl z-0" />;
}